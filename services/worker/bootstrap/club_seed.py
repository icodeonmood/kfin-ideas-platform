"""The 1% Club synthetic seed for the handoff pack's tables (BLD-E006): `make demo DEMO_SET=1pc` (or
`python -m bootstrap.club_seed`). Dev only: refused unless APP_ENV=dev and the database is the local `ideas` one.

Everything here is invented and clearly synthetic. People are new names, not the pack's demo cast (P-PRODUCT.cast
stays out of every database) and not the old demo's; employee IDs are `SYN-10001`… (above the synthetic HR
directory's range), emails `….1pc@kfintech.example`. Customer details in the words are made-up values that only
look like a folio, PAN or phone number; they are masked as the pack masks them and the unmasked words sit in the
worker-only `idea_words_sealed` (DEC-103).

What it gives every screen of the pack something to show:
- ideas in every stored status (draft, checking, with the review desk, picked, being built, shipped, not now,
  not picked, withdrawn, merged; "needs you" is the sharer's view of an open question set), drafts at different
  steps and one archived, each with its messages, six parts, hidden details and sorting;
- the review desk's four tabs: to review, waiting on the sharer (one overdue), answered, decided;
- decisions inside the Ones Committee's window (one extended), expired ones, and a reversal;
- a team-up request waiting on a lead (with an idea brought along), approved and declined ones, three drafts' merge
  requests waiting on one lead (each in her Inbox, one per answer J-SIMILAR/6 walks), an accepted one, and a desk
  merge inside its window;
- two ideas on one reviewer's desk, opened, that list each other as similar, ready for a desk merge (J-REVIEW/M3);
- a draft that arrived by email, its detail hidden, with its "kept your draft" Inbox item (J-RESUME/5, 6);
- crews, passes on the crew deck, conversations with events, questions, answers and messages;
- every Inbox kind; Ones with numbers, tiers 1 to 7, briefs and posts with likes; build teams, measurements;
- one One whose tier rose with the moment not yet shown (J-ONE step 6).

It does not write `sla_timers`: the old SLA tick reads a rule for every running timer and would stop on the new
clock kinds. Clock dates live on the rows themselves (decide_by, due_at, closes_at, return_at, team_by).

`--remove` takes out the seed's people and everything that is theirs; `--reset` removes and loads again. Nobody
else's rows are touched. The old demo (`make demo`) is separate and can be loaded beside it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.crypto import encrypt_json
from core.db import Conn, connect
from identity.codes import assign_contributor_code, emp_id_hash
from onepc.context import seal_text, sealed_context
from pii import vault

IST = ZoneInfo("Asia/Kolkata")
DOMAIN = "kfintech.example"
LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}
DECLARATION = "1pc-2026-11"

# (employee ID, name, area, city, line of business, roles, tier, name on the Wall, label for the walkthrough)
PEOPLE: list[tuple[str, str, str, str, str, tuple[str, ...], int, bool, str]] = [
    ("SYN-10001", "Tanvi Deshmukh", "Investor service", "Hyderabad", "LOB-mf", (), 2, True, "Sharer with ideas at every stage"),
    ("SYN-10002", "Harish Venkatesan", "Operations", "Hyderabad", "LOB-product-strategy", ("reviewer",), 3, True, "Review desk"),
    ("SYN-10003", "Lavanya Krishnan", "Technology", "Chennai", "LOB-product-strategy", ("reviewer",), 1, True, "Review desk"),
    ("SYN-10004", "Manoj Agarwal", "Compliance", "Mumbai", "LOB-compliance-legal", ("committee",), 4, True, "Ones Committee"),
    ("SYN-10005", "Shalini Bose", "Distributor experience", "Kolkata", "LOB-sales", ("committee",), 3, True, "Ones Committee"),
    ("SYN-10006", "Kunal Malhotra", "Technology", "Hyderabad", "LOB-technology", ("admin",), 1, True, "Admin"),
    ("SYN-10007", "Hyderabad Office Screen", "Operations", "Hyderabad", "LOB-admin", ("display",), 1, False, "Office display"),
    ("SYN-10008", "Gopal Iyengar", "Technology", "Bengaluru", "LOB-technology", (), 7, True, "Build team lead, One No. 15"),
    ("SYN-10009", "Rekha Saxena", "Investor service", "Hyderabad", "LOB-mf", (), 4, True, "Lead with a team-up request waiting"),
    ("SYN-10010", "Varun Chopra", "Operations", "Mumbai", "LOB-shared-operations", (), 3, True, "One No. 11, shipped fix"),
    ("SYN-10011", "Pallavi Joshi", "Distributor services", "Mumbai", "LOB-sales", (), 1, True, ""),
    ("SYN-10012", "Siddharth Menezes", "Technology", "Bengaluru", "LOB-digital-platforms", (), 1, True, "New One, number still open"),
    ("SYN-10013", "Aparna Hegde", "Corporate registry", "Hyderabad", "LOB-corporate-registry", (), 6, True, "Founding One, being built"),
    ("SYN-10014", "Naveen Reddy", "Investor service", "Hyderabad", "LOB-mf", (), 1, True, ""),
    ("SYN-10015", "Zoya Mirza", "Sales", "Mumbai", "LOB-sales", (), 2, True, ""),
    ("SYN-10016", "Bhavesh Patel", "Operations", "Jaipur", "LOB-shared-operations", (), 1, True, ""),
    ("SYN-10017", "Charulata Sen", "Compliance", "Kolkata", "LOB-compliance-legal", (), 2, False, "Hides name on the Wall"),
    ("SYN-10018", "Dinesh Kamath", "Distributor experience", "Bengaluru", "LOB-digital-platforms", (), 5, True, "One No. 8, tier just rose"),
    ("SYN-10019", "Esha Talwar", "New business", "Mumbai", "LOB-product-strategy", (), 1, True, ""),
    ("SYN-10020", "Faisal Ansari", "Operations", "Hyderabad", "LOB-mf", (), 1, True, ""),
    ("SYN-10021", "Geetanjali Dutta", "Investor service", "Kolkata", "LOB-mf", (), 2, True, ""),
    ("SYN-10022", "Hemant Rawat", "Technology", "Jaipur", "LOB-technology", (), 1, True, ""),
    ("SYN-10023", "Indira Natarajan", "Corporate registry", "Chennai", "LOB-corporate-registry", (), 2, True, ""),
    ("SYN-10024", "Jatin Khurana", "Sales", "Jaipur", "LOB-sales", (), 1, True, ""),
]  # fmt: skip
EMP = {name.split()[0].lower(): emp for emp, name, *_ in PEOPLE}  # "tanvi" -> "SYN-10001"

MASK_LABEL = {"folio": "Folio", "pan": "PAN", "phone": "Phone", "email": "Email", "account": "Account",
              "aadhaar": "Aadhaar", "name": "Name"}  # fmt: skip
VAULT_TYPE = {"folio": "FOLIO_NUMBER", "pan": "PAN", "phone": "PHONE", "account": "ACCOUNT_NUMBER"}


@dataclass
class Spec:
    """One idea. `words` are the sharer's own words; a `{folio}`-style marker is a made-up customer detail, typed
    as `hidden[...]` gives it, masked everywhere but in the sharer's own copy."""

    owner: str
    status: str
    kind: str
    title: str
    summary: str
    area: str
    words: list[str]
    often: str | None = None
    affects: list[str] = field(default_factory=lambda: ["Investors"])
    brings: list[str] = field(default_factory=lambda: ["saves_time"])
    hidden: dict[str, tuple[str, str]] = field(default_factory=dict)  # marker -> (kind, made-up value)
    shown: dict[str, str] = field(default_factory=dict)  # marker -> show reason
    shared_days: float | None = None  # days ago; None for a draft
    opened_days: float | None = None
    reviewer: str | None = None
    decided: tuple[str, float, str] | None = None  # (choice, days ago, reviewer key)
    team_days: float | None = None  # build team chosen, days ago
    shipped_days: float | None = None
    step: str | None = None
    saved_days: float = 0.1
    archived: bool = False
    withdrawn_days: float | None = None
    fix: dict[str, Any] | None = None
    worth: dict[str, Any] | None = None
    helpers: list[str] = field(default_factory=list)
    channel: str = "web"
    via: str = "typed"
    origin: str | None = None  # an email arrival's subject (L-DRAFT.channels), arrived as the draft was made


