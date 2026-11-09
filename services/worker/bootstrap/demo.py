"""A synthetic demo for a local walkthrough (`make demo`, `make demo-reset`). Dev only: refused unless APP_ENV=dev.

Everything here is made up and clearly demo data: employee IDs `DEMO-00001`…, emails `….demo@kfintech.example`,
measures marked `"demo": true`. It is never used by the golden sets (those live in `eval/golden/`).

- **Personas** sign in through the mock IdP with their employee ID as the username (see docs/DEMO.md).
- **Other people's ideas** are written straight to the database at every stage, with neutral summaries, and go
  through the repo writer and indexer like any idea, so they appear on the wall and in Find your crew.
- **The employee's own ideas** go through the real scan, review and message flows (fake model route), so
  Find your crew, the review desk, a question from the desk and the inbox are the real thing.
- **The Ones**: six founding Ones (Nos. 1–6), three new Ones (Nos. 17–19), one retired (No. 7 resting) and one
  whose removal is approved (No. 20), plus a sponsored inclusion waiting for the chair, a tier-up waiting for
  approval, a glow-up waiting for No. 17's first sign-in and a Showcase brief partly filled.

`--reset` removes the demo's own rows (its people, their Ones records, proposals, deliveries and ideas) and its
idea files from the local company repo, then loads it again. Nobody else's rows are touched. The glow-up plays
once, so reset to see it again.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from psycopg.types.json import Jsonb

from comms.route import emit
from core.config import REPO_ROOT, get_settings
from core.crypto import encrypt_json
from core.db import Conn, connect
from identity.codes import assign_contributor_code, emp_id_hash
from ones.text import seal, seal_json

NOW = dt.datetime.now(dt.UTC)
YEAR = NOW.astimezone().year
CANVAS_EXAMPLE = (REPO_ROOT or Path.cwd()) / "agents" / "canvas-assist" / "examples" / "01-quick-capture.json"

# (employee ID, name, line of business, roles, label for DEMO.md, name on the wall)
PEOPLE: list[tuple[str, str, str, tuple[str, ...], str, bool]] = [
    ("DEMO-00001", "Kavya Menon", "LOB-mf", (), "Employee with ideas", True),
    ("DEMO-00002", "Nikhil Rao", "LOB-product-strategy", ("reviewer",), "Review desk", False),
    ("DEMO-00003", "Meera Pillai", "LOB-technology", ("core_committee",), "Core committee member", False),
    ("DEMO-00004", "Vivek Shenoy", "LOB-mf", ("core_committee", "core_chair"), "Core committee chair", False),
    ("DEMO-00005", "Demo CEO", "LOB-technology", ("ceo",), "CEO", False),
    ("DEMO-00006", "Sana Qureshi", "LOB-technology", ("admin",), "Admin", False),
    ("DEMO-00007", "Rahul Deshpande", "LOB-mf", (), "Manager with a team", False),
    (
        "DEMO-00008",
        "Ananya Rao",
        "LOB-mf",
        ("working_group",),
        "One No. 17 (glow-up waiting), delivery owner",
        True,
    ),
    ("DEMO-00009", "Rohit Menon", "LOB-mf", (), "Founding One No. 1, tier 4", True),
    ("DEMO-00010", "Priya Nair", "LOB-shared-operations", (), "", True),
    ("DEMO-00011", "Karthik Subramanian", "LOB-corporate-registry", (), "", False),
    ("DEMO-00012", "Sneha Kulkarni", "LOB-sales", (), "", True),
    ("DEMO-00013", "Deepa Joshi", "LOB-technology", ("working_group",), "Delivery PM", True),
    ("DEMO-00014", "Imran Shaikh", "LOB-mf", (), "", True),
    ("DEMO-00015", "Farhan Qureshi", "LOB-sales", (), "", True),
    ("DEMO-00016", "Lakshmi Iyer", "LOB-shared-operations", (), "", False),
    ("DEMO-00017", "Vikram Bhat", "LOB-mf", (), "Fix-track owner", False),
    ("DEMO-00018", "Gaurav Sethi", "LOB-technology", (), "", False),
    ("DEMO-00019", "Suresh Patil", "LOB-mf", (), "", False),
    ("DEMO-00020", "Pooja Iyer", "LOB-mf", (), "", True),
    ("DEMO-00021", "Aditya Kulkarni", "LOB-mf", (), "", False),
    ("DEMO-00022", "Fatima Sheikh", "LOB-shared-operations", (), "", True),
    ("DEMO-00023", "Rakesh Gupta", "LOB-mf", (), "", False),
]
MANAGER, TEAM = "DEMO-00007", ("DEMO-00001", "DEMO-00008", "DEMO-00020", "DEMO-00021")

# Other people's ideas, straight to their stage: (owner, stage, one line, neutral summary)
IDEAS: list[tuple[str, str, str, str]] = [
    (
        "DEMO-00009",
        "shipped",
        "Flag likely-wrong bank details before a payout is sent",
        "Check bank details against the IFSC and past payouts before a redemption is paid, so fewer payouts fail.",
    ),
    (
        "DEMO-00010",
        "closed",
        "One status page for every investor service request",
        "Give investors one page that shows where each service request is, so fewer people call to ask.",
    ),
    (
        "DEMO-00012",
        "measuring",
        "Distributor brokerage statements in plain words",
        "Rewrite brokerage statements so distributors can read their earnings without calling support.",
    ),
    (
        "DEMO-00008",
        "in_garage",
        "Fill nominee details from CKYC when a folio is created",
        "Pre-fill nominee details from CKYC at folio creation, so investors do not fill the same form twice.",
    ),
    (
        "DEMO-00015",
        "handover",
        "One page where distributors can see why an SIP registration is stuck",
        "Show distributors on IRIS why an SIP registration is stuck, before they need to call.",
    ),
    (
        "DEMO-00017",
        "in_fix_track",
        "One checklist for change-of-bank requests at service centres",
        "Give service centres one checklist for change-of-bank requests, with the IFSC and a cancelled cheque, so "
        "fewer requests are sent back.",
    ),
    (
        "DEMO-00016",
        "picked",
        "Check transmission documents before they reach the service centre",
        "Check transmission documents online first, so cases reach the service centre complete.",
    ),
    (
        "DEMO-00020",
        "in_cluster",
        "A shorter call-back form for redemption queries",
        "Cut the call-back form for redemption queries to three fields, so service centres answer faster.",
    ),
    (
        "DEMO-00021",
        "ready_for_scoring",
        "Show distributors on IRIS when an SIP is paused",
        "Tell distributors on IRIS when an investor pauses an SIP, so they can follow up in time.",
    ),
    (
        "DEMO-00022",
        "reviewed",
        "Fill the bank name from the IFSC on change-of-bank forms",
        "Fill the bank name from the IFSC code on change-of-bank forms, so investors type less and make fewer errors.",
    ),
    (
        "DEMO-00023",
        "reviewed",
        "Manual checks on SIP mandates delay registration",
        "Operations re-check every SIP mandate by hand because bank fields are often missing at capture, which delays registration.",
    ),
    (
        "DEMO-00020",
        "parked",
        "A weekend helpdesk for distributors",
        "Open a small distributor helpdesk on Saturdays for urgent transaction questions.",
    ),
]
HISTORY = {
    "reviewed": ["reviewed"],
    "in_cluster": ["reviewed", "grouped"],
    "ready_for_scoring": ["reviewed", "grouped", "assessed"],
    "picked": ["reviewed", "assessed", "picked"],
    "handover": ["reviewed", "assessed", "picked", "handover"],
    "in_garage": ["reviewed", "assessed", "picked", "building"],
    "in_fix_track": ["reviewed", "assessed", "picked", "in_fix_track"],
    "shipped": ["reviewed", "picked", "building", "shipped"],
    "measuring": ["reviewed", "picked", "building", "shipped"],
    "closed": ["reviewed", "picked", "building", "shipped", "closed"],
    "parked": ["reviewed", "parked"],
}

# The employee's own ideas, through the real flows: (text, one line, summary, what happens)
OWN: list[tuple[str, str, str, str]] = [
    ("Ops re-check every SIP mandate by hand because bank fields are often missing at capture, and it delays "
     "registration for investors and distributors.",
     "Catch missing bank fields on SIP mandates at capture",
     "Check SIP mandate bank fields at capture, so operations stop re-checking them by hand.", "crew"),
    ("Physical redemption forms are couriered to service centres with no tracking, so we cannot tell investors "
     "where their form is when they call.",
     "Track couriered redemption forms",
     "Track couriered redemption forms, so service centres can tell investors where their form is.", "desk"),
    ("Investors miss SIP instalments when their mandate expires because nobody reminds them a month before.",
     "Remind investors before an SIP mandate expires",
     "Remind investors a month before their SIP mandate expires, so fewer instalments are missed.", "question"),
    ("Distributors get rejection codes on transactions that they cannot understand, so they call the contact "
     "centre for every rejection.",
     "Plain words for transaction rejection reasons",
     "Explain transaction rejections to distributors in plain words, so they stop calling to ask.", "decide"),
]  # fmt: skip

# The Ones: (employee ID, number, tier, way in, title or idea owner's idea, brief, measures)
ONES: list[dict[str, Any]] = [
    {"emp": "DEMO-00009", "number": 1, "tier": 4, "way_in": "founding",
     "title": "Bank details checked before every payout",
     "brief": "It worked: fewer redemption payouts fail, and more investors are paid on the first attempt.",
     "measures": {"time": {"value": 120, "unit": "hours a month"},
                  "money": {"value": 450000, "unit": "rupees a year", "finance_confirmed": True},
                  "effort": {"value": 800, "unit": "errors avoided a month"},
                  "scale": {"value": 30000, "unit": "transactions a month"}}},
    {"emp": "DEMO-00010", "number": 2, "tier": 3, "way_in": "founding",
     "title": "One status page for investor service requests",
     "brief": "It worked: investors can see where their request is without calling.",
     "measures": {"time": {"value": 60, "unit": "hours a month"}, "scale": {"value": 12000, "unit": "investors"}}},
    {"emp": "DEMO-00011", "number": 3, "tier": 2, "way_in": "founding",
     "title": "Dividend reconciliation checks for every AMC",
     "brief": "It worked: AMCs stopped reprocessing dividend files by hand.",
     "measures": {"effort": {"value": 300, "unit": "corrections avoided a month"}}},
    {"emp": "DEMO-00012", "number": 4, "tier": 5, "way_in": "founding",
     "title": "Brokerage statements in plain words",
     "brief": "It worked: distributors read their earnings without calling support.",
     "measures": {"effort": {"value": 300, "unit": "calls avoided a month"},
                  "scale": {"value": 5000, "unit": "distributors"}}},
    {"emp": "DEMO-00013", "number": 5, "tier": 1, "way_in": "founding",
     "title": "Faster change-of-address for investors",
     "brief": "It worked: address changes go through in a day instead of a week.",
     "measures": {"time": {"value": 40, "unit": "hours a month"}}},
    {"emp": "DEMO-00014", "number": 6, "tier": 2, "way_in": "founding",
     "title": "Service centre queue on one screen",
     "brief": "It worked: service centre staff see every AMC's queue in one place.", "measures": {}},
    {"emp": "DEMO-00008", "number": 17, "tier": 1, "way_in": "accepted_idea",
     "brief": "If this works: new investors never fill a nominee form twice.", "measures": {}},
    {"emp": "DEMO-00015", "number": 18, "tier": 1, "way_in": "accepted_idea",
     "brief": "If this works: distributors stop calling to ask why an SIP is stuck.", "measures": {}},
    {"emp": "DEMO-00016", "number": 19, "tier": 3, "way_in": "accepted_idea",
     "brief": "If this works: transmission cases arrive complete, and families wait less.", "measures": {}},
    {"emp": "DEMO-00019", "number": 20, "tier": 1, "way_in": "sponsored",
     "title": "Weekly reconciliation of unclaimed redemptions",
     "brief": "If this works: unclaimed redemptions are traced and paid sooner.", "measures": {},
     "inducted_days_ago": 400},
]  # fmt: skip

# Deliveries (§4.8 to §4.11), one in each state: (idea owner, idea stage, track, state, owner, sponsor, delivery PM,
# metric, baseline, target, unit, product, days since the sponsor approved, extra). Numbers are made up.
CHECKED = {"working_group_formed": True, "baseline_captured": True, "build_slot_confirmed": True,
           "dev_slot_confirmed": True}  # fmt: skip
DELIVERIES: list[dict[str, Any]] = [
    {"idea": ("DEMO-00015", "handover"), "track": "build", "state": "awaiting_sponsor", "owner": "DEMO-00008",
     "sponsor": "DEMO-00005", "pm": "DEMO-00013", "metric": "Calls a month asking why an SIP is stuck",
     "baseline": 900, "target": 300, "unit": "calls a month", "product": "iris"},
    {"idea": ("DEMO-00008", "in_garage"), "track": "build", "state": "in_delivery", "owner": "DEMO-00008",
     "sponsor": "DEMO-00005", "pm": "DEMO-00013", "metric": "Minutes to open a folio with a nominee",
     "baseline": 12, "target": 4, "unit": "minutes per case", "product": "other", "approved_days_ago": 18,
     "phase": "05-build"},
    {"idea": ("DEMO-00012", "measuring"), "track": "build", "state": "shipped", "owner": "DEMO-00012",
     "sponsor": "DEMO-00005", "pm": "DEMO-00013", "metric": "Calls a month about brokerage statements",
     "baseline": 1200, "target": 400, "unit": "calls a month", "product": "iris", "approved_days_ago": 150,
     "shipped_days_ago": 92, "writeup": "submitted",
     "results": {"day_30": ({"metric_actual": 700, "effort": {"value": 500, "unit": "calls avoided a month"}}, True),
                 "day_90": ({"metric_actual": 380, "effort": {"value": 820, "unit": "calls avoided a month"},
                             "scale": {"value": 5000, "unit": "distributors"}}, False)}},
    {"idea": ("DEMO-00010", "closed"), "track": "build", "state": "closed", "owner": "DEMO-00010",
     "sponsor": "DEMO-00005", "pm": "DEMO-00013", "metric": "Calls a month asking where a service request is",
     "baseline": 5000, "target": 2000, "unit": "calls a month", "product": "other", "approved_days_ago": 220,
     "shipped_days_ago": 100,
     "results": {"day_30": ({"metric_actual": 3100}, True),
                 "day_90": ({"metric_actual": 1800, "time": {"value": 60, "unit": "hours a month"},
                             "money": {"value": 600000, "unit": "rupees a year"}}, True)}},
    {"idea": ("DEMO-00017", "in_fix_track"), "track": "fix", "state": "in_delivery", "owner": "DEMO-00017",
     "sponsor": "DEMO-00005", "pm": None, "metric": "Change-of-bank requests sent back a month",
     "baseline": 220, "target": 50, "unit": "cases a month", "product": "other", "approved_days_ago": 21,
     "objective": "Every change-of-bank request is complete the first time it reaches a service centre",
     "milestones": [("Agree the checklist with two service centres", -12, "done"),
                    ("Train service centre staff on the checklist", -3, "open"),
                    ("Put the checklist on the intranet and the forms page", 10, "open")]},
]  # fmt: skip

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}


def _dev_only() -> None:
    """Dev only, twice over: the process says APP_ENV=dev, and the database it would write to is the local dev
    stack's (a local host and the `ideas` database), never a UAT or production server (Ones review)."""
    settings = get_settings()
    if settings.app_env != "dev":
        raise SystemExit("make demo is for the local dev stack only (APP_ENV=dev); nothing was changed")
    url = urlparse(settings.database_url)
    if (url.hostname or "") not in LOCAL_DB_HOSTS or url.path.lstrip("/") != "ideas":
        raise SystemExit("make demo writes only to the local dev database; nothing was changed")


