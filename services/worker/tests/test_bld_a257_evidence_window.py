"""BLD-A257: the evidence window after the switch to full mode (the product lead's Sunday plan, lane A item 3).

`docs/UAT.md`, "Switching to full mode (mode A)", carries a note after step 10 with three read-only reads IT runs on
the server after Monday's switch: Send to sorted, the model calls by agent and outcome, and the team-up counts. Counts
and seconds only, never text (non-negotiable 3). For information, not a gate. Doc tests only, no database: the
database dry run of the same three SQL strings is `test_bld_a257_evidence_window_db.py` (stack, CI only).

The helpers here (`reads`, `bad_read`, `sealed_hits`) are shared with that test, so both read the doc's own SQL.
"""

from __future__ import annotations

import re

import pytest

from tests import helpers
from tests.test_b4_service_roles import HIDDEN_FROM_WEB  # the pinned list; a pure import, no database

UAT_DOC = helpers.ROOT / "docs" / "UAT.md"
MIGRATIONS = helpers.ROOT / "db" / "migrations"
NOTE = "**The evidence window after the switch (BLD-A257; for information, not a gate).**"
BACK = "**Back to Capture first**"
PSQL = re.compile(r'^docker exec kfin-ideas-uat-postgres-1 psql -U ideas -d ideas -c "([^"]+)"$')
# The window starts at the latest `ai.all` switch-on, read from the audit row both writers make (core/killswitch.py
# `set_switch` and the Admin page's apps/web/src/server/killswitch.ts).
SINCE = (
    "WITH s AS (SELECT max(at) AS since FROM audit_log WHERE action = 'kill_switch.set' "
    "AND entity = 'kill_switch:ai.all' AND after->>'state' = 'on')"
)
# What each read prints, in order: numbers, the window start and two labels.
COLUMNS = (
    ("since", "sent", "sorted", "checking_over_15_min", "p50_s", "p95_s", "max_s"),
    ("agent", "outcome", "calls", "p50_s", "p95_s", "max_s"),
    ("teamup_sent", "teamup_answered", "teamup_declined", "draft_asks", "draft_asks_declined"),
)

# ---- the allowlist: every identifier the three reads may use (lane C's review) -----------------------------------
# String literals are taken out first; what is left must be one of these, or the scan names it.
SQL_WORDS = {
    "with", "as", "select", "from", "join", "on", "where", "and", "is", "null", "filter", "count", "min", "max",
    "round", "percentile_cont", "within", "group", "order", "by", "extract", "epoch", "now", "interval", "numeric",
}  # fmt: skip
ALIASES = {
    "s", "t", "h", "o", "c", "r", "m", "since", "sent", "sorted", "checking_over_15_min", "p50_s", "p95_s", "max_s",
    "calls", "teamup_sent", "teamup_answered", "teamup_declined", "draft_asks", "draft_asks_declined",
}  # fmt: skip
TABLES = {"audit_log", "idea_status_history", "llm_calls", "teamup_requests", "merge_requests"}
TABLE_COLUMNS = {
    "audit_log": {"at", "action", "entity", "after"},
    "idea_status_history": {"idea_uuid", "from_status", "to_status", "at", "source"},
    "llm_calls": {"agent", "outcome", "latency_ms", "created_at"},
    "teamup_requests": {"sent_at", "answered_at", "state"},
    "merge_requests": {"sent_at", "answered_at", "state"},
}
ALLOWED = SQL_WORDS | ALIASES | TABLES | set().union(*TABLE_COLUMNS.values())


def not_allowed(sql: str) -> list[str]:
    """Every identifier of the SQL, outside its string literals, that is not on the allowlist (lower case)."""
    words = re.findall(r"[a-z_][a-z0-9_]*", re.sub(r"'[^']*'", "''", sql).lower())
    return sorted({w for w in words if w not in ALLOWED})


