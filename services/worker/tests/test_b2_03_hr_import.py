"""AT-B2-03: HR CSV import upserts users and maps department to LOB and job title to role family using the
seed taxonomy; unmapped values create a `taxonomy_proposal` review item; a user missing from the next import
becomes inactive, not deleted."""

import csv
from pathlib import Path
from typing import Any

import generators as g
import pytest

from bootstrap.synthetic_hr import DOMAIN, generate
from identity.codes import emp_id_hash
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