# --- People ------------------------------------------------------------------------------------------------------


def _email(name: str) -> str:
    first, *rest = name.lower().split()
    return f"{first}.{'.'.join(rest) or 'demo'}.demo@kfintech.example"


def _people(conn: Conn) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    version = get_settings().privacy_notice_version
    for emp, name, lob, roles, _label, consent in PEOPLE:
        row = conn.execute(
            "INSERT INTO users (emp_id_hash, name, email, source, lob_id) VALUES (%s, %s, %s, 'sign_in', %s) "
            "RETURNING id",
            (emp_id_hash(emp), name, _email(name), lob),
        ).fetchone()
        assert row is not None
        uid = str(row["id"])
        code = assign_contributor_code(conn, uid, emp)
        for role in roles:
            conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (uid, role))
        conn.execute("INSERT INTO comms_prefs (user_id, public_name_consent) VALUES (%s, %s)", (uid, consent))
        conn.execute(
            "INSERT INTO privacy_acceptances (user_id, notice_version) VALUES (%s, %s)", (uid, version)
        )
        out[emp] = {"id": uid, "code": code, "name": name}
    manager = out[MANAGER]["id"]
    for emp in TEAM:
        conn.execute("UPDATE users SET manager_user_id = %s WHERE id = %s", (manager, out[emp]["id"]))
    return out