IDEAS: dict[str, Spec] = {
    # Tanvi's ideas: one at every stage the pack draws.
    "T1": Spec("tanvi", "draft", "problem", "Walk-in KYC updates queue twice at the branch",
               "Investors who walk in to update KYC wait in the general queue, then again at the KYC desk. "
               "Many leave before the second queue.",
               "Investor service",
               ["Walk-in investors who come to update KYC stand in the general queue and then again at the KYC "
                "desk. Yesterday one investor with {folio} left after forty minutes. This happens most mornings."],
               often="Most mornings at one branch", hidden={"{folio}": ("folio", "7700012389")},
               step="check:3", saved_days=2.2, via="voice"),
    "T2": Spec("tanvi", "draft", "problem", "SIP failure SMS gives no reason",
               "When a SIP debit fails, the SMS says only that it failed. Investors call the branch to ask why.",
               "Investor service",
               ["The SMS for a failed SIP debit only says it failed. Investors call us to ask why and we look "
                "it up each time. About twenty calls a day come in for this."],
               often="About 20 calls a day", step="check:6", saved_days=0.4),
    "T3": Spec("tanvi", "draft", "business_idea", "Nominee reminders for older folios",
               "Older folios without a nominee could get a gentle reminder with a one-step form.",
               "Investor service",
               ["Older folios often have no nominee. A reminder with a one-step form could fix many of them."],
               step="tell", saved_days=36, archived=True),
    "T4": Spec("tanvi", "checking", "problem", "Change of address forms come back for one missing tick",
               "Change of address forms are returned when one consent box is not ticked. The investor has to "
               "come back to the branch.",
               "Operations", ["Change of address forms come back to us when one consent box is not ticked. "
                              "The investor has to visit the branch again for one tick."],
               often="A few times a week", shared_days=0.01),
    "T5": Spec("tanvi", "with_review_desk", "problem", "Redemption status is not visible to the branch",
               "Branch staff cannot see where a redemption request is. They raise an internal mail for each "
               "investor who asks.",
               "Investor service",
               ["Branch staff cannot see where a redemption request is. For each investor who asks we raise a "
                "mail and wait. Ref {ref} is the latest one I raised."],
               often="About 15 requests a day", hidden={"{ref}": ("account", "SR40021187")},
               shown={"{ref}": "internal_reference"}, shared_days=1.0, brings=["saves_time", "saves_cost"],
               fix={"how": "Show the redemption status from the transaction system on the branch screen, read only.",
                    "needs": "Read access to the status table", "solved_already": "partly",
                    "solved_note": "One region has a report, updated once a day", "basis": "own_research",
                    "risks": "Status codes need plain words"},
               worth={"hours_low": 70, "hours_high": 150}, helpers=["Someone from tech", "Data or reports"]),
    "T6": Spec("tanvi", "with_review_desk", "problem", "PAN mismatch holds new folios for days",
               "New folios wait when the PAN name and the form name differ by a letter. Nobody tells the investor.",
               "Operations",
               ["New folios are held when the PAN name and the form name differ by one letter. An investor "
                "with {pan} waited six days last week and nobody told them why."],
               often="About 30 folios a week", hidden={"{pan}": ("pan", "AAAPZ9999Z")},
               shared_days=2.5, opened_days=1.6, reviewer="harish", brings=["saves_time"]),
    "T7": Spec("tanvi", "picked", "fix", "Plain words for transaction rejection codes",
               "Rejection letters show codes like R07 that investors cannot read. A short plain sentence per "
               "code would cut the calls that follow.",
               "Investor service",
               ["Rejection letters show only a code like R07. Investors cannot read it and call us. A short plain "
                "sentence for each code would stop most of these calls."],
               often="About 40 calls a day across branches", shared_days=9, opened_days=8, reviewer="harish",
               decided=("pick", 5, "harish"), brings=["saves_time", "saves_cost"],
               fix={"how": "Keep a table of codes with one plain sentence each and print it on the letter.",
                    "needs": "Sign-off from compliance on the wording", "solved_already": "no",
                    "basis": "conversation", "risks": "Codes change when the exchange changes them"},
               worth={"hours_low": 120, "hours_high": 200, "cost_low": 40000}),
    "T8": Spec("tanvi", "not_now", "business_idea", "A paid express change-of-bank service",
               "Investors in a hurry could pay a small fee for a same-day change of bank, done at the branch.",
               "New business", ["Some investors would pay a small fee to change their bank the same day."],
               shared_days=48, opened_days=46, reviewer="lavanya", decided=("not_now", 42, "lavanya"),
               brings=["earns_revenue"], affects=["Investors", "KFin teams"]),
    "T9": Spec("tanvi", "picked", "problem", "Dividend bank mandate reminders go out too late",
               "The reminder to update a bank mandate goes out after the dividend record date, so payouts fail.",
               "Operations",
               ["The reminder to update the bank mandate goes out after the record date. Payouts fail and the "
                "investor calls us."],
               often="Every dividend season", shared_days=13, opened_days=12, reviewer="lavanya",
               decided=("not_picked", 6, "lavanya"), brings=["saves_cost"]),
    "T10": Spec("tanvi", "withdrawn", "problem", "Token slips at the branch run out by noon",
                "The token printer at the branch runs out of slips by noon on busy days.",
                "Operations", ["Our token printer runs out of slips by noon on busy days."],
                shared_days=1.5, withdrawn_days=1.0),
    "T11": Spec("tanvi", "merged", "problem", "Investors call twice about failed SIP debits",
                "Investors call once when the SIP fails and again when the next one is due, because nobody "
                "said what to fix.",
                "Investor service",
                ["Investors call once when the SIP fails and again before the next one, because nobody said "
                 "what to fix."],
                shared_days=4, opened_days=3, reviewer="lavanya"),
    # Other people's ideas.
    "R1": Spec("rekha", "with_review_desk", "problem", "Investors get no reason when a SIP debit fails",
               "A failed SIP debit reaches the investor without a reason. Branches spend time looking it up.",
               "Investor service",
               ["When a SIP debit fails the investor gets no reason. We look it up by hand for every call."],
               often="Daily at every branch", shared_days=6, opened_days=5, reviewer="lavanya",
               helpers=["Someone in operations", "Someone from tech"]),
    "R2": Spec("rekha", "with_review_desk", "problem", "One clear message after a failed SIP debit",
               "Send one clear message after a failed SIP debit: what failed, why and what to do next.",
               "Investor service", ["After a failed SIP debit, one clear message would save two calls."],
               shared_days=5, opened_days=3.2, reviewer="lavanya"),
    "V1": Spec("varun", "shipped", "fix", "Flag likely-wrong bank details before a payout",
               "Check bank details against past payouts before a redemption is paid, so fewer payouts bounce.",
               "Operations", ["Payouts bounce when bank details are wrong. A check before payout would stop most."],
               shared_days=110, opened_days=108, reviewer="harish", decided=("pick", 104, "harish"),
               team_days=95, shipped_days=40, brings=["saves_cost", "saves_time"]),
    "S1": Spec("siddharth", "shipped", "fix", "Auto-fill pin code details on the online form",
               "Fill city and state from the pin code on the online form, so fewer forms come back.",
               "Technology", ["Online forms come back with a wrong city for the pin code."],
               shared_days=170, opened_days=168, reviewer="lavanya", decided=("pick", 165, "lavanya"),
               team_days=150, shipped_days=100),
    "D1": Spec("dinesh", "shipped", "fix", "Brokerage statements distributors can read",
               "Rewrite brokerage statements in plain words, so distributors stop calling support to read them.",
               "Distributor experience", ["Distributors call support to understand their brokerage statement."],
               shared_days=300, opened_days=298, reviewer="harish", decided=("pick", 290, "harish"),
               team_days=270, shipped_days=200, affects=["Distributors"], brings=["saves_time"]),
    "I1": Spec("indira", "shipped", "fix", "One checklist for share transfer requests",
               "A single checklist for share transfer requests at the service centre.",
               "Corporate registry", ["Share transfer requests come back for missing papers."],
               shared_days=140, opened_days=139, reviewer="harish", decided=("pick", 135, "harish"),
               team_days=120, shipped_days=45, affects=["Investors", "KFin teams"]),
    "A1": Spec("aparna", "being_built", "fix", "Pre-fill nominee details from CKYC",
               "Fill nominee details from CKYC when a folio is created, so investors do not fill them twice.",
               "Corporate registry", ["Investors fill nominee details twice when CKYC already has them."],
               shared_days=30, opened_days=29, reviewer="harish", decided=("pick", 20, "harish"), team_days=12),
    "H1": Spec("hemant", "being_built", "fix", "Retry failed mandate registrations overnight",
               "Retry failed mandate registrations overnight instead of asking the distributor to resubmit.",
               "Technology", ["Mandate registrations that fail on a timeout are resubmitted by hand."],
               shared_days=60, opened_days=58, reviewer="lavanya", decided=("pick", 45, "lavanya"), team_days=30,
               affects=["Distributors"]),
    "P1": Spec("pallavi", "with_review_desk", "problem", "Distributors re-send the same empanelment papers",
               "Distributors are asked for empanelment papers they already sent, because the check list is "
               "kept in two places.",
               "Distributor services", ["Distributors send the same empanelment papers two or three times."],
               shared_days=3, affects=["Distributors"]),
    "Z1": Spec("zoya", "with_review_desk", "business_idea", "A paid portfolio review for distributors",
               "Distributors could buy a quarterly portfolio review report for their clients.",
               "Sales", ["Distributors ask for a quarterly portfolio review they could share with clients."],
               shared_days=7, opened_days=6, reviewer="harish", affects=["Distributors"], brings=["earns_revenue"]),
    "B1": Spec("bhavesh", "with_review_desk", "problem", "Courier returns are logged on paper",
               "Returned couriers are logged in a register, so nobody can search them.",
               "Operations", ["Returned couriers go into a paper register that nobody can search."],
               shared_days=5.5, opened_days=4.5, reviewer="lavanya"),
    "C1": Spec("charulata", "picked", "problem", "Two teams check the same FATCA declarations",
               "FATCA declarations are checked by two teams one after the other.",
               "Compliance", ["Two teams check the same FATCA declaration, one after the other."],
               shared_days=16, opened_days=15, reviewer="harish", decided=("pick", 10, "harish"),
               affects=["KFin teams"], brings=["saves_time"]),
    "E1": Spec("esha", "checking", "business_idea", "Sell plain-language fund factsheets to AMCs",
               "AMCs could buy plain-language versions of their fund factsheets for first-time investors.",
               "New business", ["AMCs could buy plain-language factsheets for first-time investors."],
               shared_days=0.02, brings=["earns_revenue"], affects=["Investors"]),
    "F1": Spec("faisal", "not_picked", "problem", "Separate queue for senior citizens at the branch",
               "A separate queue for senior citizens on pension days.",
               "Operations", ["Senior citizens wait in the same queue as everyone on pension days."],
               shared_days=8, opened_days=7, reviewer="harish", decided=("not_picked", 3, "harish")),
    "G1": Spec("geetanjali", "not_now", "problem", "Investors cannot download old account statements",
               "Statements older than three years cannot be downloaded online.",
               "Investor service", ["Older statements cannot be downloaded online, so investors write in."],
               shared_days=7, opened_days=6, reviewer="lavanya", decided=("not_now", 2, "lavanya")),
    "J1": Spec("jatin", "picked", "business_idea", "Co-branded investor webinars with distributors",
               "Run co-branded investor webinars with large distributors.",
               "Sales", ["Large distributors would co-host investor webinars with us."],
               shared_days=45, opened_days=44, reviewer="harish", decided=("pick", 38, "harish"),
               affects=["Distributors", "Investors"], brings=["earns_revenue"]),
    "N1": Spec("naveen", "merged", "problem", "Rejection codes confuse investors at the counter",
               "Investors at the counter cannot read rejection codes on their letters.",
               "Investor service", ["Investors bring rejection letters to the counter and ask what R07 means."],
               step="check:6", saved_days=7),
    # J-REVIEW/M3 (L-MERGE.desk): two sharers, one problem, both opened by Lavanya, each listing the other.
    "F2": Spec("faisal", "with_review_desk", "problem", "Change of bank waits for a cancelled cheque by post",
               "Investors who change their bank must post a cancelled cheque. The request waits until the cheque "
               "reaches us.",
               "Operations",
               ["Investors who change their bank have to post us a cancelled cheque. The request waits a week or "
                "more until it arrives, and the investor calls to ask why."],
               often="About 25 requests a week", shared_days=4.5, opened_days=3.0, reviewer="lavanya"),
    "J2": Spec("jatin", "with_review_desk", "problem", "Clients wait a week for a bank change to go through",
               "A client who changes their bank waits for a posted cheque to reach us. Distributors take the calls "
               "meanwhile.",
               "Sales",
               ["My distributors say their clients wait a week to change their bank, because the cancelled cheque "
                "goes by post. The distributor takes the calls while they wait."],
               often="Every week, across my distributors", shared_days=3.5, opened_days=2.0, reviewer="lavanya",
               affects=["Distributors", "Investors"]),
    # J-SIMILAR/6b and /6c (L-MERGE.request/6, 7): drafts whose merge requests wait on Rekha, as T2's does.
    "N2": Spec("naveen", "draft", "problem", "Branch staff see no reason when a SIP debit bounces",
               "When an investor asks why a SIP debit bounced, the branch has no reason to give. Staff raise a mail "
               "each time.",
               "Investor service",
               ["Investors come to the counter to ask why their SIP debit bounced. We have no reason on our screen, "
                "so we raise a mail and ask them to come back."],
               often="Several times a day", step="check:6", saved_days=0.3),
    "G2": Spec("geetanjali", "draft", "problem", "Failed SIP debit notes show only a bank code",
               "The note for a failed SIP debit shows only a bank code. Investors cannot tell what to fix.",
               "Investor service",
               ["The note an investor gets for a failed SIP debit shows only a bank code. They cannot tell whether "
                "to add money or change the mandate, so they call us."],
               often="About ten calls a week at our branch", step="check:6", saved_days=0.5),
    # J-RESUME/5 and /6 (L-DRAFT.channels): a forwarded email that landed as a draft, one detail hidden, not opened.
    "I2": Spec("indira", "draft", "problem", "Returned dividend letters go back to old addresses",
               "Dividend letters that come back are posted again to the same old address. Nobody checks the "
               "address first.",
               "Corporate registry",
               ["Forwarding this thread. Dividend letters that come back are posted again to the same old address. "
                "The one for {folio} came back last week for the third time. Could we check the address with the "
                "depository before we post again?"],
               often="Every dividend season", affects=["Investors", "KFin teams"], brings=["saves_cost"],
               hidden={"{folio}": ("folio", "4400076512")}, step="tell", saved_days=0.15, channel="email",
               via="email", origin="Fwd: Dividend letter returned again"),
}  # fmt: skip
# J2 was written after F2 was shared, so it found F2 while drafting (L-SIMILAR.rules/4, 5); F2 got J2 when J2 was
# shared (L-SIMILAR.rules/6). Nobody asked to merge: the desk can (L-MERGE.desk/1), F2 leading as shared first.
DESK_PAIR = ("F2", "J2", "Close match: a bank change waits for a cheque by post")


