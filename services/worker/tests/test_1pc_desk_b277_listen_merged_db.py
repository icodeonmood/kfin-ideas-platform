"""BLD-B277 (L-LISTEN/2, L-MERGE.effects/3, C-LISTEN): the surviving idea's listen script reads the ideas merged
into it, as S-R2 lists them. Each part goes on, after the lead's words and answers, with "From Ravi’s idea: …"; a part
the merged idea left empty is not read for it. The script stays the same for every viewer, so a merged idea's file
that holds a customer detail (DEC-107), which S-R2 shows the desk with its marker, is never named. Its version
changes with the merge (L-LISTEN/3).

Synthetic people and files only (non-negotiable 11); lane B's and lane F's fixtures, cleaned up after each test."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.db import Conn
from desk import merging, reads
from tests import convo_fixtures as fx
from tests import desk_fixtures as f
from tests.desk_fixtures import clean_up_desk_rows  # noqa: F401 (autouse: removes what the helpers made)

NOW = f.at(16, 13)  # Monday 16 November 2026, 1 pm IST
KAVYA_SUMMARY = "Investors call the branch because the SMS gives a code, not a reason."  # desk_fixtures.idea
KAVYA_OFTEN = "About 40 calls a day at one branch."
RAVI_SUMMARY = "The redemption SMS shows R07 and nothing else, so investors ring the branch to ask."
RAVI_OFTEN = "About 15 calls a week at the Vizag branch."
OWN, FOUND = "vizag-call-log-nov.xlsx", "vizag-investor-letters.pdf"


@pytest.fixture
def repo(company_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    from core.config import get_settings

    monkeypatch.setenv("COMPANY_REPO_PATH", str(company_repo))
    get_settings.cache_clear()
    yield company_repo
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def cast(db: Conn, repo: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    _ = repo
    f.install_fake_notify(monkeypatch)
    kavya, ravi = f.person(db, "Kavya Menon"), f.person(db, "Ravi Nair")
    ravis = f.idea(
        db, ravi, title="Rejection SMS codes confuse investors", shared_at=f.at(15, 9), summary=RAVI_SUMMARY,
        often=RAVI_OFTEN,
    )  # fmt: skip
    fx.attachment(db, ravis, ravi, name=OWN, purpose="idea")
    fx.attachment(db, ravis, ravi, file_state="personal_data_found", name=FOUND, purpose="idea")
    return {
        "kavya": kavya, "ravi": ravi, "meera": f.person(db, "Meera Iyer", roles=("reviewer",)),
        "idea": f.idea(db, kavya), "ravis": ravis,
    }  # fmt: skip


def _parts(script: dict[str, Any]) -> dict[str, str]:
    return {p["part"]: p["text"] for p in script["parts"]}


def test_L_LISTEN_2_L_MERGE_effects_3_BLD_B277_the_surviving_idea_reads_its_merged_contribution(
    db: Conn, cast: dict[str, Any]
) -> None:
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    before = reads.listen_script(db, ref, meera)
    assert "Ravi" not in " ".join(_parts(before).values())

    merging.desk_merge(db, ref, meera,
                       {"other_idea_id": cast["ravis"]["idea_id"], "lead": "this",
                        "note": "You both found the same R07 calls."}, f.at(16, 12))  # fmt: skip
    after = reads.listen_script(db, ref, meera)
    said = _parts(after)
    assert said["summary"] == f"{KAVYA_SUMMARY} From Ravi’s idea: {RAVI_SUMMARY}"
    assert said["often"] == f"{KAVYA_OFTEN} From Ravi’s idea: {RAVI_OFTEN}"
    # the lead has no file of its own; Ravi's checked file is read, the one holding a customer detail never is
    assert said["evidence"] == f"Nothing attached. From Ravi’s idea: One file: {OWN}."
    assert FOUND not in " ".join(said.values())
    # parts Ravi's idea left empty are read for the lead alone
    assert said["who"] == "Not given." and said["fix"] == "No fix suggested. It was optional."
    assert [c["part"] for c in after["chapters"]] == [
        c["part"] for c in before["chapters"]
    ]  # still six parts
    assert after["version"] != before["version"]  # L-LISTEN/3: a saved copy is replaced


def test_L_MERGE_effects_3_BLD_B277_the_script_reads_each_contribution_as_S_R2_lists_it(
    db: Conn, cast: dict[str, Any]
) -> None:
    """The script and S-R2 read the same merged ideas: each contribution on the page is read under its sharer."""
    ref, meera = cast["idea"]["idea_id"], cast["meera"]["id"]
    merging.desk_merge(db, ref, meera,
                       {"other_idea_id": cast["ravis"]["idea_id"], "lead": "this",
                        "note": "You both found the same R07 calls."}, f.at(16, 12))  # fmt: skip
    page = reads.reviewer_idea(db, ref, meera, NOW)
    assert [c["sharer"]["first_name"] for c in page["contributions"]] == ["Ravi"]
    said = " ".join(_parts(reads.listen_script(db, ref, meera)).values())
    assert said.count("From Ravi’s idea:") == 3  # summary, often and evidence