# --- Ideas -------------------------------------------------------------------------------------------------------


def _canvas(one_line: str, summary: str) -> dict[str, Any]:
    example = json.loads(CANVAS_EXAMPLE.read_text(encoding="utf-8"))
    canvas: dict[str, Any] = dict(example["output"])
    canvas.update(
        {"one_line": one_line, "details": summary, "neutral_summary": summary, "original_text": summary}
    )
    canvas["demo"] = True
    canvas["generated_by"] = "canvas-assist/0.1.0"
    return canvas


def _idea(conn: Conn, owner: dict[str, str], stage: str, one_line: str, summary: str) -> str:
    n = conn.execute("SELECT next_number('IDEA', %s) AS n", (str(YEAR),)).fetchone()
    assert n is not None
    idea_id, sub_id = f"IDEA-{YEAR}-{int(n['n']):06d}", f"SUB-{YEAR}-{int(n['n']):06d}"
    canvas = _canvas(one_line, summary)
    system = canvas["system"]
    conn.execute(
        "INSERT INTO ideas (idea_id, submission_id, stage, capture_mode, kind, category, play, basis, strength, scope, "
        "area_ids, lobs, systems, roles_affected, visibility, contributor_code, language, canvas, submitted_at) "
        "VALUES (%s,%s,%s,'quick',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'org',%s,'en',%s, %s)",
        (idea_id, sub_id, stage, canvas["kind"], canvas["value"]["category"], canvas["value"]["play"],
         canvas["value"]["basis"], 4, system["scope"], system["areas"], system["lobs"], system["systems"],
         system["roles_affected"], owner["code"], Jsonb(canvas), NOW - dt.timedelta(days=20)),
    )  # fmt: skip
    history = [{"event": "submitted", "note": ""}] + [
        {"event": e, "note": ""} for e in HISTORY.get(stage, [])
    ]
    conn.execute(
        "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.submitted', %s, %s, %s)",
        (idea_id, owner["code"], Jsonb({"idea_id": idea_id, "history": history})),
    )
    return idea_id


