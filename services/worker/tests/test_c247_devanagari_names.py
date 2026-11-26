"""Names written in Devanagari are tagged like names in Latin script (DEC-139 (d); lane C, BLD-C247): a table in the
repo (pii/names/devanagari.tsv), no new dependency; other scripts wait for r8. Pure unit tests, no database.
Every name here is a common, generic one from the table or made up for the test (synthetic data only)."""

from __future__ import annotations

import json
import tomllib
import unicodedata
from pathlib import Path

import pytest

from pii import detect

ROOT = Path(__file__).resolve().parents[3]
TABLE = ROOT / "services" / "worker" / "pii" / "names" / "devanagari.tsv"
DEVANAGARI = range(0x0900, 0x0980)
# Everyday Hindi words that are also names: never in the table, as English words are not in the Latin lists.
EVERYDAY = ("विकास", "आशा", "किरण", "कविता", "सीमा", "पूजा", "दीपक", "प्रकाश", "आकाश", "विजय", "रेखा", "रानी", "लाल",
            "आरती", "ज्योति", "भारत", "दिया",
            # From the review: words this product's own ideas use (innovative, new, satisfaction, pride, huge, all,
            # teenager, humility).
            "अभिनव", "नवीन", "संतोष", "गौरव", "विशाल", "अखिल", "किशोर", "विनय")  # fmt: skip


def _rows() -> list[tuple[str, str]]:
    lines = TABLE.read_text(encoding="utf-8").splitlines()
    return [tuple(ln.split("\t")) for ln in lines if ln.strip() and not ln.startswith("#")]  # type: ignore[misc]


def _found(text: str) -> list[str]:
    return [text[s:e] for s, e, _score in detect._devanagari_people(text)]


def test_bld_c247_the_table_is_well_formed() -> None:
    rows = _rows()
    kinds = {k for _w, k in rows}
    assert kinds == {"given", "surname", "stop"}
    for word, _kind in rows:
        assert word == unicodedata.normalize("NFC", word) and word == word.strip(), word
        assert all(ord(ch) in DEVANAGARI or ch in "‌‍" for ch in word), word
    per_kind = [(w, k) for w, k in rows]
    assert len(per_kind) == len(set(per_kind)), "a row appears twice"
    names = {w for w, k in rows if k != "stop"}
    stops = {w for w, k in rows if k == "stop"}
    assert not names & stops
    assert not names & set(EVERYDAY)
    assert (
        len([w for w, k in rows if k == "given"]) > 150 and len([w for w, k in rows if k == "surname"]) > 80
    )


def test_bld_c247_no_new_dependency() -> None:
    project = tomllib.loads((ROOT / "services" / "worker" / "pyproject.toml").read_text("utf-8"))
    deps = " ".join(project["project"]["dependencies"]).lower()
    for lib in ("indic", "transliterat", "polyglot", "stanza", "aksharamukha"):
        assert lib not in deps


@pytest.mark.parametrize(
    ("text", "names"),
    [
        # A given name takes one unknown word after it; a surname takes one before it.
        ("देविका रघुनाथन ने बताया कि फ़ॉर्म दो बार टाइप होता है", ["देविका रघुनाथन"]),
        ("कल अमित शर्मा जी से बात हुई।", ["अमित शर्मा"]),
        ("अमित खुरानिया ने कहा", ["अमित खुरानिया"]),
        ("वसुधा शर्मा ने कहा", ["वसुधा शर्मा"]),
        # A word that ends a name in Hindi is never pulled in.
        ("अमित से बात की", ["अमित"]),
        ("मैंने अमित, सुनीता और राहुल को बताया", ["अमित", "सुनीता", "राहुल"]),
        ("श्रीनिवास राव आए", ["श्रीनिवास राव"]),
        # Everyday words and sentences with no name.
        ("विकास की बात करो, आशा है", []),
        ("शाखा में हर बैंक बदलने का फॉर्म दो बार टाइप होता है, क्योंकि स्कैन साफ़ नहीं होता।", []),
        ("निवेशक का नंबर नौ आठ सात छह पांच चार तीन दो एक शून्य है, फॉर्म वापस आ गया।", []),
        # From the review of a160dac2.
        ("यह एक अभिनव विचार है", []),
        ("ग्राहक संतोष नहीं है", []),
        ("मैं डॉक्टर बनना चाहता था", []),  # डॉक्टर the job, not an honorific
        ("अमित प्रकाश शर्मा ने PAN भेजा", ["अमित प्रकाश शर्मा"]),  # one span, not two that overlap
        ("इरफान ने बताया", ["इरफान"]),  # typed without the nukta: the table has इरफ़ान
        ("इरफ़ान ने बताया", ["इरफ़ान"]),
        ("ज़ोया और फातिमा ने कहा", ["ज़ोया", "फातिमा"]),
        ("शर्माजी ने कहा", ["शर्माजी"]),  # जी joined: the name is found, and tagged whole
        ("अनिता पाण्डेय से पूछो", ["अनिता पाण्डेय"]),
    ],
)
def test_bld_c247_names_in_devanagari_are_found(text: str, names: list[str]) -> None:
    assert [n for n in _found(text) if n] == names