def _dev_only() -> None:
    settings = get_settings()
    if settings.app_env != "dev":
        raise SystemExit(
            "the 1% Club seed is for the local dev stack only (APP_ENV=dev); nothing was changed"
        )
    url = urlparse(settings.database_url)
    if (url.hostname or "") not in LOCAL_DB_HOSTS or url.path.lstrip("/") != "ideas":
        raise SystemExit("the 1% Club seed writes only to the local dev database; nothing was changed")


def _ago(days: float, now: dt.datetime) -> dt.datetime:
    return now - dt.timedelta(days=days)


def _working_days_after(start: dt.datetime, n: int) -> dt.datetime:
    """Weekends only; the real clock uses the holiday calendar. Good enough for synthetic dates."""
    day = start
    while n:
        day += dt.timedelta(days=1)
        if day.astimezone(IST).weekday() < 5:
            n -= 1
    return day


def _email(name: str) -> str:
    first, *rest = name.lower().split()
    return f"{first}.{'.'.join(rest) or 'seed'}.1pc@{DOMAIN}"


# --- People --------------------------------------------------------------------------------------------------------


def _people(conn: Conn) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    version = get_settings().privacy_notice_version
    for emp, name, area, city, lob, roles, tier, on_wall, _label in PEOPLE:
        row = conn.execute(
            "INSERT INTO users (emp_id_hash, name, email, source, lob_id, location, first_name, area, tier) "
            "VALUES (%s, %s, %s, 'sign_in', %s, %s, %s, %s, %s) RETURNING id",
            (emp_id_hash(emp), name, _email(name), lob, city, name.split()[0], area, tier),
        ).fetchone()
        assert row is not None
        uid = str(row["id"])
        code = assign_contributor_code(conn, uid, emp)
        for role in ("employee", *roles):
            conn.execute("INSERT INTO role_grants (user_id, role) VALUES (%s, %s)", (uid, role))
        conn.execute(
            "INSERT INTO comms_prefs (user_id, public_name_consent, teams, email, reminders) "
            "VALUES (%s, %s, %s, true, %s)",
            (uid, on_wall, emp not in (EMP["bhavesh"], EMP["zoya"]), emp != EMP["jatin"]),
        )
        conn.execute(
            "INSERT INTO person_settings (user_id, show_name_on_wall, sidebar_folded) VALUES (%s, %s, %s)",
            (uid, on_wall, emp == EMP["harish"]),
        )
        if version:
            conn.execute(
                "INSERT INTO privacy_acceptances (user_id, notice_version) VALUES (%s, %s)", (uid, version)
            )
        out[name.split()[0].lower()] = {"id": uid, "code": code, "name": name, "city": city, "emp": emp}
    return out


# --- Ideas ---------------------------------------------------------------------------------------------------------


@dataclass
class Made:
    uuid: str
    ref: str | None
    spec: Spec
    messages: list[str]


def _mask(kind: str, value: str) -> str:
    return f"{MASK_LABEL[kind]} ••••{value[-2:]}"


def _status_path(s: Spec, now: dt.datetime) -> list[tuple[str, dt.datetime]]:
    created = _ago((s.shared_days or s.saved_days) + 0.05, now)
    path = [("draft", created)]
    if s.shared_days is None:
        return path
    shared = _ago(s.shared_days, now)
    path.append(("checking", shared))
    if s.status == "checking":
        return path
    path.append(("with_review_desk", shared + dt.timedelta(minutes=3)))
    if s.withdrawn_days is not None:
        path.append(("withdrawn", _ago(s.withdrawn_days, now)))
    if s.decided:
        choice, days, _ = s.decided
        path.append(({"pick": "picked"}.get(choice, choice), _ago(days, now)))
    if s.team_days is not None:
        path.append(("being_built", _ago(s.team_days, now)))
    if s.shipped_days is not None:
        path.append(("shipped", _ago(s.shipped_days, now)))
    return path