def _wait_for_repo(conn: Conn, timeout_s: float = 180.0) -> None:
    """The worker container's repo writer and indexer pick the demo ideas up; wait until both are done."""
    repo = Path(get_settings().company_repo_path)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pending = conn.execute("SELECT count(*) AS n FROM outbox WHERE committed_at IS NULL").fetchone()
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        state = conn.execute("SELECT last_commit FROM index_state").fetchone()
        if pending and int(pending["n"]) == 0 and state and state["last_commit"] == head:
            return
        time.sleep(2)
    raise SystemExit("the repo writer or the indexer did not catch up in time; is `make up` running?")


def _own_ideas(conn: Conn, kavya: dict[str, str], reviewer: str) -> dict[str, str]:
    """The employee's ideas through the real scan and review flows (fake model route)."""
    from review import service as review
    from scan import pipeline, save
    from scan.confirm import confirm

    out: dict[str, str] = {}
    for text, one_line, summary, what in OWN:
        idea_uuid = str(uuid.uuid4())
        n = conn.execute("SELECT next_number('IDEA', %s) AS n", (str(YEAR),)).fetchone()
        assert n is not None
        idea_id = f"IDEA-{YEAR}-{int(n['n']):06d}"
        raw: dict[str, Any] = {
            "mode": "quick", "kind": None, "one_line": one_line, "details": text,
            "who": {"segments": ["kfin_teams", "investors"], "frequency_or_reach": "", "today_alternative": ""},
            "value": {"category": "cost_saving", "play": None,
                      "estimate": {"hours_saved_per_month": None, "note": ""}, "basis": None},
            "ecosystem": {"solved_elsewhere": None, "references": [], "our_advantage": ""},
            "solution": {"approach": "", "needs": "", "risks": ""},
            "visibility": "org", "visibility_reason": "",
            "declarations": {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True},
            "provenance": {},
        }  # fmt: skip
        conn.execute(
            "INSERT INTO ideas (id, idea_id, submission_id, stage, capture_mode, contributor_code, raw_encrypted, "
            "submitted_at) VALUES (%s, %s, %s, 'scanning', 'quick', %s, %s, now())",
            (
                idea_uuid,
                idea_id,
                f"SUB-{YEAR}-{int(n['n']):06d}",
                kavya["code"],
                encrypt_json(raw, idea_uuid),
            ),
        )
        if pipeline.run(conn, idea_uuid) != "done":
            raise SystemExit(f"the scan did not finish for the demo idea ({what}); is the stack up?")
        confirm(conn, idea_uuid, idea_id, {})
        out[what] = idea_id
        if what == "crew":
            continue  # left on Find your crew, waiting for her choice
        save.save(conn, idea_uuid, kavya["code"], {"choice": "new"})
        item = conn.execute("SELECT id FROM review_items WHERE ref_id = %s", (idea_id,)).fetchone()
        assert item is not None
        if what == "question":
            review.act(conn, int(item["id"]), reviewer,
                       {"action": "ask", "question": "Which AMCs see the most expired mandates each month?"})  # fmt: skip
        elif what == "decide":
            review.act(conn, int(item["id"]), reviewer, {"action": "decide"})
        # The fake model route writes the same sample summary for every idea: give each its own, once the flows
        # that write the card have run.
        conn.execute(
            "UPDATE ideas SET canvas = canvas || %s WHERE id = %s AND canvas IS NOT NULL",
            (Jsonb({"one_line": one_line, "neutral_summary": summary, "demo": True}), idea_uuid),
        )
    # A draft she has not shared yet.
    draft = {"mode": "full", "one_line": "Let investors update their nominee themselves", "details": "",
             "visibility": "org", "provenance": {}}  # fmt: skip
    did = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO ideas (id, stage, capture_mode, contributor_code, raw_encrypted) "
        "VALUES (%s, 'draft', 'full', %s, %s)",
        (did, kavya["code"], encrypt_json(draft, did)),
    )
    return out


# --- The Ones ----------------------------------------------------------------------------------------------------