# ---- the deny list, the second net: columns and tables that hold people's words or hidden values ----------------
# The plain-text columns of the schema that carry words (masked or not), and the sealed tables by name.
PLAIN_TEXT = {
    "title", "summary", "text", "note", "words", "reason", "name", "email", "first_name", "body", "comment",
    "content", "context_text", "description", "detail", "helper_text", "helper_picks", "open_questions", "outline",
    "parts", "payload", "qna_notes", "source_quote", "statement", "why", "figure_line", "role_title",
    "hr_job_title", "hr_department", "outcome_note", "solved_note", "hidden_note", "clear_reason",
    "override_reason", "plain_reason", "restore_reason", "veto_reason", "visibility_reason",
    "below_threshold_reason",
}  # fmt: skip
SEALED_TABLES = {"idea_words_sealed", "pseudonym_vault", "hidden_values", "hidden_details", "vault_counters"}
SEALED_SUFFIXES = ("_encrypted", "_sealed", "_masked", "_reason", "_note", "_text", "_name", "_quote")
_NOT_A_COLUMN = {
    "returns",
    "type",
    "as",
}  # `RETURNS bytea`, `TYPE bytea`: keywords before the type, not names


def _migrations() -> str:
    return "\n".join(p.read_text("utf-8") for p in sorted(MIGRATIONS.glob("*.sql")))


def bytea_columns() -> set[str]:
    """Every column any migration declares `bytea`: sealed words, sealed notes, the vault's values and hashes."""
    found = {m.lower() for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+bytea\b", _migrations())}
    return found - _NOT_A_COLUMN


def web_revoked_tables() -> set[str]:
    """Every table a migration revokes from the web role altogether (the worker-only tables, non-negotiable 6)."""
    out: set[str] = set()
    for names in re.findall(r"REVOKE ALL ON ([a-z0-9_, ]+?) FROM [a-z_, ]*\bideas_web_svc\b", _migrations()):
        out |= {n.strip() for n in names.split(",") if n.strip()}
    return out


def deny_list() -> set[str]:
    return PLAIN_TEXT | SEALED_TABLES | bytea_columns() | web_revoked_tables()


def denied(word: str, deny: set[str] | None = None) -> bool:
    return word in (deny_list() if deny is None else deny) or word.endswith(SEALED_SUFFIXES)


def sealed_hits(sql: str) -> list[str]:
    """Every word of the SQL, string literals included (`after->>'note'` would read a text), that names a column or
    a table holding people's words or hidden values. Empty means the read touches none of them."""
    deny = deny_list()
    words = re.findall(r"[a-z_][a-z0-9_]*", sql.lower())
    return sorted({w for w in words if denied(w, deny)})


# ---- the note and its three reads ---------------------------------------------------------------------------------


def _section(doc: str, heading: str) -> str:
    return doc.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def full_mode() -> str:
    return _section(UAT_DOC.read_text("utf-8"), "Switching to full mode (mode A)")


def note() -> str:
    return full_mode().split(NOTE, 1)[1].split(BACK, 1)[0]


def _bash_blocks() -> list[str]:
    return re.findall(r"^```bash\n(.*?)^```$", note(), re.M | re.S)


def reads() -> list[str]:
    """The three SQL strings, read out of the note's bash block. The database test runs these, never a copy."""
    return [m.group(1) for line in "".join(_bash_blocks()).splitlines() if (m := PSQL.match(line))]


def bad_read() -> str:
    """Read 1 with the ideas' titles added to its select list: built here, never in the doc. Both gates must fail
    on it: the sealed-column scan below, and the database test's numbers-only check on its output."""
    first = reads()[0]
    head = "SELECT (SELECT since FROM s) AS since, "
    assert head in first
    title = "(SELECT string_agg(i.title, ' | ') FROM ideas i) AS title, "  # the test's own bad read, never in the doc
    return first.replace(head, head + title, 1)


def test_bld_a257_note_sits_after_step_10_and_before_back_to_capture_first() -> None:
    doc = UAT_DOC.read_text("utf-8")
    section = full_mode()
    assert doc.count(NOTE) == 1 and section.count(NOTE) == 1
    positions = [
        section.index("10. **Run the smoke checks**"),
        section.index("`smoke: all checks passed`"),
        section.index(NOTE),
        section.index(BACK),
    ]
    assert positions == sorted(positions)
    # It is a note, not a step: the ten numbered steps stay as they are (test_a245_mode_a.py pins them).
    assert re.findall(r"^ ?(\d+)\. \*\*", section, re.M) == [str(n) for n in range(1, 11)]
    assert not re.search(r"^ ?\d+\. ", note(), re.M)


def test_bld_a257_three_psql_reads_and_nothing_else_that_runs() -> None:
    [block] = _bash_blocks()
    lines = block.splitlines()
    assert len(lines) == 3 and all(PSQL.match(line) for line in lines), lines
    assert len(reads()) == 3
    text = note()
    assert text.count("docker exec ") == 3 and text.count("```") == 2
    assert not re.search(r"\b(sudo|compose|make|python|curl|psql -f)\b", text.replace(block, ""))


@pytest.mark.parametrize("n", [0, 1, 2], ids=["send-to-sorted", "model-calls", "team-up"])
def test_bld_a257_each_read_only_reads(n: int) -> None:
    sql = reads()[n]
    assert re.match(r"(WITH|SELECT)\b", sql)
    assert ";" not in sql
    words = re.sub(r"'[^']*'", "''", sql)  # literals cannot run anything; `'kill_switch.set'` is not SET
    writes = r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE|COPY|CREATE|GRANT|REVOKE|INTO|SET|LOCK|CALL|DO|VACUUM)\b"
    assert not re.search(writes, words, re.I), sql
    assert not re.search(r"\b(nextval|setval|set_config|pg_\w+|dblink\w*|lo_\w+)\s*\(", words, re.I), sql
    # The window: the latest ai.all switch-on, the same way in all three.
    assert sql.startswith(SINCE)
    # Its last select prints the columns the note names and the database test checks, in order.
    named = [c for c in COLUMNS[n] if c not in ("agent", "outcome")]
    assert re.findall(r"\bAS (\w+)", sql)[-len(named) :] == named
    if n == 1:
        assert "SELECT c.agent, c.outcome, count(*) AS calls" in sql
    if n == 2:  # a decline is counted by its state, never by the lead's reason column
        assert "r.answered_at >= s.since AND r.state = 'declined') AS teamup_declined" in sql
        assert "m.answered_at >= s.since AND m.state = 'declined') AS draft_asks_declined FROM s" in sql


