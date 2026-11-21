"""AT-B2-03: HR CSV import upserts users and maps department to LOB and job title to role family using the
seed taxonomy; unmapped values create a `taxonomy_proposal` review item; a user missing from the next import
becomes inactive, not deleted."""

import csv
from pathlib import Path
from typing import Any

import generators as g
import pytest

from bootstrap.synthetic_hr import DOMAIN, generate
from identity import hr_import
from identity.codes import email_key_hash, emp_id_hash
from identity.hr_import import HEADER, ImportRefused, import_rows, read_csv
from identity.taxonomy_map import load

pytestmark = pytest.mark.stack


def _csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    return path


def _people() -> list[dict[str, str]]:
    rng = g.default_rng(77)
    spec = [
        ("SYN-80001", "MF Operations", "Head - Operations", ""),
        ("SYN-80002", "MF Operations", "Team Lead - Operations", "SYN-80001"),
        ("SYN-80003", "mf  operations", "Processing Associate", "SYN-80002"),  # case and spacing ignored
        ("SYN-80004", "Engineering", "QA Engineer", ""),
        ("SYN-80005", "Brand Studio", "Graphic Designer", ""),  # unmapped department and title
        ("SYN-80006", "Contact Centre", "Investor Service Associate", ""),
    ]
    return [
        {
            "employee_id": eid,
            "name": g.person_name(rng),
            "email": f"person.{eid[-3:]}@{DOMAIN}",
            "department": dep,
            "job_title": title,
            "location": "Hyderabad",
            "manager_employee_id": mgr,
        }
        for eid, dep, title, mgr in spec
    ]


def _user(db: Any, employee_id: str) -> dict[str, Any]:
    return db.execute(
        "SELECT u.*, m.contributor_code, mgr.emp_id_hash AS manager_hash FROM users u "
        "LEFT JOIN contributor_map m ON m.user_id = u.id LEFT JOIN users mgr ON mgr.id = u.manager_user_id "
        "WHERE u.emp_id_hash = %s",
        (emp_id_hash(employee_id),),
    ).fetchone()


def test_import_maps_proposes_and_deactivates(db: Any, company_repo: Path, tmp_path: Path) -> None:
    tax = load(company_repo)
    people = _people()
    r = import_rows(db, read_csv(_csv(tmp_path / "hr1.csv", people)), tax)
    assert (r.created, r.updated, r.deactivated) == (6, 0, 0)

    head, lead, assoc, qa, designer, service = (_user(db, p["employee_id"]) for p in people)
    assert (head["lob_id"], head["role_family"]) == ("LOB-mf", "ROLE-leader")
    assert (lead["role_family"], lead["manager_hash"]) == ("ROLE-ops-team-lead", emp_id_hash("SYN-80001"))
    assert (assoc["lob_id"], assoc["role_family"]) == ("LOB-mf", "ROLE-ops-executive")
    assert (qa["lob_id"], qa["role_family"]) == ("LOB-technology", "ROLE-qa-engineer")
    assert (service["lob_id"], service["role_family"]) == ("LOB-shared-operations", "ROLE-client-service")
    assert designer["lob_id"] is None and designer["role_family"] is None
    assert all(u["contributor_code"].startswith("CTR-") for u in (head, lead, assoc, qa, designer, service))

    proposals = {
        r["ref_id"]: r
        for r in db.execute(
            "SELECT ref_id, state FROM review_items WHERE item_type = 'taxonomy_proposal'"
        ).fetchall()
    }
    assert set(proposals) == {"hr_department:Brand Studio", "job_title:Graphic Designer"}

    # The raw employee ID is never stored anywhere in users.
    assert (
        db.execute("SELECT count(*) AS n FROM users WHERE users::text LIKE '%%SYN-8000%%'").fetchone()["n"]
        == 0
    )

    # Next import without the designer: inactive, not deleted; proposals are not duplicated.
    r2 = import_rows(
        db, read_csv(_csv(tmp_path / "hr2.csv", [p for p in people if p["employee_id"] != "SYN-80005"])), tax
    )
    assert (r2.created, r2.updated, r2.deactivated) == (0, 5, 1)
    gone = _user(db, "SYN-80005")
    assert gone is not None and gone["active"] is False
    assert gone["contributor_code"] == designer["contributor_code"]  # their ideas stay under the same code
    assert (
        db.execute("SELECT count(*) AS n FROM review_items WHERE item_type = 'taxonomy_proposal'").fetchone()[
            "n"
        ]
        == 2
    )

    # Coming back reactivates the same person.
    import_rows(db, read_csv(_csv(tmp_path / "hr3.csv", people)), tax)
    assert _user(db, "SYN-80005")["active"] is True


