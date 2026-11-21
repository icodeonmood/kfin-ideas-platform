"""HR import rows are read as HR wrote them, or refused by line (BLD-A238; L-AUTH.rules/6, the directory).

From the read-only r3 review (`install-hr-csv-silent-column-shift`): header names with stray spaces now key the rows,
so no field reads as empty; a row with extra or missing fields (an unquoted comma in a name shifts every value after
it) and an email without exactly one `@` are refused. Every message names the line of HR's file where the row ends,
the reader's own count, and never a value. Nothing reaches the database (`main` exits 4).

Unit level only: `read_stream` on `io.StringIO`; `main` with the database stubbed. No stack, no docker, no make.
Synthetic people only (SYN- IDs, @kfintech.example).
"""

from __future__ import annotations

import io
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from identity import hr_import
from identity.hr_import import HEADER, ImportResult, read_stream
from tests import helpers

PEOPLE = [
    {
        "employee_id": "SYN-91001",
        "name": "Ishaan Vermani",
        "email": "ishaan.vermani@kfintech.example",
        "department": "MF Operations",
        "job_title": "Head - Operations",
        "location": "Hyderabad",
        "manager_employee_id": "",
    },
    {
        "employee_id": "SYN-91002",
        "name": "Rhea Kulkarnee",
        "email": "rhea.kulkarnee@kfintech.example",
        "department": "Engineering",
        "job_title": "QA Engineer",
        "location": "Pune",
        "manager_employee_id": "SYN-91001",
    },
    {
        "employee_id": "SYN-91003",
        "name": "Tarun Mehrotte",
        "email": "tarun.mehrotte@kfintech.example",
        "department": "Contact Centre",
        "job_title": "Investor Service Associate",
        "location": "Jaipur",
        "manager_employee_id": "SYN-91002",
    },
]
EXPECTED = "expected 7 fields"
NOT_AN_ADDRESS = "email is not an address (it needs exactly one @)"


def _line(person: dict[str, str]) -> str:
    return ",".join(person[k] for k in HEADER)


def _file(*lines: str, header: str = ",".join(HEADER)) -> io.StringIO:
    return io.StringIO("\n".join([header, *lines]) + "\n", newline="")


def _values(people: list[dict[str, str]]) -> list[str]:
    """Every value a row holds, and the parts of each email, that a message must never carry."""
    out = [v for p in people for v in p.values() if v]
    out += [part for p in people for part in p["email"].split("@") if part]
    return out


def _refused(fh: io.StringIO) -> str:
    with pytest.raises(ValueError) as caught:
        read_stream(fh)
    return str(caught.value)


# ---- 1. Header names are stripped, so the row keys match --------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        "employee_id, name, email, department, job_title, location, manager_employee_id",
        "employee_id,name,email,department ,job_title,location,manager_employee_id ",
        " employee_id ,\tname,email,department,job_title,location , manager_employee_id",
    ],
)
def test_a238_l_auth_rules_6_spaced_header_names_key_every_field(header: str) -> None:
    """The review's case: `department ` or `manager_employee_id ` passed the check, then read empty on every row."""
    rows = read_stream(_file(*(_line(p) for p in PEOPLE), header=header))
    assert [(r.employee_id, r.department, r.location, r.manager_employee_id) for r in rows] == [
        (p["employee_id"], p["department"], p["location"], p["manager_employee_id"]) for p in PEOPLE
    ]
    assert [r.line for r in rows] == [2, 3, 4]


def test_a238_a_header_that_differs_by_more_than_spaces_is_still_refused() -> None:
    message = _refused(_file(_line(PEOPLE[0]), header=",".join(HEADER).replace("location", "city")))
    assert message == f"HR CSV header must be exactly: {','.join(HEADER)}"


def test_a238_values_are_still_read_stripped_and_line_never_compares() -> None:
    spaced = {k: f" {v} " if v else v for k, v in PEOPLE[1].items()}
    [row] = read_stream(_file(_line(spaced)))
    assert (row.name, row.email, row.department) == (
        PEOPLE[1]["name"],
        PEOPLE[1]["email"],
        PEOPLE[1]["department"],
    )
    same: dict[str, Any] = dict(PEOPLE[1], line=99)
    assert row.line == 2 and row == hr_import.HrRow(**same)  # line is not part of a row's equality


# ---- 2. Extra or missing fields, and an email without exactly one @ ---------------------------------------------


def test_a238_l_auth_rules_6_an_unquoted_comma_in_a_name_is_refused_not_shifted() -> None:
    """The review's case: `Kulkarnee, Rhea` unquoted put the email under department and the name under email."""
    shifted = dict(PEOPLE[1], name="Kulkarnee, Rhea")
    message = _refused(_file(_line(PEOPLE[0]), _line(shifted), _line(PEOPLE[2])))
    assert message == f"line 3: {EXPECTED}, found 8"


def test_a238_extra_empty_fields_are_refused_too() -> None:
    message = _refused(_file(_line(PEOPLE[0]) + ",,", _line(PEOPLE[1])))
    assert message == f"line 2: {EXPECTED}, found 9"


@pytest.mark.parametrize(("keep", "found"), [(5, 5), (6, 6), (1, 1)])
def test_a238_l_auth_rules_6_a_short_row_is_refused(keep: int, found: int) -> None:
    short = ",".join(PEOPLE[2][k] for k in HEADER[:keep])
    message = _refused(_file(_line(PEOPLE[0]), _line(PEOPLE[1]), short))
    assert message == f"line 4: {EXPECTED}, found {found}"


