"""L-LISTEN: the script the reviewer's browser reads aloud (BLD-B230), built from the masked idea."""

from __future__ import annotations

from desk import listen, worth
from desk.listen import Answer, FileLine
from desk.worth import Worth

TEXTS = {
    "summary": "Investors call the branch to ask why a redemption was rejected. Folio ••••89 was one of them.",
    "often": "About 40 calls a day at the Hyderabad branch.",
    "who": "Investors, and the branch team.",
}


def test_L_LISTEN_1_six_parts_in_the_ideas_order_with_chapters() -> None:
    s = listen.build(TEXTS)
    assert [p.part for p in s.parts] == ["summary", "often", "who", "cost", "evidence", "fix"]
    data = s.as_json()
    chapters = data["chapters"]
    assert isinstance(chapters, list) and chapters[0] == {"part": "summary", "at": 0.0}
    assert [c["at"] for c in chapters] == sorted(c["at"] for c in chapters)
    assert abs(sum(p.seconds for p in s.parts) + 0.5 * 5 - s.total_seconds) < 1e-9


def test_C_LISTEN_behaviour_6_hidden_details_are_read_as_hidden() -> None:
    first = listen.build(TEXTS).parts[0].text
    assert "Folio hidden was one of them." in first and "89" not in first and "•" not in first
    assert listen.speakable("PAN ••••4F, phone ••••21.") == "PAN hidden, phone hidden."


def test_L_LISTEN_2_empty_parts_files_worth_and_answers() -> None:
    s = listen.build(
        TEXTS,
        worth=Worth(hours_month=worth.parse("hours_month", "70 to 150")),
        files=[
            FileLine("A branch call log for November", "PDF", 3, "A phone number on page 2 is hidden."),
            FileLine(None, "PNG"),
        ],
        answers={"summary": [Answer("Kavya", "All of them. R07 is about half the calls.")]},
    )
    by = {p.part: p.text for p in s.parts}
    assert by["summary"].endswith("Kavya answered: All of them. R07 is about half the calls.")
    assert by["cost"] == "Time saved: 70 to 150 hours a month."
    assert by["evidence"] == (
        "Two files: A branch call log for November. A phone number on page 2 is hidden. A PNG."
    )
    assert by["fix"] == "No fix suggested. It was optional."


def test_L_LISTEN_3_the_version_changes_with_the_content() -> None:
    a, b = listen.build(TEXTS), listen.build({**TEXTS, "often": "About 50 calls a day."})
    assert a.version == listen.build(TEXTS).version and a.version != b.version


def test_L_LISTEN_1_the_servers_chapters_match_the_browser_engine() -> None:
    """Writes the vector apps/web/tests/unit/desk-listen.test.ts reads, and checks it is current."""
    import json
    from pathlib import Path

    s = listen.build(TEXTS, answers={"summary": [Answer("Kavya", "All of them.")]})
    vector = {"script": {"parts": s.as_json()["parts"]}, "chapters": s.as_json()["chapters"],
              "total_seconds": s.as_json()["total_seconds"]}  # fmt: skip
    path = Path(listen.__file__).with_name("listen_vector.json")
    assert json.loads(path.read_text()) == vector, "regenerate desk/listen_vector.json"