def _idea(conn: Conn, key: str, s: Spec, p: dict[str, dict[str, str]], now: dt.datetime) -> Made:
    owner = p[s.owner]
    idea_uuid = str(uuid.uuid4())
    shared = _ago(s.shared_days, now) if s.shared_days is not None else None
    ref = None
    if shared is not None:
        row = conn.execute("SELECT next_idea_ref(%s) AS ref", (shared,)).fetchone()
        assert row is not None
        ref = str(row["ref"])
    opened = _ago(s.opened_days, now) if s.opened_days is not None else None
    reviewer = p[s.reviewer]["id"] if s.reviewer else None
    confirmed = shared is not None or (s.step or "").startswith("check:6")
    sources = {f: {"source": "confirmed" if confirmed else "suggested", "why": "From your words"}
               for f in ("affects", "kind", "area", "brings")}  # fmt: skip
    if key == "T5":
        sources["area"] = {"source": "changed", "why": "Your call"}
    path = _status_path(s, now)
    text_chars = sum(len(w) for w in s.words)
    # An email or Teams arrival has no device (L-DRAFT.channels); otherwise where it was last saved.
    device = None if s.channel in ("email", "teams") else ("phone" if s.via == "voice" else "laptop")
    conn.execute(
        "INSERT INTO ideas (id, idea_id, contributor_code, status, kind, title, summary, often, city, affects, area, "
        "brings, sorting_sources, sorting_confirmed_at, helper_picks, channel, step, saved_at, saved_device, "
        "saved_device_id, char_count, archived_at, shared_at, share_seconds, declaration_version, declared_at, "
        "edit_closes_at, withdrawn_at, decide_by, reviewer_id, opened_at, opened_by, created_at, language) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, 'en')",
        (
            idea_uuid, ref, owner["code"], s.status, s.kind, s.title, s.summary, s.often,
            owner["city"] if shared else None, s.affects, s.area, s.brings, Jsonb(sources),
            shared if confirmed else None, s.helpers, s.channel,
            s.step if shared is None else None, _ago(s.saved_days, now) if shared is None else shared,
            device, f"seed-device-{s.owner}" if device else None,
            text_chars, _ago(s.saved_days, now) if s.archived else None, shared,
            40 + (len(s.title) % 50) if shared else None, DECLARATION if shared else None, shared,
            (min(opened, shared + dt.timedelta(days=3)) if opened else shared + dt.timedelta(days=3)) if shared else None,
            _ago(s.withdrawn_days, now) if s.withdrawn_days is not None else None,
            _working_days_after(shared, 5) if shared else None, reviewer, opened, reviewer if opened else None,
            path[0][1],
        ),
    )  # fmt: skip
    if s.origin is not None:  # sealed as draft intake seals it: masked subject, the note on top, when it came
        origin = {"received_at": path[0][1].isoformat(), "subject": s.origin, "note": s.origin}
        conn.execute(
            "UPDATE ideas SET origin_encrypted = %s WHERE id = %s",
            (
                seal_text("ideas", "origin_encrypted", idea_uuid, json.dumps(origin, ensure_ascii=False)),
                idea_uuid,
            ),
        )
    # The track's history at the real times (the trigger recorded "now").
    conn.execute("DELETE FROM idea_status_history WHERE idea_uuid = %s", (idea_uuid,))
    prev = None
    for status, at in path:
        conn.execute(
            "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, %s, %s, %s)",
            (idea_uuid, prev, status, at),
        )
        prev = status
    conn.execute("UPDATE ideas SET status_changed_at = %s WHERE id = %s", (path[-1][1], idea_uuid))

    scope = ref or f"DRAFT-{idea_uuid}"
    message_ids: list[str] = []
    for seq, own in enumerate(s.words, start=1):
        mid = str(uuid.uuid4())
        message_ids.append(mid)
        masked, spans, values = own, [], []
        for marker, (kind, value) in s.hidden.items():
            if marker not in own:
                continue
            start = own.replace(marker, value).index(value)
            spans.append({"start": start, "end": start + len(value), "kind": kind})
            values.append((marker, kind, value, start))
        own_text = own
        for marker, kind, value, _ in values:
            own_text = own_text.replace(marker, value)
            shown = marker in s.shown
            masked = masked.replace(marker, value if shown else _mask(kind, value))
        at = path[0][1] + dt.timedelta(minutes=seq)
        conn.execute(
            "INSERT INTO idea_messages (id, idea_uuid, seq, via, device, lang, text_encrypted, spans, char_count, "
            "created_at) VALUES (%s, %s, %s, %s, %s, 'en', %s, %s, %s, %s)",
            (mid, idea_uuid, seq, s.via, device,
             seal_text("idea_messages", "text_encrypted", mid, masked), Jsonb(spans), len(own_text), at),
        )  # fmt: skip
        if values:
            conn.execute(
                "INSERT INTO idea_words_sealed (idea_uuid, source, source_id, owner_user_id, text_encrypted) "
                "VALUES (%s, 'message', %s, %s, %s)",
                (idea_uuid, mid, owner["id"],
                 seal_text("idea_words_sealed", "text_encrypted", f"message:{mid}", own_text, vault=True)),
            )  # fmt: skip
        for marker, kind, value, start in values:
            tag = vault.assign(conn, scope, VAULT_TYPE[kind], value, subject_user_id=None)
            reason = s.shown.get(marker)
            conn.execute(
                "INSERT INTO hidden_details (idea_uuid, source, source_id, span_start, span_end, kind, masked, "
                "vault_tag, state, reason, shown_by, shown_at) VALUES (%s, 'message', %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s)",
                (idea_uuid, mid, start, start + len(value), kind, _mask(kind, value), tag,
                 "shown" if reason else "hidden", reason, owner["id"] if reason else None,
                 at + dt.timedelta(minutes=2) if reason else None),
            )  # fmt: skip

    # The six parts and the run that filled them (L-DRAFT.parts), with timings for the loader's means.
    run_id = str(uuid.uuid4())
    timings = {"title": 1900, "often": 1300, "who": 1100, "value": 1500, "area": 900, "similar": 2600}
    failed = key == "T1"  # one draft shows the failed-part state (C-DRAFT-LOADER.failure)
    conn.execute(
        "INSERT INTO draft_runs (id, idea_uuid, message_id, state, parts, part_ms, receipt, suggestions, ready, "
        "started_at, finished_at) VALUES (%s, %s, %s, 'done', %s, %s, %s, %s, true, %s, %s)",
        (run_id, idea_uuid, message_ids[-1], list(timings), Jsonb(timings),
         Jsonb([*(["Turned your email into a draft. Nothing has been sent."] if s.channel == "email" else []),
                "Wrote a title and a short summary from your words.",
                *(["Hid 1 personal detail from everyone but you."] if s.hidden else [])]),
         Jsonb(["Add what you already tried", "Say who feels it most"]), path[0][1], path[0][1] + dt.timedelta(seconds=3)),
    )  # fmt: skip
    parts: dict[str, Any] = {
        "title": {"title": s.title, "summary": s.summary},
        "often": s.often,
        "who": s.affects,
        "value": s.brings,
        "area": s.area,
        "similar": [],
    }
    for part, part_value in parts.items():
        filled: Any = part_value
        state = "filled"
        if failed and part == "often":
            state, filled = "failed", None
        elif key == "T5" and part == "area":
            state = "pinned"
        elif filled is None:
            state = "waiting"
        conn.execute(
            "INSERT INTO idea_parts (idea_uuid, key, state, value, why, source_quote, run_id, took_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (idea_uuid, part, state, Jsonb(filled) if filled is not None else None,
             "Because you mentioned it" if state == "filled" else None,
             s.words[0][:60].split("{")[0] if state == "filled" and part in ("title", "often") else None,
             run_id, timings[part]),
        )  # fmt: skip

    if s.fix:
        conn.execute(
            "INSERT INTO idea_fix (idea_uuid, how, needs, solved_already, solved_note, basis, risks) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (idea_uuid, s.fix["how"], s.fix.get("needs"), s.fix.get("solved_already"), s.fix.get("solved_note"),
             s.fix.get("basis"), s.fix.get("risks")),
        )  # fmt: skip
    if s.worth:
        conn.execute(
            "INSERT INTO idea_worth (idea_uuid, by_side, by_code, hours_low, hours_high, cost_low, at) "
            "VALUES (%s, 'sharer', %s, %s, %s, %s, %s)",
            (idea_uuid, owner["code"], s.worth.get("hours_low"), s.worth.get("hours_high"), s.worth.get("cost_low"),
             shared or path[0][1]),
        )  # fmt: skip
    if shared is not None:
        conn.execute(
            "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) "
            "VALUES (%s, %s, 'lead', 'shared', %s)",
            (idea_uuid, owner["code"], shared),
        )
        _event(conn, idea_uuid, "shared", shared, {})
        if s.status != "checking":
            _event(conn, idea_uuid, "checked_matched", shared + dt.timedelta(minutes=3),
                   {"hidden": len(s.hidden), "similar": 0})  # fmt: skip
        if opened is not None and reviewer:
            _event(conn, idea_uuid, "opened_by_desk", opened, {"reviewer_id": reviewer})
    return Made(idea_uuid, ref, s, message_ids)


def _event(conn: Conn, idea_uuid: str, event: str, at: dt.datetime, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO conversation_entries (idea_uuid, type, event, payload, at) VALUES (%s, 'event', %s, %s, %s)",
        (idea_uuid, event, Jsonb(payload), at),
    )


def _message(
    conn: Conn, idea_uuid: str, at: dt.datetime, text: str, *, code: str | None = None, user: str | None = None,
    mentions: list[str] | None = None,
) -> str:  # fmt: skip
    eid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO conversation_entries (id, idea_uuid, type, author_code, author_user_id, text_encrypted, "
        "mentions, at) VALUES (%s, %s, 'message', %s, %s, %s, %s, %s)",
        (eid, idea_uuid, code, user, seal_text("conversation_entries", "text_encrypted", eid, text),
         mentions or [], at),
    )  # fmt: skip
    return eid


# --- Review: questions, decisions, windows, a reversal, merges -------------------------------------------------------


def _questions(
    conn: Conn, made: Made, by: str, sharer_code: str, now: dt.datetime, *, state: str, sent_days: float | None,
    due_days: float | None, qs: list[tuple[str, str, bool, str | None, bool]],
) -> str:  # fmt: skip
    """qs: (part, question, suggested, answer or None, answer sent)."""
    sid = str(uuid.uuid4())
    sent = _ago(sent_days, now) if sent_days is not None else None
    due = now + dt.timedelta(days=due_days) if due_days is not None else None
    conn.execute(
        "INSERT INTO question_sets (id, idea_uuid, by_user_id, state, time_to_answer, sent_at, seen_at, due_at, "
        "answered_at, closed_at, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (sid, made.uuid, by, state, "3d" if state != "queued" else None, sent,
         sent + dt.timedelta(hours=2) if sent and state != "sent" else None, due,
         now - dt.timedelta(hours=1) if state == "answered" else None,
         _ago(5.2, now) if state == "closed" else None, sent or now),
    )  # fmt: skip
    for seq, (part, text, suggested, answer, answer_sent) in enumerate(qs, start=1):
        qid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO questions (id, set_id, seq, part, text_encrypted, suggested) VALUES (%s, %s, %s, %s, %s, %s)",
            (qid, sid, seq, part, seal_text("questions", "text_encrypted", qid, text), suggested),
        )
        if answer is not None:
            aid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO answers (id, question_id, by_code, text_encrypted, added_to, sent_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (aid, qid, sharer_code, seal_text("answers", "text_encrypted", aid, answer), part,
                 (sent or now) + dt.timedelta(hours=20) if answer_sent else None),
            )  # fmt: skip
    if sent is not None:
        conn.execute(
            "INSERT INTO conversation_entries (idea_uuid, type, question_set_id, at) VALUES (%s, 'questions', %s, %s)",
            (made.uuid, sid, sent),
        )
        if state in ("answered", "closed"):
            conn.execute(
                "INSERT INTO conversation_entries (idea_uuid, type, question_set_id, at) "
                "VALUES (%s, 'answers', %s, %s)",
                (made.uuid, sid, sent + dt.timedelta(hours=20)),
            )
    return sid