def test_a238_the_field_count_is_checked_before_the_required_fields() -> None:
    """A short row with no email is named for its fields: the missing email may only be a shifted value."""
    message = _refused(_file(",".join([PEOPLE[0]["employee_id"], PEOPLE[0]["name"]])))
    assert message == f"line 2: {EXPECTED}, found 2"


@pytest.mark.parametrize(
    "email",
    [
        "ishaan.vermani.kfintech.example",  # no @
        "ishaan.vermani@kfintech@example",  # two
        "ishaan@vermani@kfintech.example",
        "@@",
    ],
)
def test_a238_l_auth_rules_6_an_email_without_exactly_one_at_is_refused(email: str) -> None:
    bad = dict(PEOPLE[0], email=email)
    message = _refused(_file(_line(PEOPLE[1]), _line(bad)))
    assert message == f"line 3: {NOT_AN_ADDRESS}"
    assert email not in message


def test_a238_one_at_is_enough_for_the_shape_check() -> None:
    rows = read_stream(_file(_line(dict(PEOPLE[0], email="i.v@kfintech.example"))))
    assert rows[0].email == "i.v@kfintech.example"


# ---- Every message: a line number, and none of the row's values --------------------------------------------------


def _cases() -> list[tuple[str, io.StringIO]]:
    return [
        ("extra", _file(_line(PEOPLE[0]), _line(dict(PEOPLE[1], name="Kulkarnee, Rhea")))),
        ("missing", _file(_line(PEOPLE[0]), ",".join(PEOPLE[1][k] for k in HEADER[:4]))),
        ("no at", _file(_line(dict(PEOPLE[0], email=PEOPLE[0]["email"].replace("@", "."))))),
        ("two at", _file(_line(dict(PEOPLE[0], email=PEOPLE[0]["email"].replace(".", "@", 1))))),
        ("required", _file(_line(dict(PEOPLE[0], name="")))),
        ("multi-line", _file(_line(dict(PEOPLE[0], job_title='"Team Lead\nOperations"')), "SYN-91009,x")),
    ]


@pytest.mark.parametrize("case", [c for c, _ in _cases()])
def test_a238_every_message_names_a_line_and_no_value(case: str) -> None:
    fh = dict(_cases())[case]
    message = _refused(fh)
    assert re.fullmatch(r"line [0-9]+: [a-z0-9 ,_()@]+", message), message
    leaked = [v for v in [*_values(PEOPLE), "Kulkarnee", "Rhea", "Team Lead", "SYN-91009"] if v in message]
    assert not leaked


# ---- A quoted field with a line break: the line where the row ends ----------------------------------------------


def test_a238_after_a_quoted_line_break_the_extra_field_names_the_files_line() -> None:
    two_lines = dict(PEOPLE[0], job_title='"Team Lead\nOperations"')  # lines 2-3
    message = _refused(_file(_line(two_lines), _line(dict(PEOPLE[1], name="Kulkarnee, Rhea"))))
    assert message == f"line 4: {EXPECTED}, found 8"


def test_a238_after_a_quoted_line_break_the_bad_email_names_the_files_line() -> None:
    two_lines = dict(PEOPLE[0], job_title='"Team Lead\r\nOperations"')  # lines 2-3
    message = _refused(_file(_line(two_lines), _line(PEOPLE[1]), _line(dict(PEOPLE[2], email="tarun"))))
    assert message == f"line 5: {NOT_AN_ADDRESS}"


def test_a238_a_short_row_that_spans_two_lines_is_named_by_the_line_it_ends_on() -> None:
    short = ",".join([PEOPLE[1]["employee_id"], PEOPLE[1]["name"], '"two\nlines"'])  # lines 3-4
    message = _refused(_file(_line(PEOPLE[0]), short))
    assert message == f"line 4: {EXPECTED}, found 3"


def test_a238_each_row_carries_the_line_it_ends_on() -> None:
    two_lines = dict(PEOPLE[1], job_title='"QA\nEngineer"')  # lines 3-4
    rows = read_stream(_file(_line(PEOPLE[0]), _line(two_lines), _line(PEOPLE[2])))
    assert [r.line for r in rows] == [2, 4, 5]
    assert rows[1].job_title == "QA\nEngineer"


# ---- Through the command: exit 4, nothing reaches the database --------------------------------------------------


def test_a238_the_command_prints_the_line_and_exits_4_with_nothing_imported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], captured_logs: io.StringIO
) -> None:
    imported: list[Any] = []

    @contextmanager
    def connect(autocommit: bool = False) -> Iterator[object]:
        yield object()

    def import_rows(conn: Any, rows: Any, tax: Any, *, force: bool = False) -> ImportResult:
        imported.append(rows)
        return ImportResult()

    monkeypatch.setattr(hr_import, "load", lambda repo: object())
    monkeypatch.setattr(hr_import, "connect", connect)
    monkeypatch.setattr(hr_import, "import_rows", import_rows)
    shifted = dict(PEOPLE[1], name="Kulkarnee, Rhea")
    data = _file(_line(PEOPLE[0]), _line(shifted)).getvalue().encode("utf-8")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data), encoding="utf-8"))
    assert hr_import.main(["-", "--repo", str(helpers.SEED)]) == 4
    assert imported == []
    out = capsys.readouterr()
    assert out.out == "failed: line 3: expected 7 fields, found 8; nothing was changed\n"
    assert out.err == ""
    logs = captured_logs.getvalue()
    assert not [v for v in _values(PEOPLE) if v in out.out or v in logs]