def test_bld_a257_the_window_start_is_the_row_set_switch_writes() -> None:
    """Both writers of a switch change make the row SINCE reads: action, entity and `after.state`."""
    py = (helpers.ROOT / "services" / "worker" / "core" / "killswitch.py").read_text("utf-8")
    assert "VALUES (%s, 'kill_switch.set', %s, %s, %s, %s, %s)" in py
    assert 'f"kill_switch:{name}"' in py and 'Jsonb({"state": state})' in py
    ts = (helpers.ROOT / "apps" / "web" / "src" / "server" / "killswitch.ts").read_text("utf-8")
    assert 'action: "kill_switch.set"' in ts and "entity: `kill_switch:${input.name}`" in ts
    assert "after: JSON.stringify({ state: input.state })" in ts
    # Step 7's fourth read starts its window the same way (with the gatekeeper's switch as well).
    assert (
        "SELECT max(at) AS since FROM audit_log WHERE action = 'kill_switch.set' AND entity IN" in full_mode()
    )


def test_bld_a257_send_and_sorted_are_the_moves_the_code_makes() -> None:
    """Send moves an idea draft -> checking; the check moves it on from checking. The history trigger records each
    move with source 'live'. "Sorted" is the first move out of checking, the moment the conversation shows
    "Checked and matched" (convo/render.py `checked`)."""
    worker = helpers.ROOT / "services" / "worker"
    send = (worker / "submit" / "send.py").read_text("utf-8")
    assert "UPDATE ideas SET status = 'checking'" in send and "WHERE id = %s AND status IN ('draft')" in send
    check = (worker / "submit" / "check.py").read_text("utf-8")
    assert "UPDATE ideas SET status = 'with_review_desk'" in check and "AND status = 'checking'" in check
    render = (worker / "convo" / "render.py").read_text("utf-8")
    assert (
        "SELECT min(at) AS at FROM idea_status_history WHERE idea_uuid = %s AND from_status = 'checking'"
        in render
    )
    cutover = (MIGRATIONS / "20261121500100_handoff_cutover.sql").read_text("utf-8")
    assert "source      text        NOT NULL DEFAULT 'live' CHECK (source IN ('live', 'backfill'))" in cutover
    assert "CREATE TRIGGER ideas_status_history AFTER INSERT OR UPDATE OF status ON ideas" in cutover
    sql = reads()[0]
    assert "h.from_status = 'draft' AND h.to_status = 'checking' AND h.source = 'live'" in sql
    assert "o.from_status = 'checking' AND o.at >= h.at" in sql