def _ones(conn: Conn, p: dict[str, dict[str, str]], idea_of: dict[str, str]) -> dict[str, int]:
    one_ids: dict[str, int] = {}
    for o in ONES:
        person = p[o["emp"]]
        n = conn.execute("SELECT next_number('ONE', '') AS n").fetchone()
        assert n is not None
        inducted = NOW - dt.timedelta(
            days=int(o.get("inducted_days_ago", 25 if o["way_in"] != "founding" else 360))
        )
        measures = {k: {**v, "demo": True} for k, v in o["measures"].items()}
        row = conn.execute(
            "INSERT INTO ones (induction_no, user_id, number, way_in, idea_id, tier, measures, inducted_at, swap_until, "
            "brief_approved_at, announced_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (n["n"], person["id"], o["number"], o["way_in"], idea_of.get(o["emp"]) if o["way_in"] == "accepted_idea" else None,
             o["tier"], Jsonb(measures), inducted, inducted + dt.timedelta(days=30), inducted, inducted),
        ).fetchone()  # fmt: skip
        assert row is not None
        oid = int(row["id"])
        one_ids[o["emp"]] = oid
        conn.execute(
            "UPDATE ones SET title_encrypted = %s, brief_encrypted = %s WHERE id = %s",
            (seal(o.get("title"), f"one:{oid}:title"), seal(o["brief"], f"one:{oid}:brief"), oid),
        )
        conn.execute(
            "INSERT INTO one_number_history (one_id, number, how, from_at) VALUES (%s, %s, 'allocated', %s)",
            (oid, o["number"], inducted),
        )
    # A One who retired: No. 7 rests for six months.
    n = conn.execute("SELECT next_number('ONE', '') AS n").fetchone()
    assert n is not None
    retired_at = NOW - dt.timedelta(days=20)
    row = conn.execute(
        "INSERT INTO ones (induction_no, user_id, number, status, way_in, tier, inducted_at, swap_until, retired_at) "
        "VALUES (%s, %s, NULL, 'retired', 'sponsored', 2, %s, %s, %s) RETURNING id",
        (
            n["n"],
            p["DEMO-00018"]["id"],
            NOW - dt.timedelta(days=380),
            NOW - dt.timedelta(days=350),
            retired_at,
        ),
    ).fetchone()
    assert row is not None
    conn.execute(
        "INSERT INTO one_number_history (one_id, number, how, from_at, to_at, rests_until) VALUES (%s, 7, 'allocated', %s, %s, %s)",
        (row["id"], NOW - dt.timedelta(days=380), retired_at, retired_at + dt.timedelta(days=183)),
    )
    # The system's counter carries on after the demo's numbers.
    conn.execute(
        "INSERT INTO id_counters (kind, period, last_value) VALUES ('ONE-NO', '', 20) "
        "ON CONFLICT (kind, period) DO UPDATE SET last_value = 20"
    )
    return one_ids


def _proposal(conn: Conn, **f: Any) -> int:
    reason, text = f.pop("reason", None), f.pop("text", None)
    cols = ", ".join(f)
    marks = ", ".join(["%s"] * len(f))
    row = conn.execute(
        f"INSERT INTO one_proposals ({cols}) VALUES ({marks}) RETURNING id",  # noqa: S608 (fixed column names)
        tuple(f.values()),
    ).fetchone()
    assert row is not None
    pid = int(row["id"])
    conn.execute(
        "UPDATE one_proposals SET reason_encrypted = %s, text_encrypted = %s WHERE id = %s",
        (seal(reason, f"one_proposal:{pid}:reason"), seal(text, f"one_proposal:{pid}:text"), pid),
    )
    return pid


def _message(conn: Conn, pid: int, author: str, role: str, text: str) -> None:
    row = conn.execute(
        "INSERT INTO one_messages (proposal_id, author_user_id, author_role) VALUES (%s, %s, %s) RETURNING id",
        (pid, author, role),
    ).fetchone()
    assert row is not None
    conn.execute(
        "UPDATE one_messages SET text_encrypted = %s WHERE id = %s",
        (seal(text, f"one_message:{row['id']}"), row["id"]),
    )


def _console(conn: Conn, p: dict[str, dict[str, str]], one_ids: dict[str, int]) -> None:
    member, chair, ceo, admin = (p[e]["id"] for e in ("DEMO-00003", "DEMO-00004", "DEMO-00005", "DEMO-00006"))
    yesterday = (NOW - dt.timedelta(days=1)).date()

    # No. 17's tier-up has just been carried out: her glow-up plays when she signs in.
    ananya = one_ids["DEMO-00008"]
    pid = _proposal(conn, kind="tier_up", one_id=ananya, subject_user_id=p["DEMO-00008"]["id"], tier_to=2,
                    proposed_by=member, state="carried_out", approval="chair", decided_by=chair, decided_at=NOW,
                    carried_out_by=admin, carried_out_at=NOW,
                    reason="The CKYC pre-fill pilot is live in two AMCs and working")  # fmt: skip
    _message(conn, pid, member, "committee",
             "Your pilot showed every AMC what good looks like. Glow suits you. Thank you, Ananya.")  # fmt: skip
    _message(conn, pid, ceo, "ceo", "This is exactly what the 1% Club is for. Keep going.")
    conn.execute(
        "INSERT INTO one_message_invites (proposal_id, user_id, invited_by) VALUES (%s, %s, %s)",
        (pid, p["DEMO-00001"]["id"], member),
    )
    _message(
        conn,
        pid,
        p["DEMO-00001"]["id"],
        "peer",
        "Proud to work next to you. The nominee form was everyone's headache.",
    )
    conn.execute("UPDATE ones SET tier = 2 WHERE id = %s", (ananya,))
    conn.execute(
        "INSERT INTO one_glow_ups (one_id, proposal_id, tier_from, tier_to) VALUES (%s, %s, 1, 2)",
        (ananya, pid),
    )
    emit(
        conn,
        "ones.tier_changed",
        {"current_owner_ids": [p["DEMO-00008"]["id"]], "one_id": ananya, "proposal_id": pid},
    )

    # Waiting for the chair: a sponsored inclusion.
    _proposal(conn, kind="include", subject_user_id=p["DEMO-00017"]["id"], way_in="sponsored", proposed_by=member,
              text="Rebuilt the dividend reconciliation checks every AMC now uses",
              reason="His checks cut reprocessing for every AMC this year.")  # fmt: skip
    # Waiting for approval: No. 18's tier-up, with the committee's message already written.
    farhan = one_ids["DEMO-00015"]
    tid = _proposal(conn, kind="tier_up", one_id=farhan, subject_user_id=p["DEMO-00015"]["id"], tier_to=2,
                    proposed_by=member, reason="The SIP status page is live for all IRIS distributors")  # fmt: skip
    _message(conn, tid, member, "committee", "Distributors noticed within a week. Well done, Farhan.")
    conn.execute(
        "INSERT INTO one_message_invites (proposal_id, user_id, invited_by) VALUES (%s, %s, %s)",
        (tid, p["DEMO-00001"]["id"], member),
    )
    emit(conn, "ones.message_invited", {"current_owner_ids": [p["DEMO-00001"]["id"]], "proposal_id": tid})
    # Approved at a meeting, waiting for the admin member: No. 20's removal after a lapse.
    _proposal(conn, kind="remove", one_id=one_ids["DEMO-00019"], subject_user_id=p["DEMO-00019"]["id"],
              proposed_by=member, state="approved", approval="majority", meeting_on=yesterday, decided_by=chair,
              decided_at=NOW, reason="Membership lapsed after twelve months without a delivery, mentoring or a new idea.")  # fmt: skip

    # No. 17's Showcase brief, partly filled.
    parts = {"idea": "", "proposed_impact": "", "progress": "",
             "impact_so_far": "Live in two AMCs; nominee mismatches down in both.",
             "timelines": "All AMCs by March; the CKYC call is ready for the rest.",
             "team": "", "help": "A sponsor in operations to agree the rollout order with AMCs."}  # fmt: skip
    conn.execute(
        "INSERT INTO one_showcase_briefs (one_id, parts_encrypted) VALUES (%s, %s)",
        (ananya, seal_json(parts, f"one:{ananya}:showcase")),
    )