def test_bld_c247_an_honorific_marks_the_name_after_it_and_is_not_part_of_it() -> None:
    for text, name in (
        ("श्रीमती सुनीता ने कहा", "सुनीता"),
        ("डॉ. रघुनाथन को फ़ोन करो", "रघुनाथन"),
        ("श्री शर्मा जी आए", "शर्मा"),
        ("कुमारी वसुधा खुरानिया से पूछो", "वसुधा खुरानिया"),  # made up: not in the table, found by the honorific
        ("डॉ॰ वसुधा खुरानिया से पूछो", "वसुधा खुरानिया"),  # the abbreviation sign after डॉ
    ):
        found = _found(text)
        assert name in found, (text, found)
        assert not any(f.startswith(("श्री", "डॉ", "कुमारी")) for f in found), found


def test_bld_c247_a_word_joined_to_its_neighbour_by_a_danda_or_comma_is_not_pulled_in() -> None:
    assert _found("रघुनाथन। नमस्ते") == ["रघुनाथन"]
    assert _found("बैंक, रघुनाथन") == ["रघुनाथन"]


def test_bld_c247_the_speech_golden_scripts_hold_no_name() -> None:
    lines = (ROOT / "eval" / "golden" / "speech.jsonl").read_text("utf-8").splitlines()
    for case in (json.loads(ln) for ln in lines if ln.strip()):
        if case.get("language") == "hi":
            assert _found(case["script"]) == [], case["id"]


def test_bld_c247_the_recogniser_tags_them_before_any_model_call() -> None:
    """Through Presidio, as `pii.detect` runs before every model call (non-negotiable 2): PERSON, as Latin names."""
    text = "देविका रघुनाथन ने बताया कि Ravi Sharma भी आए थे"
    people = {f.value for f in detect._people(text, set()) if f.type == "PERSON"}
    assert "देविका रघुनाथन" in people and "Ravi Sharma" in people


def test_bld_c247_a_text_in_devanagari_only_is_tagged_too() -> None:
    """The review of a160dac2 (Critical): `detect` runs the name recognisers only on a text with a capital letter, and
    Devanagari has none. A sentence in Hindi alone, as most are, now goes through the table too (without the English
    NER model); this is the call `tagger.tag_text` makes before every model call (non-negotiable 2)."""
    d = detect.Directory().compile()
    text = "देविका रघुनाथन ने बताया कि फ़ॉर्म दो बार टाइप होता है"
    assert not any(ch.isupper() for ch in text)
    found = detect.detect(text, d, kfin_domains=[])
    assert [(f.type, f.value) for f in found] == [("PERSON", "देविका रघुनाथन")]
    assert detect.detect("विकास की बात करो, आशा है", d, kfin_domains=[]) == []
    assert detect.detect(text, d, kfin_domains=[], people=False) == []


def test_bld_c247_a_malformed_row_says_which_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "devanagari.tsv").write_text("# header\nअमित\tgiven\nशर्मा surname\n", encoding="utf-8")
    monkeypatch.setattr(detect, "NAMES_DIR", tmp_path)
    detect._deva_table.cache_clear()
    try:
        with pytest.raises(ValueError, match="line 3"):
            detect._deva_table()
    finally:
        monkeypatch.undo()
        detect._deva_table.cache_clear()