def _decide(
    conn: Conn, made: Made, p: dict[str, dict[str, str]], now: dt.datetime, reason: str, *,
    extended: int = 0, joined_with: str | None = None,
) -> tuple[str, str]:  # fmt: skip
    """The desk's decision and its committee window: open (30 days), extended, or expired."""
    choice, days, who = made.spec.decided or ("pick", 0.0, "harish")
    at = _ago(days, now)
    did = str(uuid.uuid4())
    return_at = at + dt.timedelta(days=91) if choice == "not_now" else None
    team_by = _working_days_after(at, 10) if choice == "pick" else None
    conn.execute(
        "INSERT INTO idea_decisions (id, idea_uuid, choice, reason_encrypted, by_user_id, at, joined_with, return_in, "
        "return_at, team_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (did, made.uuid, choice, seal_text("idea_decisions", "reason_encrypted", did, reason), p[who]["id"], at,
         joined_with, "3m" if choice == "not_now" else None, return_at, team_by),
    )  # fmt: skip
    closes = at + dt.timedelta(days=30 * (1 + extended))
    state = "expired" if closes < now else ("extended" if extended else "open")
    wid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO decision_windows (id, decision_id, state, opens_at, closes_at, max_closes_at, extended_times, "
        "last_extended_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (wid, did, state, at, closes, at + dt.timedelta(days=91), extended,
         p["shalini"]["id"] if extended else None),
    )  # fmt: skip
    _event(conn, made.uuid, "decided", at, {"decision_id": did})
    return did, wid


# --- Load ----------------------------------------------------------------------------------------------------------


def load(conn: Conn, now: dt.datetime | None = None) -> dict[str, Made]:
    """Write the whole seed in one transaction. Callers check it is not loaded yet (`remove` first)."""
    now = now or dt.datetime.now(dt.UTC)
    with conn.transaction():
        p = _people(conn)
        m = {key: _idea(conn, key, spec, p, now) for key, spec in IDEAS.items()}
        _review(conn, p, m, now)
        _crews(conn, p, m, now)
        _builds_and_impact(conn, p, m, now)
        _ones(conn, p, m, now)
        _inbox(conn, p, m, now)
        _wall_and_flags(conn, p, m, now)
    return m


def _review(conn: Conn, p: dict[str, dict[str, str]], m: dict[str, Made], now: dt.datetime) -> None:
    tanvi = p["tanvi"]
    # T5: an edit (2 versions) and a shown detail, still open to changes.
    for n, fields_ in ((1, ["title", "summary", "sorting"]), (2, ["fix"])):
        conn.execute(
            "INSERT INTO idea_versions (idea_uuid, n, changed_fields, by_code, snapshot_encrypted, at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (m["T5"].uuid, n, fields_, tanvi["code"],
             encrypt_json({"title": m["T5"].spec.title, "n": n}, sealed_context("idea_versions", "snapshot_encrypted", f"{m['T5'].uuid}:{n}")),
             _ago(1.0 - 0.1 * n, now)),
        )  # fmt: skip
    # T6: questions sent and seen, one answer saved but not sent (Needs you).
    _questions(conn, m["T6"], p["harish"]["id"], tanvi["code"], now, state="seen", sent_days=1.0, due_days=2.0,
               qs=[("often", "How many folios were held last month?", True, "About 120, mostly in one region.", False),
                   ("who", "Which teams see the hold first?", False, None, False),
                   ("evidence", "Is there a report that shows the holds?", True, None, False)])  # fmt: skip
    _message(conn, m["T6"].uuid, _ago(0.9, now), "I'll pull the count from the hold report and answer today.",
             code=tanvi["code"])  # fmt: skip
    # Z1: overdue. B1: answered, back with the desk. P1: a set the reviewer is still writing.
    _questions(conn, m["Z1"], p["harish"]["id"], p["zoya"]["code"], now, state="sent", sent_days=4.0, due_days=-1.0,
               qs=[("cost", "What would a distributor pay per report?", True, None, False),
                   ("who", "Which distributors have asked for it?", False, None, False)])  # fmt: skip
    _questions(conn, m["B1"], p["lavanya"]["id"], p["bhavesh"]["code"], now, state="answered", sent_days=3.0,
               due_days=0.5,
               qs=[("often", "How many couriers come back in a week?", True, "Around 60 a week.", True),
                   ("fix", "Would a scan at the counter be enough?", False, "Yes, one scan and a search box.", True)])  # fmt: skip
    _questions(conn, m["P1"], p["lavanya"]["id"], p["pallavi"]["code"], now, state="queued", sent_days=None,
               due_days=None, qs=[("who", "Which distributor segments re-send most?", True, None, False)])  # fmt: skip
    # T7: answered before the pick, set closed with the decision.
    _questions(conn, m["T7"], p["harish"]["id"], tanvi["code"], now, state="closed", sent_days=7.5, due_days=-4.5,
               qs=[("often", "Is the 40 a day across all branches?", False, "Yes, across the six largest branches.", True)])  # fmt: skip

    reasons = {
        "T7": "This is a clear problem with a simple fix. The wording needs compliance sign-off, which the team can get.",
        "T8": "The right idea, but fees need a pricing policy first. We will look again once that is in place.",
        "T9": "The mandate reminder dates are set by the exchange calendar, so we cannot move them on our own.",
        "V1": "Bounced payouts cost us every week. The check is small and uses data we already have.",
        "S1": "A small change on the form that removes a common reason for returned forms.",
        "D1": "Distributors will call less and trust the statements more.",
        "I1": "One checklist is cheap and stops most of the returns.",
        "A1": "CKYC already has the nominee details, so investors should not type them twice.",
        "H1": "Overnight retries remove a manual step for distributors and for us.",
        "C1": "The two checks look at the same fields. One team can do it with a shared checklist.",
        "F1": "Branches already run a priority counter on pension days. Your words carry on in that guidance.",
        "G1": "Older statements are moving to a new archive next quarter. We will look again after the move.",
        "J1": "Distributor webinars fit the plan for the coming quarter, and two distributors have asked.",
    }  # fmt: skip
    windows: dict[str, str] = {}
    for key, reason in reasons.items():
        _did, wid = _decide(conn, m[key], p, now, reason, extended=1 if key == "C1" else 0)
        windows[key] = wid
    # T9: the committee reversed "Not picked" to "Picked" inside the window: final.
    rid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO decision_reversals (id, window_id, to_choice, note_encrypted, by_user_id, at) "
        "VALUES (%s, %s, 'pick', %s, %s, %s)",
        (rid, windows["T9"], seal_text("decision_reversals", "note_encrypted", rid,
         "We can ask the exchange to move the reminder. Failed dividends cost more than the change."),
         p["manoj"]["id"], _ago(2, now)),
    )  # fmt: skip
    conn.execute("UPDATE decision_windows SET state = 'reversed' WHERE id = %s", (windows["T9"],))
    _event(conn, m["T9"].uuid, "decision_reversed", _ago(2, now), {"reversal_id": rid})
    conn.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'not_picked', 'picked', %s)",
        (m["T9"].uuid, _ago(2, now)),
    )
    # T7: the reviewer revised what it is worth (L-WORTH), next to Tanvi's figures.
    row = conn.execute(
        "INSERT INTO idea_worth (idea_uuid, by_side, by_user_id, hours_low, hours_high, cost_low, cost_high, "
        "outside_tools, at) VALUES (%s, 'reviewer', %s, 150, 220, 40000, 60000, 'none', %s) RETURNING id",
        (m["T7"].uuid, p["harish"]["id"], _ago(5.1, now)),
    ).fetchone()
    assert row is not None
    conn.execute(
        "UPDATE idea_worth SET note_encrypted = %s WHERE id = %s",
        (seal_text("idea_worth", "note_encrypted", row["id"], "Counted the calls at all six large branches."), row["id"]),
    )  # fmt: skip
    # T11: the desk merged it into Rekha's R2 (window open); Tanvi joins that crew.
    mid = str(uuid.uuid4())
    merged_at = _ago(2.5, now)
    conn.execute(
        "INSERT INTO merges (id, lead_idea_uuid, merged_idea_uuid, via, by_user_id, team_up, note_encrypted, "
        "prior_status, at) VALUES (%s, %s, %s, 'review_desk', %s, true, %s, 'with_review_desk', %s)",
        (mid, m["R2"].uuid, m["T11"].uuid, p["lavanya"]["id"],
         seal_text("merges", "note_encrypted", mid, "Both ideas ask for one clear message after a failed debit."),
         merged_at),
    )  # fmt: skip
    conn.execute(
        "INSERT INTO decision_windows (merge_id, state, opens_at, closes_at, max_closes_at) "
        "VALUES (%s, 'open', %s, %s, %s)",
        (mid, merged_at, merged_at + dt.timedelta(days=30), merged_at + dt.timedelta(days=91)),
    )
    conn.execute("UPDATE ideas SET merged_into = %s WHERE id = %s", (m["R2"].uuid, m["T11"].uuid))
    conn.execute(
        "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'with_review_desk', 'merged', %s)",
        (m["T11"].uuid, merged_at),
    )
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, merge_id, joined_at) "
        "VALUES (%s, %s, 'crew', 'desk_merge', %s, %s)",
        (m["R2"].uuid, tanvi["code"], mid, merged_at),
    )
    _event(conn, m["R2"].uuid, "desk_merged", merged_at, {"merge_id": mid})
    _event(conn, m["T11"].uuid, "desk_merged", merged_at, {"merge_id": mid})