# --- Delivery, lenses and learning ----------------------------------------------------------------------------------


def _deliveries(conn: Conn, p: dict[str, dict[str, str]], idea_at: dict[tuple[str, str], str]) -> None:
    """One delivery in each state, written straight to the database (the ideas are already at their stage)."""
    from delivery.service import target_met

    for f in DELIVERIES:
        idea = idea_at[f["idea"]]
        approved = NOW - dt.timedelta(days=int(f.get("approved_days_ago", 0)))
        shipped = NOW - dt.timedelta(days=int(f["shipped_days_ago"])) if "shipped_days_ago" in f else None
        pack = {"product": f["product"], "feature_type": "kfintech-product", "compliance_tier": "standard",
                "unit": f["unit"], "baseline": f["baseline"], "target": f["target"], "spend": "CC-OPS/2026",
                "checklist": dict(CHECKED), "demo": True}  # fmt: skip
        started = f["state"] != "awaiting_sponsor"
        build = f["track"] != "fix"
        row = conn.execute(
            "INSERT INTO deliveries (subject_type, subject_id, track, state, owner_user_id, sponsor_user_id, "
            "pm_user_id, pack, sponsor_approved_by, sponsor_approved_at, slug, link_state, phase, gate_status, "
            "phase_updated_at, shipped_at, closed_at, outcome, created_by, created_at) VALUES ('idea', %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (idea, f["track"], f["state"], p[f["owner"]]["id"], p[f["sponsor"]]["id"],
             p[f["pm"]]["id"] if f["pm"] else None, Jsonb(pack),
             p[f["sponsor"]]["id"] if started else None, approved if started else None, idea.lower(),
             "manual" if started and build else "none",
             (f.get("phase") or ("shipped" if shipped else None)) if build and started else None,
             "clear" if build and started else None, approved if started else None, shipped,
             shipped + dt.timedelta(days=91) if shipped and f["state"] == "closed" else None,
             "target_met" if f["state"] == "closed" else None, p["DEMO-00003"]["id"],
             approved - dt.timedelta(days=5)),
        ).fetchone()  # fmt: skip
        assert row is not None
        did = int(row["id"])
        conn.execute(
            "UPDATE deliveries SET metric_encrypted = %s, objective_encrypted = %s WHERE id = %s",
            (seal(f["metric"], f"delivery:{did}:metric"),
             seal(f["objective"], f"delivery:{did}:objective") if f.get("objective") else None, did),
        )  # fmt: skip
        for title, due_in, status in f.get("milestones", []):
            m = conn.execute(
                "INSERT INTO delivery_milestones (delivery_id, title_encrypted, owner_user_id, due_on, status, "
                "done_at) VALUES (%s, '\\x00', %s, %s, %s, %s) RETURNING id",
                (did, p[f["owner"]]["id"], (NOW + dt.timedelta(days=due_in)).date(), status,
                 NOW + dt.timedelta(days=due_in) if status == "done" else None),
            ).fetchone()  # fmt: skip
            assert m is not None
            conn.execute(
                "UPDATE delivery_milestones SET title_encrypted = %s WHERE id = %s",
                (seal(title, f"milestone:{m['id']}"), m["id"]),
            )
        if shipped is None:
            continue
        for mark, days in (("day_30", 30), ("day_90", 90)):
            given = f.get("results", {}).get(mark)
            results: dict[str, Any] | None = None
            if given:
                results = {**given[0], "demo": True}
                results["target_met"] = target_met(f["baseline"], f["target"], results["metric_actual"])
                results["actual_vs_target"] = round(results["metric_actual"] / f["target"], 3)
            filled = shipped + dt.timedelta(days=days) if given else None
            confirmed = filled + dt.timedelta(days=1) if filled is not None and given and given[1] else None
            conn.execute(
                "INSERT INTO delivery_measurements (delivery_id, mark, due_at, results, filled_by, filled_at, "
                "confirmed_by, confirmed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (did, mark, shipped + dt.timedelta(days=days), Jsonb(results or {}),
                 p[f["owner"]]["id"] if given else None, filled,
                 p[f["sponsor"]]["id"] if confirmed else None, confirmed),
            )  # fmt: skip
        if f.get("writeup"):  # a write-up waiting for the sponsor (BLD-133), synthetic text
            w = conn.execute(
                "INSERT INTO solution_writeups (delivery_id, state, parts_encrypted, drafted_by, submitted_by, "
                "submitted_at) VALUES (%s, %s, '\\x00', %s, %s, %s) RETURNING id",
                (did, f["writeup"], p[f["owner"]]["id"], p[f["owner"]]["id"], NOW - dt.timedelta(days=1)),
            ).fetchone()
            assert w is not None
            conn.execute(
                "UPDATE solution_writeups SET parts_encrypted = %s WHERE id = %s",
                (seal_json(DEMO_WRITEUP, f"writeup:{w['id']}"), w["id"]),
            )


