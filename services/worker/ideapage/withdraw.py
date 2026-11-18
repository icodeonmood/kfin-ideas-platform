"""Withdraw and restore, the sharer's two actions on their own idea (L-SUBMIT.withdraw, E-ENUMS.idea-machine).

- Withdraw: only inside the edit window (before the desk opens it, before any question is sent, and at most
  3 days after sharing). It confirms in place with an optional reason; the idea leaves every queue and the Wall
  at once and keeps its reference (L-SUBMIT.withdraw/1–2).
- Restore: any time; it shares the idea again as it was, with the same reference, and the review clock and the
  edit window start again from the restore (L-SUBMIT.withdraw/3, P-DECISIONS.signoff/3).

Crew members are told (L-SUBMIT.withdraw/4) through lane A's `notify.post`. Ending their team-up and closing
requests that wait on the idea are writes to lane F's tables: `ON_WITHDRAWN_HOOK` is where lane F plugs them in.

A restore's two clocks are first sharing's, from lane C's `submit.clock` (L-SUBMIT.send/4, L-SUBMIT.edit/1), so a
restored idea and a newly shared one get the same decide-by and edit window. The worker app plugs lane C's
`submit.adapters.on_restored` into `ON_RESTORED_HOOK`: it writes `decide_by` and `edit_closes_at`, restarts the
review clock (`clock.start_review_clock`) and queues the check, which leaves the idea at `checking`; restore then
writes none of those itself, so nothing is written twice. Without the hook, restore uses the same `submit.clock`
functions itself and moves `withdrawn → checking → with_review_desk` at once: the idea comes back as it was.

Every withdraw and restore is written to `audit_log` with IDs only (non-negotiable 9, 3).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from psycopg.types.json import Jsonb

import notify
from core.db import Conn
from ideapage import read
from ideapage.sharer import may_withdraw, sharer_view
from onepc.context import seal_text
from pii.patterns import scan
from submit import clock

REASON_MAX = 500

# Lane F (L-TEAMUP/11, L-SUBMIT.withdraw/4): end the crew's team-up and close requests waiting on the idea as
# "withdrawn by the sharer". Called inside the withdraw's transaction: (conn, idea_uuid, at) -> None.
ON_WITHDRAWN_HOOK: Callable[[Conn, str, dt.datetime], None] | None = None
# Lane C (L-SUBMIT.send/3, /4): restart the clocks from the restore and re-run the check. Called inside the restore's
# transaction after the idea is set to `checking`; it writes `decide_by`, `edit_closes_at` and the review clock, and
# the check job then moves the idea on: (conn, idea_uuid) -> None.
ON_RESTORED_HOOK: Callable[[Conn, str], None] | None = None


class Refused(Exception):
    """A-API.conventions/2: `{error: {code, message, field?, ...}}` with an HTTP status."""

    def __init__(self, status: int, code: str, message: str = "", **extra: Any) -> None:
        super().__init__(code)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, **self.extra}}


def masked_reason(text: str) -> str:
    """Customer details in the optional reason are masked before it is stored (non-negotiable 4): the person's own
    reason is read only by them, but no other copy of a detail is kept."""
    out = text
    for m in sorted(scan(text), key=lambda m: m.start, reverse=True):
        if m.action != "block":
            continue
        value = text[m.start : m.end]
        out = out[: m.start] + f"{m.label} ••••{value[-2:]}" + out[m.end :]
    return out


def _load_own(conn: Conn, key: str, me: read.Viewer) -> dict[str, Any]:
    idea = read.find_idea(conn, key)
    if idea is None or not me.is_sharer(idea):
        raise read.NotFound  # never confirm someone else's idea
    row = conn.execute("SELECT * FROM ideas WHERE id = %s FOR UPDATE", (idea["id"],)).fetchone()
    assert row is not None
    return dict(row)


def _audit(conn: Conn, user_id: str, action: str, idea: dict[str, Any], after: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, entity, after) VALUES (%s, %s, %s, %s)",
        (f"user:{user_id}", action, f"idea:{read.key_of(idea)}", Jsonb(after)),
    )


def withdraw(
    conn: Conn, key: str, user_id: str, reason: str | None = None, *, now: dt.datetime | None = None
) -> dict[str, Any]:
    """`POST /ideas/:id/withdraw` → the sharer's page in its Withdrawn state. Repeating it changes nothing."""
    t = now or read.now()
    me = read.viewer(conn, user_id)
    with conn.transaction():
        idea = _load_own(conn, key, me)
        if idea["status"] != "withdrawn":
            qset = read.question_set(conn, str(idea["id"]))
            if not may_withdraw(idea, qset, t):
                raise Refused(
                    409,
                    "edit_window_closed",
                    "The review desk has it now, so it can’t be withdrawn. Write to them in the conversation.",
                    **({"opened_by_desk_at": idea["opened_at"].isoformat()} if idea.get("opened_at") else {}),
                )
            text = " ".join(str(reason or "").split())[:REASON_MAX]
            sealed = (
                seal_text("ideas", "withdraw_reason_encrypted", str(idea["id"]), masked_reason(text))
                if text
                else None
            )
            conn.execute(
                "UPDATE ideas SET status = 'withdrawn', withdrawn_at = %s, withdraw_reason_encrypted = %s WHERE id = %s",
                (t, sealed, idea["id"]),
            )
            crew = [
                str(r["user_id"])
                for r in conn.execute(
                    "SELECT m.user_id FROM crew_members c JOIN contributor_map m ON m.contributor_code = c.contributor_code "
                    "WHERE c.idea_uuid = %s AND c.left_at IS NULL AND c.contributor_code <> %s",
                    (idea["id"], idea["contributor_code"]),
                ).fetchall()
            ]
            if crew:
                notify.post(
                    conn,
                    "stage_moved",
                    crew,
                    idea_id=str(idea["id"]),
                    sender=user_id,
                    refs={"status": "withdrawn"},
                    dedupe_key=f"withdrawn:{idea['id']}:{t.isoformat()}",
                )
            if ON_WITHDRAWN_HOOK is not None:
                ON_WITHDRAWN_HOOK(conn, str(idea["id"]), t)
            _audit(conn, user_id, "idea.withdraw", idea, {"status": "withdrawn", "with_reason": bool(text)})
        fresh = read.find_idea(conn, str(idea["id"]))
        assert fresh is not None
        return sharer_view(conn, fresh, me, t)