def _crews(conn: Conn, p: dict[str, dict[str, str]], m: dict[str, Made], now: dt.datetime) -> None:
    tanvi = p["tanvi"]
    # Similar ideas (L-SIMILAR): found while drafting, kept separate, asked to merge.
    for a, b, strength, reason, outcome in (
        ("T1", "R1", "related", "Related: the calls branches take", None),
        ("T2", "R1", "close", "Close match: the same failed SIP debit", "merge_asked"),
        ("T5", "P1", "related", "Related: papers asked for twice", "kept_separate"),
        ("T6", "Z1", "related", "Related: distributors waiting on us", "previewed"),
        ("T11", "R2", "close", "Close match: one message after a failed debit", None),
        ("N2", "R1", "close", "Close match: no reason given for a failed SIP debit", "merge_asked"),
        ("G2", "R1", "close", "Close match: investors cannot tell why a SIP debit failed", "merge_asked"),
    ):
        conn.execute(
            "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, outcome) VALUES (%s, %s, %s, %s, %s)",
            (m[a].uuid, m[b].uuid, strength, reason, outcome),
        )
    conn.execute("UPDATE ideas SET kept_separate = true WHERE id = %s", (m["T5"].uuid,))
    first, later, reason = DESK_PAIR
    for a, b, found in ((later, first, "drafting"), (first, later, "later")):
        conn.execute(
            "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, found_while) "
            "VALUES (%s, %s, 'close', %s, %s)",
            (m[a].uuid, m[b].uuid, reason, found),
        )
    conn.execute(  # "Checked and matched" counts the one it found (L-SIMILAR.rules/5)
        "UPDATE conversation_entries SET payload = jsonb_set(payload, '{similar}', '1') "
        "WHERE idea_uuid = %s AND event = 'checked_matched'",
        (m[later].uuid,),
    )

    # T2's, N2's and G2's merge requests wait on Rekha (Submit is held), each in her Inbox with the three answers
    # (L-TEAMUP.rules/5, J-SIMILAR/5). N1's was accepted into T7.
    for key, other, state, note, days in (
        ("T2", "R1", "waiting", "Mine is the same failed SIP SMS. Happy for it to be part of yours.", 0.3),
        (
            "N2",
            "R1",
            "waiting",
            "Investors ask me the same thing at the counter. Please take mine into yours.",
            0.25,
        ),
        (
            "G2",
            "R1",
            "waiting",
            "My branch hears the same question about failed debits. Happy to join yours.",
            0.45,
        ),
        (
            "N1",
            "T7",
            "accepted",
            "I see the same R07 letters at the counter every day. Please take mine in.",
            6.5,
        ),
    ):
        rid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO merge_requests (id, draft_uuid, other_idea_uuid, from_code, note_encrypted, state, "
            "answered_by_code, sent_at, answered_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (rid, m[key].uuid, m[other].uuid, p[m[key].spec.owner]["code"],
             seal_text("merge_requests", "note_encrypted", rid, note), state,
             tanvi["code"] if state == "accepted" else None, _ago(days, now),
             _ago(days - 0.4, now) if state == "accepted" else None),
        )  # fmt: skip
        if state == "waiting":  # as the request's sender posts it: the draft comes along (brought 1)
            _inbox_item(conn, p[m[other].spec.owner]["id"], "teamup_request", p[m[key].spec.owner]["id"],
                        m[other].uuid, {"idea_id": m[other].ref, "request_id": rid, "request": "merge", "brought": 1},
                        _ago(days, now), needs=True, actions=ANSWERS_WITH_MERGE)  # fmt: skip
        if state == "accepted":
            merge_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO merges (id, lead_idea_uuid, merged_idea_uuid, via, by_code, team_up, prior_status, "
                "merge_request_id, at) VALUES (%s, %s, %s, 'lead_accepted', %s, true, 'draft', %s, %s)",
                (merge_id, m[other].uuid, m[key].uuid, tanvi["code"], rid, _ago(days - 0.4, now)),
            )
            conn.execute("UPDATE ideas SET merged_into = %s WHERE id = %s", (m[other].uuid, m[key].uuid))
            conn.execute(
                "INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at) VALUES (%s, 'draft', 'merged', %s)",
                (m[key].uuid, _ago(days - 0.4, now)),
            )
            conn.execute(
                "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, merge_id, joined_at) "
                "VALUES (%s, %s, 'crew', 'merge', %s, %s)",
                (m[other].uuid, p["naveen"]["code"], merge_id, _ago(days - 0.4, now)),
            )

    # Team-up requests (L-TEAMUP): one waiting on Tanvi with an idea brought along, one waiting on Rekha,
    # one approved, one declined.
    requests: tuple[tuple[str, str, str, str | None, float, list[str], str], ...] = (
        (
            "esha",
            "T5",
            "sent",
            None,
            0.5,
            ["E1"],
            "My factsheet idea is about plain words too. Could we work on the investor side together?",
        ),
        (
            "bhavesh",
            "R1",
            "sent",
            None,
            1.2,
            [],
            "I run the courier desk and see the returned SIP letters. Happy to help with the numbers.",
        ),
        (
            "faisal",
            "T7",
            "approved_team_only",
            None,
            4.0,
            [],
            "I handle rejection letters at the Hyderabad counter and can test the new wording.",
        ),
        (
            "tanvi",
            "A1",
            "declined",
            "The build team is full for now. We will ask for testers next month.",
            9.0,
            [],
            "I can help test the nominee pre-fill with walk-in investors at my branch.",
        ),
        (
            "zoya",
            "R1",
            "approved_team_only",
            None,
            5.0,
            [],
            "Distributors ask me the same question after a failed debit. I would like to help.",
        ),
    )
    for who, key, state, lead_reason, days, brought, note in requests:
        rid = str(uuid.uuid4())
        lead = p[m[key].spec.owner]
        conn.execute(
            "INSERT INTO teamup_requests (id, idea_uuid, from_code, note_encrypted, state, lead_reason_encrypted, "
            "answered_by_code, sent_at, answered_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (rid, m[key].uuid, p[who]["code"], seal_text("teamup_requests", "note_encrypted", rid, note), state,
             seal_text("teamup_requests", "lead_reason_encrypted", rid, lead_reason) if lead_reason else None,
             lead["code"] if state != "sent" else None, _ago(days, now),
             _ago(days - 0.5, now) if state != "sent" else None),
        )  # fmt: skip
        for b in brought:
            conn.execute(
                "INSERT INTO teamup_brought (request_id, idea_uuid) VALUES (%s, %s)", (rid, m[b].uuid)
            )
        if state.startswith("approved"):
            conn.execute(
                "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, teamup_request_id, joined_at) "
                "VALUES (%s, %s, 'crew', 'teamup', %s, %s)",
                (m[key].uuid, p[who]["code"], rid, _ago(days - 0.5, now)),
            )
            _event(conn, m[key].uuid, "crew_joined", _ago(days - 0.5, now), {"request_id": rid})
    # More crew on shipped and building ideas, so cards show faces and counts.
    for key, who, days in (("V1", "tanvi", 100), ("V1", "bhavesh", 98), ("A1", "hemant", 25), ("C1", "bhavesh", 9),
                           ("S1", "naveen", 160), ("J1", "pallavi", 40)):  # fmt: skip
        conn.execute(
            "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at) VALUES (%s, %s, 'crew', 'teamup', %s)",
            (m[key].uuid, p[who]["code"], _ago(days, now)),
        )
    # One crew member left (L-TEAMUP/11).
    conn.execute(
        "INSERT INTO crew_members (idea_uuid, contributor_code, role, via, joined_at, left_at, left_how) "
        "VALUES (%s, %s, 'crew', 'teamup', %s, %s, 'left')",
        (m["H1"].uuid, p["jatin"]["code"], _ago(40, now), _ago(20, now)),
    )
    # The crew deck (L-CREW/6): Tanvi passed two, then undid one.
    for key, undone in (("G1", False), ("J1", True)):
        conn.execute(
            "INSERT INTO crew_passes (user_id, idea_uuid, passed_at, undone_at) VALUES (%s, %s, %s, %s)",
            (tanvi["id"], m[key].uuid, _ago(0.2, now), _ago(0.1, now) if undone else None),
        )
    # Conversations: the crew and the desk talk on T7, with a mention.
    _message(conn, m["T7"].uuid, _ago(4.8, now), "Thanks for picking it. I have the list of the ten most common codes.",
             code=tanvi["code"])  # fmt: skip
    _message(conn, m["T7"].uuid, _ago(4.5, now), "Good. Please share the list here so compliance can start on the wording.",
             user=p["harish"]["id"])  # fmt: skip
    _message(conn, m["T7"].uuid, _ago(3.0, now), "I added the counter questions we hear for R07 and R12. Tanvi, can you check them?",
             code=p["naveen"]["code"], mentions=[tanvi["id"]])  # fmt: skip
    _message(conn, m["R1"].uuid, _ago(1.0, now), "Is the failed debit reason in the bank file, or only in the exchange report?",
             user=p["lavanya"]["id"])  # fmt: skip


def _builds_and_impact(
    conn: Conn, p: dict[str, dict[str, str]], m: dict[str, Made], now: dt.datetime
) -> None:
    teams = {"V1": ("Payout checks team", "gopal", ["hemant"]), "S1": ("Online forms team", "gopal", []),
             "D1": ("Distributor statements team", "dinesh", []), "I1": ("Registry checklist team", "indira", []),
             "A1": ("Nominee pre-fill team", "gopal", ["siddharth"]), "H1": ("Mandate retry team", "hemant", [])}  # fmt: skip
    for key, (name, lead, members) in teams.items():
        made = m[key]
        chosen = _ago(made.spec.team_days or 0, now)
        conn.execute(
            "INSERT INTO build_teams (idea_uuid, name, lead_user_id, chosen_by, chosen_at) VALUES (%s, %s, %s, %s, %s)",
            (made.uuid, name, p[lead]["id"], p["kunal"]["id"], chosen),
        )
        for person in (lead, *members):
            conn.execute(
                "INSERT INTO role_grants (user_id, role, scope_id, granted_by) VALUES (%s, 'build_team', %s, %s)",
                (p[person]["id"], made.ref, p["kunal"]["id"]),
            )
        _event(conn, made.uuid, "team_chosen", chosen, {"team": name})
        if made.spec.shipped_days is not None:
            _event(conn, made.uuid, "shipped", _ago(made.spec.shipped_days, now), {})
    _message(conn, m["A1"].uuid, _ago(1.0, now), "The first pre-filled forms are ready to try. Please check them before Thursday.",
             user=p["gopal"]["id"])  # fmt: skip

    # L-IMPACT: 30 and 90 days after shipping. Money shows only once Finance confirms.
    def measure(key: str, mark: str, results: dict[str, Any] | None, finance: bool) -> None:
        made = m[key]
        shipped = _ago(made.spec.shipped_days or 0, now)
        due = shipped + dt.timedelta(days=30 if mark == "day_30" else 90)
        filled = due + dt.timedelta(days=2) if results is not None else None
        conn.execute(
            "INSERT INTO delivery_measurements (idea_uuid, mark, due_at, results, filled_by, filled_at, confirmed_by, "
            "confirmed_at, finance_confirmed_by, finance_confirmed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (made.uuid, mark, due, Jsonb({**(results or {}), "synthetic": True}),
             p["gopal"]["id"] if filled else None, filled, p["kunal"]["id"] if filled else None, filled,
             p["kunal"]["id"] if finance else None, filled if finance else None),
        )  # fmt: skip

    measure("V1", "day_30", {"time": {"value": "620", "line": "hours a month"},
                             "money": {"value": "₹18 lakh", "line": "a year"},
                             "scale": {"value": "41", "line": "branches"},
                             "sentence": "620 hours a month saved; bounced payouts down by a third"}, True)  # fmt: skip
    measure("V1", "day_90", None, False)
    measure("S1", "day_30", {"time": {"value": "90", "line": "hours a month"}}, False)
    measure("S1", "day_90", {"time": {"value": "140", "line": "hours a month"},
                             "effort": {"value": "2 fewer steps", "line": "per online form"},
                             "sentence": "Returned online forms down by half"}, False)  # fmt: skip
    measure("D1", "day_30", {"time": {"value": "60", "line": "hours a month"}}, False)
    measure("D1", "day_90", {"time": {"value": "110", "line": "hours a month"},
                             "scale": {"value": "58,600", "line": "distributors reached"},
                             "sentence": "Support calls about statements down by 40 percent"}, False)  # fmt: skip
    measure("I1", "day_30", {"time": {"value": "70", "line": "hours a month"},
                             "money": {"value": "₹6 lakh", "line": "a year"},
                             "sentence": "Returned transfer requests down by a quarter"}, False)  # fmt: skip


