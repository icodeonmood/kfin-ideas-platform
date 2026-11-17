"""L-SUBMIT.send: Submit. One transaction does all of it, or none of it:

1. The idea gets its reference at once, `IDEA-<year>-<six-digit running number>` (`next_idea_ref`, the office year),
   and status `checking` (stage "Shared" done, "Checked and matched" now). The draft row becomes the idea, so its
   files, hidden details and sealed words stay with it.
2. The declaration's text version and the time are recorded (`L-SUBMIT.pre/5`); the sorting was confirmed before.
3. The review clock starts: decide-by 5 working days on (`submit.clock`), on lane A's timer engine (kind
   `decide_by`). The edit window closes when the desk opens the idea, at the latest 3 days on.
4. The sharer leads their idea's crew (`crew_members`, via `shared`).
5. "Checked and matched" is queued (`submit.check`): the final hidden-detail pass and similar ideas, then the idea
   goes to the review desk and the sharer is told (`notify.post`, `sent_to_desk`). Voice notes held for the draft go
   now that it is shared (DEC-096).
6. `audit_log` gets the share, with IDs and codes only.

Submit is idempotent twice over (`L-SUBMIT.send` failures): with an `Idempotency-Key` the first result comes back
(A-API.conventions/3), and without one, a draft already sent answers with its hand-over rather than a second idea.

What comes back is what `S-06` "Just shared" shows at once (V-ACC.share/12): the reference, the stage track, "The
review desk will look at it by …" and the edit-and-withdraw date, as words computed here (A-API.conventions/6).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from psycopg.types.json import Jsonb

from core.db import Conn
from jobs.runner import enqueue
from submit import clock, config, own, ready, sorting
from submit.errors import Refused
from submit.words import countdown, day, pill, short_date, stage_nodes, when_shared

ROUTE = "POST /drafts/:id/submit"
SHARED = ("checking", "with_review_desk", "needs_you")


def _hash(key: str, body: dict[str, Any]) -> str:
    raw = json.dumps({"draft": key, "declaration_version": body.get("declaration_version")}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _claim_key(conn: Conn, user_id: str, idem: str, request_hash: str) -> dict[str, Any] | None:
    """Claim the Idempotency-Key inside the transaction, or return the first result for it. A second request with
    the same key waits here until the first commits or rolls back."""
    conn.execute(
        "DELETE FROM idempotency_keys WHERE user_id = %s AND key = %s AND expires_at < now()", (user_id, idem)
    )
    claimed = conn.execute(
        "INSERT INTO idempotency_keys (key, user_id, route, request_hash) VALUES (%s, %s, %s, %s) "
        "ON CONFLICT DO NOTHING RETURNING key",
        (idem, user_id, ROUTE, request_hash),
    ).fetchone()
    if claimed:
        return None
    row = conn.execute(
        "SELECT route, request_hash, status, response_json FROM idempotency_keys WHERE user_id = %s AND key = %s",
        (user_id, idem),
    ).fetchone()
    if row is None or row["route"] != ROUTE or row["request_hash"] != request_hash:
        raise Refused(422, "idempotency_key_reused", "Something went wrong. Try again.")
    if row["response_json"] is None:
        return None
    return dict(row["response_json"])


def checked_line(n_hidden: int, n_similar: int) -> str:
    """'Personal details hidden, 2 similar ideas found' (the sharer's track, Status.md)."""
    if n_hidden > 1:
        first = "Personal details hidden"
    elif n_hidden == 1:
        first = "1 personal detail hidden"
    else:
        first = "No personal details found"
    similar = (
        f"{n_similar} similar idea{'s' * (n_similar != 1)} found" if n_similar else "no similar ideas found"
    )
    return f"{first}, {similar}"


def handover(conn: Conn, idea: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    """What S-06 shows the moment an idea is shared (and again on a repeated Submit): IDs, the track and the dates,
    as words. The page itself is lane E's (`GET /ideas/:id`)."""
    ref = str(idea["idea_id"])
    status = str(idea["status"])
    shared_at: dt.datetime = idea["shared_at"]
    decide: dt.datetime | None = idea.get("decide_by")
    closes: dt.datetime | None = idea.get("edit_closes_at")
    by = day(decide, now) if decide else None
    shared = ("done", when_shared(shared_at, now), shared_at)
    later = [("to_come", "If it’s picked", None), ("to_come", "Then we measure what changed", None)]
    if status == "checking":
        nodes = [shared, ("now", "Checking…", None), ("to_come", None, None), *later]
    elif status in ("with_review_desk", "needs_you"):
        hid = conn.execute(
            "SELECT count(*) AS n FROM hidden_details WHERE idea_uuid = %s AND state = 'hidden'",
            (idea["id"],),
        ).fetchone()
        sim = conn.execute(
            "SELECT count(*) AS n FROM similar_links WHERE idea_uuid = %s", (idea["id"],)
        ).fetchone()
        nodes = [
            shared,
            ("done", checked_line(int(hid["n"]) if hid else 0, int(sim["n"]) if sim else 0), None),
            ("now", f"By {by}" if by else None, None),
            *later,
        ]
    else:
        nodes = []
    window_open = (
        status in ("checking", "with_review_desk")
        and idea.get("opened_at") is None
        and closes is not None
        and now < closes
    )
    out: dict[str, Any] = {
        "idea_id": ref,
        "id": str(idea["id"]),
        "ref": ref,
        "status": status,
        "pill": pill(status),
        "title": idea.get("title") or "",
        "shared_at": shared_at.isoformat(),
        "shared_label": f"Shared {short_date(shared_at)}",
        "stages": stage_nodes(nodes) if nodes else [],
        "next": {"to": f"/ideas/{ref}", "replace": True, "state": "just_shared"},
    }
    if decide is not None:
        out["review"] = {
            "decide_by": decide.isoformat(),
            "by_label": f"By {by}",
            "line": f"The review desk will look at it by {by}. We’ll tell you on Teams and by email when anything "
            "changes.",
        }
    if closes is not None:
        out["edit_window"] = {
            "open": window_open,
            "closes_at": closes.isoformat(),
            **(
                {
                    "line": f"Open to changes until {day(closes, now)}. Edit or withdraw it any time before the review "
                    "desk opens it. We tell you on Teams and by email when anything moves.",
                    "countdown": countdown(closes, now),
                    "edit": {"label": "Edit it", "to": f"/ideas/{ref}/edit"},
                }
                if window_open
                else {}
            ),
        }
    return out


def submit(
    conn: Conn, key: str, user_id: str, body: Any, *, idempotency_key: str | None = None, now: dt.datetime
) -> tuple[int, dict[str, Any]]:
    """`POST /drafts/:id/submit` `{declaration_version}` → (HTTP status, the hand-over to S-06)."""
    if not isinstance(body, dict):
        raise Refused(400, "body_required", "Something went wrong. Try again.")
    version = body.get("declaration_version")
    if version != config.DECLARATION_VERSION:
        raise Refused(
            409,
            "declaration_changed",
            "The declaration beside Submit has changed. Read it again, then submit.",
            "declaration",
            version=config.DECLARATION_VERSION,
            text=config.DECLARATION["submit"],
        )
    li = config.lists()
    p = config.promises()
    with conn.transaction():
        if idempotency_key:
            first = _claim_key(conn, user_id, idempotency_key, _hash(key, body))
            if first is not None:
                return int(first.get("_status", 200)), {k: v for k, v in first.items() if k != "_status"}
        idea, code = own.load_own(conn, key, user_id, lock=True)
        if idea["status"] in SHARED and idea["idea_id"]:
            return 200, handover(conn, idea, now)  # already sent: never a second idea
        if idea["status"] not in ("draft", "merged"):
            raise Refused(409, "not_a_draft", "This idea has been sent.", ref=idea["idea_id"])
        found = ready.problems(conn, idea, li)
        if found:
            raise found[0]

        uid = str(idea["id"])
        title, summary = ready.title_and_summary(conn, idea)
        choices = sorting.current(conn, idea, li)
        fix_included = ready.fix_line(conn, uid) is not None
        ref_row = conn.execute("SELECT next_idea_ref(%s) AS ref", (now,)).fetchone()
        assert ref_row is not None
        ref = str(ref_row["ref"])
        decide = clock.decide_by(now, p)
        closes = clock.edit_closes(now, p)
        city = conn.execute(
            "SELECT u.location FROM contributor_map m JOIN users u ON u.id = m.user_id WHERE m.contributor_code = %s",
            (code,),
        ).fetchone()
        updated = conn.execute(
            "UPDATE ideas SET status = 'checking', idea_id = %s, title = %s, summary = %s, often = %s, city = %s, "
            "kind = %s, affects = %s, area = %s, brings = %s, shared_at = %s, "
            "share_seconds = GREATEST(0, EXTRACT(EPOCH FROM (%s - created_at)))::int, declaration_version = %s, "
            "declared_at = %s, edit_closes_at = %s, decide_by = %s, step = 'send', saved_at = %s "
            "WHERE id = %s AND status IN ('draft') RETURNING *",
            (
                ref,
                title,
                summary,
                ready.often(conn, idea),
                city["location"] if city else None,
                sorting.stored_kind(str(choices["kind"].value), fix_included),
                list(choices["affects"].value),
                choices["area"].value,
                list(choices["brings"].value),
                now,
                now,
                config.DECLARATION_VERSION,
                now,
                closes,
                decide,
                now,
                uid,
            ),
        ).fetchone()
        if updated is None:
            raise Refused(409, "not_a_draft", "This idea has been sent.")
        shared = dict(updated)
        clock.start_review_clock(conn, ref, now, decide)
        conn.execute(
            "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES (%s, %s, 'lead', 'shared') "
            "ON CONFLICT DO NOTHING",
            (uid, code),
        )
        enqueue(conn, "submit.check", {"idea_uuid": uid}, dedupe_key=f"submit.check:{uid}")
        enqueue(conn, "voice.purge", {"idea_uuid": uid})
        sources = shared.get("sorting_sources") or {}
        own.audit(
            conn,
            user_id,
            "idea.submit",
            shared,
            {
                "status": "checking",
                "declaration_version": config.DECLARATION_VERSION,
                "with_fix": fix_included,
                "sorting": {f: (sources.get(f) or {}).get("source") for f in sorting.FIELDS},
            },
        )
        result = handover(conn, shared, now)
        if idempotency_key:
            conn.execute(
                "UPDATE idempotency_keys SET status = 201, response_json = %s WHERE user_id = %s AND key = %s",
                (Jsonb({**result, "_status": 201}), user_id, idempotency_key),
            )
        return 201, result