def test_truncated_file_is_refused(db: Any, company_repo: Path, tmp_path: Path) -> None:
    tax = load(company_repo)
    people = _people()
    import_rows(db, read_csv(_csv(tmp_path / "full.csv", people)), tax)
    short = read_csv(_csv(tmp_path / "short.csv", people[:1]))
    with pytest.raises(ImportRefused):
        import_rows(db, short, tax)
    assert db.execute("SELECT count(*) AS n FROM users WHERE active").fetchone()["n"] == 6
    assert import_rows(db, short, tax, force=True).deactivated == 5


def test_bad_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("emp,name\nSYN-1,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        read_csv(path)


def test_synthetic_directory_is_complete(company_repo: Path) -> None:
    people = generate(company_repo, seed=42)
    assert len(people) == 200
    assert len({p["employee_id"] for p in people}) == 200
    assert all(p["email"].endswith("@" + DOMAIN) for p in people)
    tax = load(company_repo)
    assert all(tax.lob_for(p["department"]) for p in people), "every synthetic department maps to a LOB"
    unmapped = {p["job_title"] for p in people if tax.role_for(p["job_title"]) is None}
    assert unmapped <= {"Marketing Manager", "Content Specialist"}
    assert generate(company_repo, seed=42) == people  # deterministic


def test_someone_who_signed_in_first_is_adopted_by_email(db: Any, company_repo: Path, tmp_path: Path) -> None:
    """Review finding: an email-keyed sign-in user must not make the next HR import collide on email."""
    from identity.codes import email_key_hash

    person = _people()[2]
    db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'sign_in')",
        (email_key_hash(person["email"]), person["name"], person["email"]),
    )
    r = import_rows(db, read_csv(_csv(tmp_path / "hr.csv", _people())), load(company_repo))
    assert (r.created, r.updated) == (5, 1)
    adopted = _user(db, person["employee_id"])
    assert adopted["source"] == "hr" and adopted["role_family"] == "ROLE-ops-executive"
    assert (
        db.execute("SELECT count(*) AS n FROM users WHERE lower(email) = %s", (person["email"],)).fetchone()[
            "n"
        ]
        == 1
    )


def test_duplicate_emails_are_rejected(tmp_path: Path) -> None:
    people = _people()
    people[1]["email"] = people[0]["email"].upper()
    with pytest.raises(ValueError, match="same email"):
        read_csv(_csv(tmp_path / "dup.csv", people))


# ---- BLD-A238: the email adoption takes only an email-keyed sign-in; anyone else holding the email is a refusal ----

REFUSED = (
    "this email already belongs to another person in the app (a different employee ID); "
    "check the employee_id and email with HR, nothing was changed"
)


def _signed_in(db: Any, key: str, person: dict[str, str]) -> None:
    """A row as the web app's first sign-in writes it (users.ts): source "sign_in", keyed by `key`."""
    db.execute(
        "INSERT INTO users (emp_id_hash, name, email, source) VALUES (%s, %s, %s, 'sign_in')",
        (key, person["name"], person["email"]),
    )


def _state(db: Any) -> dict[str, Any]:
    """Everything an import writes, to show a refusal changed nothing."""
    return {
        "users": db.execute(
            "SELECT u.id, u.emp_id_hash, u.name, u.email, u.source, u.active, u.lob_id, u.role_family, "
            "u.manager_user_id, u.last_seen_in_hr_at, m.contributor_code FROM users u "
            "LEFT JOIN contributor_map m ON m.user_id = u.id ORDER BY u.emp_id_hash"
        ).fetchall(),
        "proposals": db.execute(
            "SELECT ref_id, proposal FROM review_items WHERE item_type = 'taxonomy_proposal' ORDER BY ref_id"
        ).fetchall(),
    }


def _values(people: list[dict[str, str]]) -> list[str]:
    return [v for p in people for v in p.values() if v]


