"""HR directory import (§3.1 "HR directory sync"; AT-B2-03). One CSV in, one transaction.

CSV header: employee_id,name,email,department,job_title,location,manager_employee_id

- Upserts users by `emp_id_hash` (the raw employee ID is never stored) and gives new users a contributor code.
- Maps department → LOB and job title → role family from the company repo's taxonomy.
- An unmapped department or title opens (or refreshes) one `taxonomy_proposal` review item per distinct value.
- A user from an earlier import who is missing from this one becomes inactive, never deleted.
- Refuses a file that would deactivate more than half of today's active users, unless forced: a truncated
  export must not switch off the organisation.

python -m identity.hr_import <file.csv> [--repo <company repo>] [--force]
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

from psycopg.types.json import Jsonb

from core.config import get_settings
from core.db import Conn, connect
from core.logging import get_logger
from identity.codes import assign_contributor_code, emp_id_hash
from identity.taxonomy_map import TaxonomyMap, load

log = get_logger("identity.hr_import")

HEADER = ["employee_id", "name", "email", "department", "job_title", "location", "manager_employee_id"]
MAX_DEACTIVATE_SHARE = 0.5


class ImportRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class HrRow:
    employee_id: str
    name: str
    email: str
    department: str
    job_title: str
    location: str
    manager_employee_id: str


@dataclass
class ImportResult:
    rows: int = 0
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    unmapped_departments: dict[str, int] = field(default_factory=dict)
    unmapped_titles: dict[str, int] = field(default_factory=dict)
    proposals_opened: int = 0


def read_csv(path: Path) -> list[HrRow]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or [f.strip() for f in reader.fieldnames] != HEADER:
            raise ValueError(f"HR CSV header must be exactly: {','.join(HEADER)}")
        rows = []
        for n, raw in enumerate(reader, start=2):
            values = {k: (raw.get(k) or "").strip() for k in HEADER}
            if not values["employee_id"] or not values["email"] or not values["name"]:
                raise ValueError(f"line {n}: employee_id, name and email are required")
            rows.append(HrRow(**values))
    ids = [r.employee_id.upper() for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("HR CSV has the same employee_id more than once")
    return rows


def _open_proposal(conn: Conn, kind: str, value: str, count: int) -> bool:
    """One open taxonomy proposal per (kind, value); refresh the count if it is already open."""
    ref = f"{kind}:{value}"
    row = conn.execute(
        "SELECT id FROM review_items WHERE item_type = 'taxonomy_proposal' AND ref_id = %s "
        "AND state IN ('open', 'in_progress')",
        (ref,),
    ).fetchone()
    proposal = {"kind": kind, "value": value, "people": count, "source": "hr_import"}
    if row:
        conn.execute("UPDATE review_items SET proposal = %s WHERE id = %s", (Jsonb(proposal), row["id"]))
        return False
    conn.execute(
        "INSERT INTO review_items (item_type, ref_id, proposal, reasons) VALUES ('taxonomy_proposal', %s, %s, %s)",
        (ref, Jsonb(proposal), Jsonb({"why": f"no {kind.replace('_', ' ')} mapping in the taxonomy"})),
    )
    return True


def import_rows(conn: Conn, rows: list[HrRow], tax: TaxonomyMap, *, force: bool = False) -> ImportResult:
    result = ImportResult(rows=len(rows))
    with conn.transaction():
        active_before = conn.execute(
            "SELECT count(*) AS n FROM users WHERE source = 'hr' AND active"
        ).fetchone()["n"]  # type: ignore[index]
        hashes = {r.employee_id: emp_id_hash(r.employee_id) for r in rows}
        would_deactivate = conn.execute(
            "SELECT count(*) AS n FROM users WHERE source = 'hr' AND active AND NOT (emp_id_hash = ANY(%s))",
            (list(hashes.values()),),
        ).fetchone()["n"]  # type: ignore[index]
        if not force and active_before and would_deactivate / active_before > MAX_DEACTIVATE_SHARE:
            raise ImportRefused(
                f"this file would deactivate {would_deactivate} of {active_before} active users; "
                "check the export or re-run with --force"
            )

        ids_by_hash: dict[str, str] = {}
        for r in rows:
            lob = tax.lob_for(r.department)
            role = tax.role_for(r.job_title)
            if lob is None and r.department:
                result.unmapped_departments[r.department] = (
                    result.unmapped_departments.get(r.department, 0) + 1
                )
            if role is None and r.job_title:
                result.unmapped_titles[r.job_title] = result.unmapped_titles.get(r.job_title, 0) + 1
            row = conn.execute(
                """
                INSERT INTO users (emp_id_hash, name, email, lob_id, role_title, role_family, location,
                                   hr_department, hr_job_title, active, source, last_seen_in_hr_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true, 'hr', now())
                ON CONFLICT (emp_id_hash) DO UPDATE SET
                  name = EXCLUDED.name, email = EXCLUDED.email, lob_id = EXCLUDED.lob_id,
                  role_title = EXCLUDED.role_title, role_family = EXCLUDED.role_family,
                  location = EXCLUDED.location, hr_department = EXCLUDED.hr_department,
                  hr_job_title = EXCLUDED.hr_job_title, active = true, source = 'hr',
                  last_seen_in_hr_at = now()
                RETURNING id, (xmax = 0) AS inserted
                """,
                (
                    hashes[r.employee_id], r.name, r.email.lower(), lob, r.job_title or None, role,
                    r.location or None, r.department or None, r.job_title or None,
                ),
            ).fetchone()  # fmt: skip
            assert row is not None
            ids_by_hash[hashes[r.employee_id]] = str(row["id"])
            if row["inserted"]:
                result.created += 1
            else:
                result.updated += 1
            assign_contributor_code(conn, str(row["id"]), r.employee_id)

        for r in rows:
            manager = ids_by_hash.get(emp_id_hash(r.manager_employee_id)) if r.manager_employee_id else None
            conn.execute(
                "UPDATE users SET manager_user_id = %s WHERE id = %s",
                (manager, ids_by_hash[hashes[r.employee_id]]),
            )

        deactivated = conn.execute(
            "UPDATE users SET active = false WHERE source = 'hr' AND active AND NOT (emp_id_hash = ANY(%s))",
            (list(hashes.values()),),
        )
        result.deactivated = deactivated.rowcount

        for kind, values in (
            ("hr_department", result.unmapped_departments),
            ("job_title", result.unmapped_titles),
        ):
            for value, count in values.items():
                if _open_proposal(conn, kind, value, count):
                    result.proposals_opened += 1

    log.info(
        "hr_import.done",
        row_count=result.rows,
        created_count=result.created,
        updated_count=result.updated,
        deactivated_count=result.deactivated,
        unmapped_department_count=len(result.unmapped_departments),
        unmapped_role_count=len(result.unmapped_titles),
        proposals_opened=result.proposals_opened,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import the HR directory CSV.")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--repo", type=Path, default=None, help="company repo (default: COMPANY_REPO_PATH)")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    tax = load(args.repo or Path(get_settings().company_repo_path))
    rows = read_csv(args.csv)
    with connect(autocommit=True) as conn:
        try:
            r = import_rows(conn, rows, tax, force=args.force)
        except ImportRefused as exc:
            print(f"refused: {exc}")
            return 2
    print(
        f"hr import: {r.rows} rows, {r.created} created, {r.updated} updated, {r.deactivated} deactivated, "
        f"{len(r.unmapped_departments)} unmapped departments, {len(r.unmapped_titles)} unmapped titles, "
        f"{r.proposals_opened} proposals opened"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