ONES: list[tuple[str, int, int, str, str | None, str, int]] = [
    # (person, number wanted, tier, way in, idea key, impact brief, days since induction)
    ("aparna", 2, 6, "founding", None, "Made share transfer checks one step for every service centre.", 400),
    ("rekha", 4, 4, "founding", None, "Cut the calls investors make after a failed SIP debit.", 380),
    ("dinesh", 8, 5, "founding", "D1", "Brokerage statements distributors can read without calling us.", 360),
    ("varun", 11, 3, "accepted_idea", "V1", "Stopped wrong bank details before a payout goes out.", 8),
    ("gopal", 15, 7, "founding", None, "Builds the fixes that save branches the most hours.", 420),
    ("siddharth", 21, 1, "accepted_idea", "S1", "Online forms that fill the city from the pin code.", 10),
    ("indira", 30, 2, "accepted_idea", "I1", "One checklist that stops share transfer returns.", 12),
]  # fmt: skip

# J-ONE step 6, S-ONE `showGlowUp` (L-ONES.rules/3): D1's 90-day figures warmed Dinesh from Tier 4, Blaze to Tier 5,
# White heat (his tier in ONES), and he has not opened his dashboard since, so the moment waits to play once. Not
# Siddharth: J-ONE/4 and /6 walk his dashboard at Tier 1, and the moment would cover it.
# (who, tier before, days since the rise, Ones Committee member who signs the note, the note)
GLOW_UP = ("dinesh", 4, 2.0, "manoj",
           "Distributors read their statements without calling us now. White heat suits you. Thank you, Dinesh.")  # fmt: skip


def _free_number(conn: Conn, wanted: int) -> int:
    n = wanted
    while conn.execute("SELECT 1 FROM ones WHERE number = %s", (n,)).fetchone():
        n += 1
    return n


def _ones(conn: Conn, p: dict[str, dict[str, str]], m: dict[str, Made], now: dt.datetime) -> None:
    one_ids: dict[str, int] = {}
    for who, wanted, tier, way_in, idea_key, brief, days in ONES:
        n = conn.execute("SELECT next_number('ONE', '') AS n").fetchone()
        assert n is not None
        number = _free_number(conn, wanted)
        inducted = _ago(days, now)
        row = conn.execute(
            "INSERT INTO ones (induction_no, user_id, number, way_in, idea_id, tier, measures, inducted_at, swap_until, "
            "brief_approved_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (n["n"], p[who]["id"], number, way_in, m[idea_key].ref if idea_key else None, tier,
             Jsonb({"time": {"value": "620", "line": "hours a month", "synthetic": True}} if who == "varun" else {}),
             inducted, inducted + dt.timedelta(days=30), inducted),
        ).fetchone()  # fmt: skip
        assert row is not None
        oid = int(row["id"])
        one_ids[who] = oid
        conn.execute(  # the Ones module's own sealing for briefs (ones/text.py seal)
            "UPDATE ones SET brief_encrypted = %s WHERE id = %s",
            (encrypt_json({"text": brief}, f"one:{oid}:brief"), oid),
        )
        conn.execute(
            "INSERT INTO one_number_history (one_id, number, how, from_at) VALUES (%s, %s, 'allocated', %s)",
            (oid, number, inducted),
        )
    posts: tuple[tuple[str, str, str, str, str, int | None, list[str]], ...] = (
        ("varun", "V1", "Payout checks are live at every branch. Bounced payouts are down by a third.", "620",
         "hours a month saved", 3, ["tanvi", "rekha", "harish", "naveen", "zoya"]),
        ("dinesh", "D1", "Distributors now read their brokerage statements without calling support.", "40%",
         "fewer support calls", None, ["aparna", "gopal", "pallavi"]),
        ("siddharth", "S1", "The online form fills the city from the pin code. Returned forms are down by half.", "50%",
         "fewer returned forms", 2, ["tanvi", "lavanya"]),
        ("indira", "I1", "One checklist for share transfers is in every service centre now.", "₹6 lakh",
         "saved a year", None, []),
    )  # fmt: skip
    for i, (who, key, text, value, line, adopted, likers) in enumerate(posts):
        pid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO one_posts (id, one_id, idea_uuid, text_encrypted, figure_value, figure_line, adopted_by, "
            "posted_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (pid, one_ids[who], m[key].uuid, seal_text("one_posts", "text_encrypted", pid, text), value, line,
             adopted, _ago(1 + 2 * i, now)),
        )  # fmt: skip
        for liker in likers:
            conn.execute(
                "INSERT INTO one_post_likes (post_id, user_id) VALUES (%s, %s)", (pid, p[liker]["id"])
            )
    _glow_up(conn, p, one_ids, now)


def _glow_up(conn: Conn, p: dict[str, dict[str, str]], one_ids: dict[str, int], now: dt.datetime) -> None:
    """GLOW_UP's tier rise, unseen. `one_glow_ups` (20261114000100) hangs off a carried-out `tier_up` proposal, and
    the committee's note rides on that proposal, which is where `ones.views.my_one` reads "Messages for you"."""
    who, tier_from, days, by, note = GLOW_UP
    tier_to = next(tier for person, _n, tier, *_rest in ONES if person == who)
    risen = _ago(days, now)
    row = conn.execute(
        "INSERT INTO one_proposals (kind, one_id, subject_user_id, tier_to, proposed_by, proposed_at, state, approval, "
        "decided_by, decided_at, carried_out_by, carried_out_at) "
        "VALUES ('tier_up', %s, %s, %s, %s, %s, 'carried_out', 'chair', %s, %s, %s, %s) RETURNING id",
        (one_ids[who], p[who]["id"], tier_to, p[by]["id"], risen, p[by]["id"], risen, p["kunal"]["id"], risen),
    ).fetchone()  # fmt: skip
    assert row is not None
    proposal = int(row["id"])
    row = conn.execute(
        "INSERT INTO one_messages (proposal_id, author_user_id, author_role, written_at) "
        "VALUES (%s, %s, 'committee', %s) RETURNING id",
        (proposal, p[by]["id"], risen),
    ).fetchone()
    assert row is not None
    conn.execute(  # sealed as the Ones module seals it (ones/text.py seal)
        "UPDATE one_messages SET text_encrypted = %s WHERE id = %s",
        (encrypt_json({"text": note}, f"one_message:{row['id']}"), row["id"]),
    )
    conn.execute(  # seen_at stays empty: it plays once on S-ONE, then glow_up_seen marks it (S-ONE.rules/3)
        "INSERT INTO one_glow_ups (one_id, proposal_id, tier_from, tier_to, created_at) VALUES (%s, %s, %s, %s, %s)",
        (one_ids[who], proposal, tier_from, tier_to, risen),
    )


# A team-up request with an idea brought along, or a draft's merge request: the lead's three answers (L-TEAMUP.rules/5).
ANSWERS_WITH_MERGE = [
    {"label": "Decline", "op": "decline", "style": "text"},
    {"label": "Team up only", "op": "team_only", "style": "line"},
    {"label": "Merge it", "op": "merge", "style": "primary"},
]


def _inbox_item(
    conn: Conn, to: str, kind: str, sender: str | None, idea_uuid: str, refs: dict[str, Any], at: dt.datetime, *,
    actions: list[dict[str, str]], needs: bool = False, due: dt.datetime | None = None, read: bool = False,
    archived: bool = False,
) -> None:  # fmt: skip
    """One in-app Inbox item. `refs` are IDs and small values only; the line is rendered at read time (BLD-088)."""
    conn.execute(
        "INSERT INTO notifications (user_id, channel, template, event, payload, state, created_at, sent_at, "
        "read_at, kind, from_user_id, idea_uuid, needs_you, due_at, archived_at, actions) "
        "VALUES (%s, 'in_app', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (to, f"inbox/{kind}", f"inbox.{kind}", Jsonb(refs), "read" if read else "sent", at, at,
         at + dt.timedelta(hours=1) if read else None, kind, sender, idea_uuid, needs, due,
         at + dt.timedelta(days=1) if archived else None, Jsonb(actions)),
    )  # fmt: skip