def test_bld_a257_the_note_says_what_it_is_when_and_its_limit() -> None:
    text = NOTE + note()  # the bold heading, then its body
    for words in (
        "for information, not a gate",
        "counts and seconds only",
        "no text, no ID and no name",
        "latest time `ai.all` was switched on",
        "about 60 minutes after step 6",
        "17:00 IST the same day",
        "Paste back: the three results, each time.",
        "there is no pass or fail",
        '"scan time at the 95th percentile under 15 s"',
        "If `checking_over_15_min` is above 0, or `since` is empty, send to lane A at once",
        "keeps no end-to-end time for a team-up send, a decline with a reason or a draft's ask",
        "one gatekeeper call outside the lock (BLD-F100)",
        "the `gatekeeper` rows of the second read are the time they wait for the model",
        "the third read counts them",
        "and drafts' asks sent and declined (with or without the lead's reason)",
    ):
        assert words in text, words
    arch = (helpers.ROOT / "docs" / "ARCHITECTURE.md").read_text("utf-8")
    assert "| Scan time at the 95th percentile under 15 s at 150 submissions an hour | Load test |" in arch
    # Plain words, no secret, no real address (as BLD-A249's note).
    assert not re.search(r"@kfintech\.com|PASSWORD=|SECRET|sk-ant-|AKIA[0-9A-Z]{12,}", text)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)


# ---- lane E's READY condition 2: no read touches a sealed column -------------------------------------------------


def test_bld_a257_the_deny_list_covers_every_sealed_column_and_worker_only_table() -> None:
    """The scan's deny list is read from the migrations, so a new sealed column or worker-only table joins it."""
    columns, tables = bytea_columns(), web_revoked_tables()
    assert {
        "text_encrypted",
        "note_encrypted",
        "lead_reason_encrypted",
        "value_encrypted",
        "value_hmac",
    } <= columns
    assert {"idea_words_sealed", "pseudonym_vault", "llm_cache", "voice_notes", "voice_streams"} <= tables
    # Every table the pinned privilege test hides from the web role is revoked in a migration the parse reads.
    assert tables >= HIDDEN_FROM_WEB
    deny = deny_list()
    assert PLAIN_TEXT.issubset(deny) and SEALED_TABLES.issubset(deny) and deny >= HIDDEN_FROM_WEB


def test_bld_a257_the_reads_own_names_pass_the_deny_list() -> None:
    """The deny list's suffixes (`_reason`, `_note`, `_text`, `_name`, `_quote` and the sealed ones) never trip on
    a name the reads use: `answered_at`, `teamup_declined`, `draft_asks_declined` and the rest."""
    deny = deny_list()
    assert [w for w in sorted(ALLOWED) if denied(w, deny)] == []
    for w in ("answered_at", "teamup_declined", "draft_asks_declined", "checking_over_15_min", "from_status"):
        assert w in ALLOWED and not denied(w, deny)
    # The suffixes do catch what they are for.
    for w in ("decline_reason", "lead_note", "helper_text", "first_name", "source_quote", "note_encrypted"):
        assert denied(w, deny), w