DEMO_WRITEUP = {
    "title": "Brokerage statement self-service for distributors",
    "what_it_does": "Distributors download their brokerage statement for any month themselves, so they stop calling "
    "the service desk to ask for it.",
    "where_it_runs": "IRIS, for every empanelled distributor; run by the distributor services team.",
    "result": "Calls about brokerage statements fell from about 1,200 a month to under 400 in ninety days.",
    "how_to_adopt": "Talk to the distributor services lead. It needs the statement file feed and about two weeks "
    "of set-up for a new product line.",
}

CHAIR_NOTE = (
    "The ideas that stood out this month named who feels the problem, and how often. Start there, then say what "
    "changes on the day it works."
)


def _ember_and_points(conn: Conn, p: dict[str, dict[str, str]]) -> None:
    """The Ember (BLD-128): last month's issue in the archive and this month's draft with the chair's note, waiting
    for the chair to approve it before an admin sends it (BLD-134), so the archive and Write The Ember are not
    empty. Then the private points (BLD-130) from everything above."""
    from ember.service import IST, as_sent, build
    from points.ledger import sync

    chair, admin = p["DEMO-00004"]["id"], p["DEMO-00006"]["id"]
    local = NOW.astimezone(IST)
    this_month = dt.date(local.year, local.month, 1)
    last_month = dt.date(local.year - (local.month == 1), (local.month - 2) % 12 + 1, 1)
    with conn.transaction():
        if not conn.execute("SELECT 1 FROM ember_issues WHERE month = %s", (last_month,)).fetchone():
            # Ones by number only: names follow live consent.
            content = as_sent(build(conn, last_month), CHAIR_NOTE)
            conn.execute(
                "INSERT INTO ember_issues (month, state, content, created_by, sent_by, sent_at, chair_note_by) "
                "VALUES (%s, 'sent', %s, %s, %s, %s, %s)",
                (last_month, Jsonb(content), admin, admin, NOW - dt.timedelta(days=9), chair),
            )
        if not conn.execute("SELECT 1 FROM ember_issues WHERE month = %s", (this_month,)).fetchone():
            row = conn.execute(
                "INSERT INTO ember_issues (month, created_by, chair_note_by) VALUES (%s, %s, %s) RETURNING id",
                (this_month, admin, chair),
            ).fetchone()
            assert row is not None
            conn.execute(
                "UPDATE ember_issues SET chair_note_encrypted = %s WHERE id = %s",
                (seal(CHAIR_NOTE, f"ember:{row['id']}:note"), row["id"]),
            )
    sync(conn)


def _insights(conn: Conn) -> None:
    """The lenses and the learning reports, so their screens are not empty. Counts and rates only."""
    import lenses
    from learning import proposals, reports

    lenses.build(conn)
    reports.autonomy(conn, NOW)
    reports.drift(conn, NOW)
    reports.canvas(conn, NOW)
    proposals.glossary(conn, NOW, NOW.strftime("%G-W%V"))


# --- Load and reset ------------------------------------------------------------------------------------------------


def _demo_user_ids(conn: Conn) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM users WHERE emp_id_hash = ANY(%s)", ([emp_id_hash(e) for e, *_ in PEOPLE],)
    ).fetchall()
    return [str(r["id"]) for r in rows]