def _inbox(conn: Conn, p: dict[str, dict[str, str]], m: dict[str, Made], now: dt.datetime) -> None:
    """Every Inbox kind (E-ENUMS.inbox) at least once. Text is rendered from templates at read time (BLD-088)."""
    items = (
        # (to, kind, from, idea, days ago, needs you, due in days, read, archived, actions)
        ("tanvi", "questions", "harish", "T6", 1.0, True, 2.0, True, False,
         [{"label": "Answer the questions", "to": "answer", "style": "primary"}]),
        ("tanvi", "answer_reminder", None, "T6", 0.1, True, 2.0, False, False,
         [{"label": "Answer the questions", "to": "answer", "style": "primary"}]),
        ("tanvi", "teamup_request", "esha", "T5", 0.5, True, None, False, False, ANSWERS_WITH_MERGE),
        ("tanvi", "decision", "harish", "T7", 5.0, False, None, True, False,
         [{"label": "Read the decision", "to": "idea", "style": "line"}]),
        ("tanvi", "decision_reversed", "manoj", "T9", 2.0, False, None, False, False,
         [{"label": "Read the note", "to": "idea", "style": "line"}]),
        ("tanvi", "desk_merge", "lavanya", "T11", 2.5, False, None, True, False,
         [{"label": "Open the idea", "to": "idea", "style": "line"}]),
        ("tanvi", "worth_revised", "harish", "T7", 5.1, False, None, True, True,
         [{"label": "Open the idea", "to": "idea", "style": "line"}]),
        ("tanvi", "crew_joined", "faisal", "T7", 3.5, False, None, True, False,
         [{"label": "Open the idea", "to": "idea", "style": "line"}]),
        ("tanvi", "mention", "naveen", "T7", 3.0, False, None, False, False,
         [{"label": "Open the conversation", "to": "conversation", "style": "line"}]),
        ("tanvi", "teamup_answer", "aparna", "A1", 8.5, False, None, True, False,
         [{"label": "Open the idea", "to": "idea", "style": "line"}]),
        ("tanvi", "stage_moved", None, "V1", 40.0, False, None, True, True,
         [{"label": "Open the idea", "to": "idea", "style": "line"}]),
        ("tanvi", "draft_kept", None, "T1", 2.2, False, None, True, False,
         [{"label": "Carry on", "to": "draft", "style": "primary"}]),
        ("tanvi", "sent_to_desk", None, "T5", 1.0, False, None, True, False,
         [{"label": "Open the idea", "to": "idea", "style": "line"}]),
        ("tanvi", "comment", "harish", "T7", 4.5, False, None, True, False,
         [{"label": "Open the conversation", "to": "conversation", "style": "line"}]),
        ("rekha", "teamup_request", "bhavesh", "R1", 1.2, True, None, False, False,
         [{"label": "Decline", "op": "decline", "style": "text"}, {"label": "Approve", "op": "team_only", "style": "primary"}]),
        ("aparna", "build_ask", "gopal", "A1", 1.0, True, 3.0, False, False,
         [{"label": "Open the conversation", "to": "conversation", "style": "primary"}]),
        ("hemant", "build_ask", "gopal", "A1", 1.0, True, 3.0, False, False,
         [{"label": "Open the conversation", "to": "conversation", "style": "primary"}]),
        ("faisal", "teamup_answer", "tanvi", "T7", 3.5, False, None, True, False,
         [{"label": "Say hello", "to": "conversation", "style": "primary"}]),
        ("faisal", "decision", "harish", "F1", 3.0, False, None, False, False,
         [{"label": "Read the decision", "to": "idea", "style": "line"}]),
        ("zoya", "questions", "harish", "Z1", 4.0, True, -1.0, True, False,
         [{"label": "Answer the questions", "to": "answer", "style": "primary"}]),
        ("lavanya", "decision_reversed", "manoj", "T9", 2.0, False, None, False, False,
         [{"label": "Read the note", "to": "idea", "style": "line"}]),
    )  # fmt: skip
    for to, kind, sender, key, days, needs, due, read, archived, actions in items:
        _inbox_item(conn, p[to]["id"], kind, p[sender]["id"] if sender else None, m[key].uuid,
                    {"idea_id": m[key].ref}, _ago(days, now), actions=actions, needs=needs,
                    due=now + dt.timedelta(days=due) if due is not None else None, read=read, archived=archived)  # fmt: skip
    # J-RESUME/5: the email arrival's "kept your draft", as draft intake posts it (L-DRAFT.channels; refs: channel).
    email = m["I2"]
    _inbox_item(conn, p[email.spec.owner]["id"], "draft_kept", None, email.uuid,
                {"idea_id": email.ref, "channel": email.spec.channel}, _ago(email.spec.saved_days + 0.05, now),
                actions=[{"label": "Check and send", "to": "draft", "style": "primary"}])  # fmt: skip


def _wall_and_flags(conn: Conn, p: dict[str, dict[str, str]], m: dict[str, Made], now: dt.datetime) -> None:
    """Opened this week (L-WALL.justin/4), per day and per person, and the S1–S3 assignments with exposures."""
    viewers = [k for k in p if k not in ("hyderabad",)]
    popularity = {"R1": 14, "P1": 9, "T6": 6, "Z1": 11, "B1": 3, "T5": 5, "R2": 7, "E1": 1, "C1": 8, "J1": 4}
    for key, count in popularity.items():
        owner = m[key].spec.owner
        for i, viewer in enumerate(v for v in viewers if v != owner and v not in ("harish", "lavanya")):
            if i >= count:
                break
            day = (now - dt.timedelta(days=i % 6)).astimezone(IST).date()
            conn.execute(
                "INSERT INTO idea_opens (idea_uuid, user_id, day) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (m[key].uuid, p[viewer]["id"], day),
            )
    for who, flag, variant in (("tanvi", "s1", "default"), ("tanvi", "s3", "alternative"), ("naveen", "s1", "alternative"),
                               ("rekha", "s2", "alternative")):  # fmt: skip
        conn.execute(
            "INSERT INTO flag_assignments (flag_key, user_id, variant, assigned_by) VALUES (%s, %s, %s, 'rule')",
            (flag, p[who]["id"], variant),
        )
        conn.execute(
            "INSERT INTO flag_exposures (flag_key, user_id, variant, screen, at) VALUES (%s, %s, %s, %s, %s)",
            (flag, p[who]["id"], variant, "S-04" if flag != "s2" else "S-05", _ago(1, now)),
        )


# --- Remove --------------------------------------------------------------------------------------------------------


def seed_user_ids(conn: Conn) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM users WHERE emp_id_hash = ANY(%s)", ([emp_id_hash(e) for e, *_ in PEOPLE],)
    ).fetchall()
    return [str(r["id"]) for r in rows]


def remove(conn: Conn) -> None:
    """The seed's people and everything that is theirs. Nobody else's rows are touched; what a seeded person did on
    someone else's idea (a decision, a question set, a crew place) goes too."""
    with conn.transaction():
        users = seed_user_ids(conn)
        if not users:
            return
        codes = [str(r["contributor_code"]) for r in conn.execute(
            "SELECT contributor_code FROM contributor_map WHERE user_id = ANY(%s::uuid[])", (users,)).fetchall()]  # fmt: skip
        ideas = conn.execute(
            "SELECT id, idea_id FROM ideas WHERE contributor_code = ANY(%s)", (codes,)
        ).fetchall()
        scopes = [str(r["idea_id"]) for r in ideas if r["idea_id"]] + [f"DRAFT-{r['id']}" for r in ideas]
        conn.execute("DELETE FROM pseudonym_vault WHERE scope_id = ANY(%s)", (scopes,))
        conn.execute("DELETE FROM vault_counters WHERE scope_id = ANY(%s)", (scopes,))
        conn.execute("DELETE FROM flag_exposures WHERE user_id = ANY(%s::uuid[])", (users,))
        conn.execute(
            "DELETE FROM ones WHERE user_id = ANY(%s::uuid[])", (users,)
        )  # posts and history go with them
        conn.execute(
            "DELETE FROM ideas WHERE contributor_code = ANY(%s)", (codes,)
        )  # every idea-scoped row cascades
        # A seeded person's actions on anyone else's idea.
        for table, column in (("decision_reversals", "by_user_id"), ("idea_decisions", "by_user_id"),
                              ("merges", "by_user_id"), ("question_sets", "by_user_id")):  # fmt: skip
            conn.execute(f"DELETE FROM {table} WHERE {column} = ANY(%s::uuid[])", (users,))  # noqa: S608 - fixed names
        for table, column in (("crew_members", "contributor_code"), ("teamup_requests", "from_code"),
                              ("merge_requests", "from_code"), ("answers", "by_code")):  # fmt: skip
            conn.execute(f"DELETE FROM {table} WHERE {column} = ANY(%s)", (codes,))  # noqa: S608 - fixed names
        conn.execute(
            "DELETE FROM delivery_measurements WHERE filled_by = ANY(%s::uuid[]) OR confirmed_by = ANY(%s::uuid[]) "
            "OR finance_confirmed_by = ANY(%s::uuid[])",
            (users, users, users),
        )
        conn.execute(
            "UPDATE users SET manager_user_id = NULL WHERE manager_user_id = ANY(%s::uuid[])", (users,)
        )
        conn.execute(
            "DELETE FROM users WHERE id = ANY(%s::uuid[])", (users,)
        )  # grants, settings, inbox cascade


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reset", action="store_true", help="remove the seed's rows and load it again")
    mode.add_argument("--remove", action="store_true", help="remove the seed's rows and stop")
    args = parser.parse_args(argv)
    _dev_only()
    with connect(autocommit=True) as conn:
        loaded = bool(seed_user_ids(conn))
        if args.remove:
            remove(conn)
            print("1% Club seed: removed" if loaded else "1% Club seed: not loaded, nothing to remove")
            return 0
        if loaded and not args.reset:
            print("1% Club seed: already loaded (make demo-reset DEMO_SET=1pc starts it fresh)")
            return 0
        remove(conn)
        load(conn)
    print("1% Club seed: loaded. Sign in at http://localhost:3000 with these employee IDs as the username:")
    for emp, name, *_rest, label in PEOPLE:
        if label:
            print(f"  {emp}  {name:24} {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