@pytest.mark.parametrize("n", [0, 1, 2], ids=["send-to-sorted", "model-calls", "team-up"])
def test_bld_a257_no_read_touches_a_sealed_column(n: int) -> None:
    assert sealed_hits(reads()[n]) == []


@pytest.mark.parametrize(
    "bad",
    [
        "title",  # read 1 with the ideas' titles (bad_read)
        "lead_reason_encrypted",  # read 3 counting by the lead's sealed reason instead of `state = 'declined'`
        "idea_words_sealed",  # read 2 joined to the sharer's sealed words
        "after_note",  # a JSON key read out of a literal
    ],
)
def test_bld_a257_the_sealed_column_scan_fails_on_a_bad_read(bad: str) -> None:
    r1, r2, r3 = reads()
    built = {
        "title": bad_read(),
        "lead_reason_encrypted": r3.replace("r.state = 'declined'", "r.lead_reason_encrypted IS NOT NULL"),
        "idea_words_sealed": r2.replace(
            "FROM s JOIN llm_calls c",
            "FROM s JOIN llm_calls c JOIN idea_words_sealed w ON w.source_id = c.ref_id",
        ),
        "after_note": r1.replace(
            "AS since, ", "AS since, (SELECT max(after->>'note') FROM audit_log) AS n, ", 1
        ),
    }[bad]
    assert built not in (r1, r2, r3)  # the bad read really differs from the doc's
    expected = {"after_note": "note"}.get(bad, bad)
    assert expected in sealed_hits(built)


# ---- the allowlist (lane C's review): only the identifiers the reads need ----------------------------------------


@pytest.mark.parametrize("n", [0, 1, 2], ids=["send-to-sorted", "model-calls", "team-up"])
def test_bld_a257_every_identifier_is_on_the_allowlist(n: int) -> None:
    assert not_allowed(reads()[n]) == []


def test_bld_a257_the_allowlist_is_only_what_the_reads_use() -> None:
    """No spare entry: every allowed name is used by at least one of the three reads."""
    used = {
        w for sql in reads() for w in re.findall(r"[a-z_][a-z0-9_]*", re.sub(r"'[^']*'", "''", sql).lower())
    }
    assert used == ALLOWED
    assert set(COLUMNS[0] + COLUMNS[2]) | {"calls", "p50_s", "p95_s", "max_s"} <= ALIASES


@pytest.mark.parametrize(
    ("bad", "names"),
    [
        ("i.title from ideas", {"i", "ideas", "title", "string_agg"}),
        ("first_name", {"u", "users", "first_name", "who"}),
        ("r.lead_reason_encrypted", {"lead_reason_encrypted", "not"}),
        ("c.ref_id", {"ref_id"}),
    ],
)
def test_bld_a257_the_allowlist_fails_on_a_bad_read_naming_the_identifier(bad: str, names: set[str]) -> None:
    r1, r2, r3 = reads()
    built = {
        "i.title from ideas": bad_read(),
        "first_name": r1.replace(
            "AS since, ", "AS since, (SELECT max(u.first_name) FROM users u) AS who, ", 1
        ),
        "r.lead_reason_encrypted": r3.replace(
            "r.state = 'declined'", "r.lead_reason_encrypted IS NOT NULL", 1
        ),
        "c.ref_id": r2.replace("SELECT c.agent, c.outcome, ", "SELECT c.agent, c.outcome, c.ref_id, ", 1),
    }[bad]
    assert built not in (r1, r2, r3)  # the bad read really differs from the doc's
    assert set(not_allowed(built)) == names