def remove(conn: Conn) -> None:
    """The demo's people and everything that is theirs: their Ones records, proposals, messages, deliveries and
    ideas. Nobody else's rows are touched (Ones review). The demo ideas' files leave the company repo through the
    repo writer (`idea.demo_removed`), so the indexer drops their chunks and Find your crew has no orphans."""
    from repo_writer.render import repo_path_for

    with conn.transaction():
        users = _demo_user_ids(conn)
        if not users:
            return
        one_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM ones WHERE user_id = ANY(%s::uuid[])", (users,)).fetchall()]  # fmt: skip
        proposals = [r["id"] for r in conn.execute(
            "SELECT id FROM one_proposals WHERE subject_user_id = ANY(%s::uuid[]) OR proposed_by = ANY(%s::uuid[]) "
            "OR decided_by = ANY(%s::uuid[]) OR carried_out_by = ANY(%s::uuid[]) OR one_id = ANY(%s)",
            (users, users, users, users, one_ids)).fetchall()]  # fmt: skip
        conn.execute("DELETE FROM one_messages WHERE proposal_id = ANY(%s) OR author_user_id = ANY(%s::uuid[])",
                     (proposals, users))  # fmt: skip
        conn.execute(
            "DELETE FROM one_message_invites WHERE proposal_id = ANY(%s) OR user_id = ANY(%s::uuid[]) "
            "OR invited_by = ANY(%s::uuid[])",
            (proposals, users, users),
        )
        conn.execute(
            "DELETE FROM one_glow_ups WHERE one_id = ANY(%s) OR proposal_id = ANY(%s)", (one_ids, proposals)
        )
        conn.execute("DELETE FROM one_proposals WHERE id = ANY(%s)", (proposals,))
        conn.execute(
            "DELETE FROM one_awards WHERE one_id = ANY(%s) OR awarded_by = ANY(%s::uuid[])", (one_ids, users)
        )
        conn.execute("DELETE FROM one_legend_numbers WHERE one_id = ANY(%s)", (one_ids,))
        conn.execute("DELETE FROM one_showcase_briefs WHERE one_id = ANY(%s)", (one_ids,))
        conn.execute("DELETE FROM ones WHERE id = ANY(%s)", (one_ids,))  # number history goes with them
        if not conn.execute("SELECT 1 FROM ones LIMIT 1").fetchone():
            # Counters restart only when no One is left at all, so nobody else's numbers can collide.
            conn.execute(
                "UPDATE id_counters SET last_value = 0 WHERE kind IN ('ONE', 'ONE-NO') AND period = ''"
            )
        codes = [r["contributor_code"] for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = ANY(%s::uuid[])", (users,)).fetchall()]  # fmt: skip
        idea_rows = conn.execute(
            "SELECT idea_id, submitted_at FROM ideas WHERE contributor_code = ANY(%s) AND idea_id IS NOT NULL",
            (codes,),
        ).fetchall()
        ideas = [r["idea_id"] for r in idea_rows]
        if _has_table(conn, "deliveries"):
            # Every delivery a demo person is named on or signed: owner, sponsor, PM, creator, approver, a
            # milestone's owner, or whoever filled or confirmed a result. Milestones and results go with them.
            conn.execute(
                "DELETE FROM deliveries d WHERE (d.subject_type = 'idea' AND d.subject_id = ANY(%s)) "
                "OR d.owner_user_id = ANY(%s::uuid[]) OR d.sponsor_user_id = ANY(%s::uuid[]) "
                "OR d.pm_user_id = ANY(%s::uuid[]) OR d.created_by = ANY(%s::uuid[]) "
                "OR d.sponsor_approved_by = ANY(%s::uuid[]) OR d.submitted_by = ANY(%s::uuid[]) "
                "OR d.completed_by = ANY(%s::uuid[]) "
                "OR EXISTS (SELECT 1 FROM delivery_milestones m WHERE m.delivery_id = d.id "
                "AND m.owner_user_id = ANY(%s::uuid[])) "
                "OR EXISTS (SELECT 1 FROM delivery_measurements m WHERE m.delivery_id = d.id AND (m.filled_by = ANY(%s::uuid[]) "
                "OR m.confirmed_by = ANY(%s::uuid[]) OR m.finance_confirmed_by = ANY(%s::uuid[])))",
                (ideas, *([users] * 11)),
            )
        if _has_table(conn, "ember_issues"):
            # Issues a demo person drafted, wrote the note for or sent (BLD-128).
            conn.execute(
                "DELETE FROM ember_issues WHERE created_by = ANY(%s::uuid[]) OR sent_by = ANY(%s::uuid[]) "
                "OR chair_note_by = ANY(%s::uuid[])",
                (users, users, users),
            )
        if _has_table(conn, "learning_proposals"):
            # Proposals drawn from demo ideas, or decided by a demo person; the next run proposes again if due.
            conn.execute(
                "DELETE FROM learning_proposals WHERE decided_by = ANY(%s::uuid[]) "
                "OR (payload -> 'idea_ids') ?| %s::text[]",
                (users, ideas),
            )
        items = [r["id"] for r in conn.execute(
            "SELECT id FROM review_items WHERE ref_id = ANY(%s)", (ideas,)).fetchall()]  # fmt: skip
        conn.execute("DELETE FROM corrections WHERE review_item_id = ANY(%s)", (items,))
        conn.execute(
            "DELETE FROM sla_timers WHERE entity_type = 'review_item' AND entity_id = ANY(%s)",
            ([str(i) for i in items],),
        )
        conn.execute("DELETE FROM review_items WHERE id = ANY(%s)", (items,))
        conn.execute(
            "DELETE FROM idea_links WHERE idea_id = ANY(%s) OR contributor_code = ANY(%s)", (ideas, codes)
        )
        conn.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (ideas,))
        # Events still waiting for these ideas would block the writer once the rows are gone; then each idea's
        # file is removed through the writer itself.
        conn.execute("DELETE FROM outbox WHERE committed_at IS NULL AND aggregate_id = ANY(%s)", (ideas,))
        for r in idea_rows:
            if r["submitted_at"] is None:
                continue
            conn.execute(
                "INSERT INTO outbox (event_type, aggregate_id, actor, payload) VALUES ('idea.demo_removed', %s, "
                "'process:demo', %s)",
                (r["idea_id"], Jsonb({"demo": True, "path": repo_path_for(r["idea_id"], r["submitted_at"])})),
            )
        conn.execute("DELETE FROM ideas WHERE contributor_code = ANY(%s)", (codes,))
        conn.execute(
            "UPDATE users SET manager_user_id = NULL WHERE manager_user_id = ANY(%s::uuid[])", (users,)
        )
        conn.execute("DELETE FROM role_grants WHERE user_id = ANY(%s::uuid[])", (users,))
        conn.execute("DELETE FROM users WHERE id = ANY(%s::uuid[])", (users,))


def _has_table(conn: Conn, name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) AS t", (f"public.{name}",)).fetchone()
    return bool(row and row["t"])


def load(conn: Conn) -> None:
    with conn.transaction():
        people = _people(conn)
        idea_of: dict[str, str] = {}
        idea_at: dict[tuple[str, str], str] = {}
        for owner, stage, one_line, summary in IDEAS:
            idea_id = _idea(conn, people[owner], stage, one_line, summary)
            idea_at[(owner, stage)] = idea_id
            if stage in ("in_garage", "handover", "picked"):
                idea_of[owner] = idea_id
    _wait_for_repo(conn)
    _own_ideas(conn, people["DEMO-00001"], people["DEMO-00002"]["id"])
    with conn.transaction():
        one_ids = _ones(conn, people, idea_of)
        _console(conn, people, one_ids)
        for emp in ("DEMO-00009", "DEMO-00015"):
            emit(conn, "ones.inducted", {"current_owner_ids": [people[emp]["id"]], "one_id": one_ids[emp]})
        _deliveries(conn, people, idea_at)
    _insights(conn)
    if _has_table(conn, "ember_issues"):
        _ember_and_points(conn, people)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="remove the demo's own rows and files and load it again"
    )
    args = parser.parse_args(argv)
    _dev_only()
    with connect(autocommit=True) as conn:
        loaded = bool(_demo_user_ids(conn))
        if loaded and not args.reset:
            print("demo: already loaded (make demo-reset starts it fresh)")
            return 0
        remove(conn)
        load(conn)
    print("demo: loaded. Sign in at http://localhost:3000 with these employee IDs as the username:")
    for emp, name, _lob, _roles, label, _consent in PEOPLE:
        if label:
            print(f"  {emp}  {name:20} {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