def restore(conn: Conn, key: str, user_id: str, *, now: dt.datetime | None = None) -> dict[str, Any]:
    """`POST /ideas/:id/restore` → the sharer's page, shared again with the same reference. Repeating it while the
    idea is back with the desk changes nothing; restoring an idea that was never withdrawn is refused."""
    t = now or read.now()
    me = read.viewer(conn, user_id)
    with conn.transaction():
        idea = _load_own(conn, key, me)
        if idea["status"] == "withdrawn":
            conn.execute(
                "UPDATE ideas SET status = 'checking', restored_at = %s, withdraw_reason_encrypted = NULL "
                "WHERE id = %s",
                (t, idea["id"]),
            )
            if ON_RESTORED_HOOK is not None:
                # Lane C's on_restored writes decide-by, the edit window and the review clock with submit.clock,
                # and queues the check: restore writes none of them too.
                ON_RESTORED_HOOK(conn, str(idea["id"]))
            else:
                p = read.promises()
                due = clock.decide_by(t, p)
                conn.execute(
                    "UPDATE ideas SET status = 'with_review_desk', decide_by = %s, edit_closes_at = %s WHERE id = %s",
                    (due, clock.edit_closes(t, p), idea["id"]),
                )
                clock.start_review_clock(conn, str(idea["idea_id"]), t, due)
            _audit(conn, user_id, "idea.restore", idea, {"status": "restored"})
        elif idea["status"] not in ("checking", "with_review_desk") or idea.get("restored_at") is None:
            raise Refused(409, "not_withdrawn", "This idea isn’t withdrawn, so there is nothing to restore.")
        fresh = read.find_idea(conn, str(idea["id"]))
        assert fresh is not None
        return sharer_view(conn, fresh, me, t)