def test_a238_a_claim_keyed_sign_in_with_another_employee_id_is_not_rekeyed(
    db: Any, company_repo: Path, tmp_path: Path
) -> None:
    """Fix 3: Entra released an employeeId (SYN-89003) that is not HR's (SYN-80003) for the same email. The row
    keyed by the claim is someone's account and keeps its key; the import is refused at HR's line 4."""
    people = _people()
    claim = emp_id_hash("SYN-89003")
    _signed_in(db, claim, people[2])
    before = _state(db)
    with pytest.raises(ImportRefused) as caught:
        import_rows(db, read_csv(_csv(tmp_path / "hr.csv", people)), load(company_repo))
    assert str(caught.value) == f"line 4: {REFUSED}"
    assert not [v for v in _values(people) if v in str(caught.value)]
    assert _state(db) == before  # nothing changed: lines 2 and 3, written first, were rolled back too
    assert before["users"][0]["emp_id_hash"] == claim and before["users"][0]["source"] == "sign_in"
    assert _user(db, people[2]["employee_id"]) is None


def test_a238_a_leavers_account_is_not_given_to_a_joiner_with_the_same_email(
    db: Any, company_repo: Path, tmp_path: Path
) -> None:
    """Fix 3 (DEC-103, non-negotiable 4): HR reissues a leaver's email to a joiner. The leaver's row stays theirs,
    inactive, with their contributor code; the import is refused at the joiner's line, and nothing changes."""
    tax = load(company_repo)
    people = _people()
    import_rows(db, read_csv(_csv(tmp_path / "hr1.csv", people)), tax)
    stayers = [p for p in people if p["employee_id"] != "SYN-80005"]
    assert import_rows(db, read_csv(_csv(tmp_path / "hr2.csv", stayers)), tax).deactivated == 1
    leaver = _user(db, "SYN-80005")
    assert leaver["active"] is False

    joiner = dict(people[4], employee_id="SYN-80099", name=g.person_name(g.default_rng(78)))
    before = _state(db)
    with pytest.raises(ImportRefused) as caught:
        import_rows(db, read_csv(_csv(tmp_path / "hr3.csv", [*stayers, joiner])), tax)  # joiner on line 7
    assert str(caught.value) == f"line 7: {REFUSED}"
    assert not [v for v in _values([*people, joiner]) if v in str(caught.value)]
    assert _state(db) == before
    assert _user(db, "SYN-80099") is None
    still = _user(db, "SYN-80005")
    assert (still["id"], still["active"], still["contributor_code"]) == (
        leaver["id"],
        False,
        leaver["contributor_code"],
    )


def test_a238_a_sign_in_for_someone_hr_lists_with_another_email_is_refused_not_a_unique_violation(
    db: Any, company_repo: Path, tmp_path: Path
) -> None:
    """Fix 4, the r3 review's itwalk-03: SYN-80003 signed in without the employeeId claim under the address they
    use, while HR's row held another. HR corrects the file to that address: refused at line 4, nothing changed."""
    tax = load(company_repo)
    people = _people()
    import_rows(db, read_csv(_csv(tmp_path / "hr1.csv", people)), tax)
    address = f"p.003.signin@{DOMAIN}"
    _signed_in(db, email_key_hash(address), dict(people[2], email=address))
    corrected = [dict(p) for p in people]
    corrected[2]["email"] = address
    before = _state(db)
    with pytest.raises(ImportRefused) as caught:
        import_rows(db, read_csv(_csv(tmp_path / "hr2.csv", corrected)), tax)
    assert str(caught.value) == f"line 4: {REFUSED}"
    assert _state(db) == before


def test_a238_the_command_prints_refused_with_the_line_and_no_value(
    db: Any,
    company_repo: Path,
    tmp_path: Path,
    test_database: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    captured_logs: Any,
) -> None:
    """Fix 4 through `main`: `refused: line N: …`, exit 2, never `UniqueViolation`, no name, email or ID."""
    from core.db import connect
    from tests import helpers

    people = _people()
    _signed_in(db, emp_id_hash("SYN-89003"), people[2])
    monkeypatch.setattr(hr_import, "connect", lambda **kw: connect(helpers.db_url(test_database), **kw))
    path = _csv(tmp_path / "hr.csv", people)
    assert hr_import.main([str(path), "--repo", str(company_repo)]) == 2
    out = capsys.readouterr()
    assert out.out == f"refused: line 4: {REFUSED}\n"
    assert "UniqueViolation" not in out.out + out.err
    logs = captured_logs.getvalue()
    assert not [v for v in _values(people) if v in out.out or v in out.err or v in logs]
    assert db.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1
