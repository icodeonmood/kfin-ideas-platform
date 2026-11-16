"""The listen script (L-LISTEN, C-LISTEN; BLD-B230): the idea read aloud, part by part, from the masked copy.

The reviewer's browser speaks the script with a local voice, so no audio leaves the device and no speech service
sees the idea. The script is built from the idea as the reviewer sees it: masked, with answers folded into their
parts (L-LISTEN/2). A hidden detail is read as "hidden" (C-LISTEN.behaviour/6), never as its last characters.
The sharer's raw words are not read. `version` changes whenever the script does, so a copy saved for offline is
replaced after an edit, an answer or a revision (L-LISTEN/3).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from desk.questions import PART_NAMES, PARTS, Part
from desk.worth import Worth, tiles

# Must match the browser engine's estimate (apps/web/src/lib/desk/listen.ts) so the server's lengths and the
# player's ticks agree.
CHARS_PER_SECOND = 15.0
PAUSE_SECONDS = 0.6

_MASK = re.compile(r"\s*•{2,}[^\s.,;:!?)]*")  # "Folio ••••89" → "Folio hidden"
_EMPTY: dict[str, str] = {
    "summary": "No summary yet.",
    "often": "Not given.",
    "who": "Not given.",
    "cost": "No figures given.",
    "evidence": "Nothing attached.",
    "fix": "No fix suggested. It was optional.",
}
_NUMBERS = ("No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten")


def speakable(masked: str) -> str:
    """Masked text as it should be heard: each hidden value becomes the word 'hidden'."""
    return re.sub(r"\s+", " ", _MASK.sub(" hidden", masked)).strip()


@dataclass(frozen=True)
class FileLine:
    """One file as the reviewer's page describes it: what it is ('a branch call log for November') when the file
    digest has said, else its kind and size."""

    description: str | None
    kind: str  # "PDF", "PNG", "Spreadsheet"…
    pages: int | None = None
    hidden: str | None = None  # "A phone number on page 2 is hidden."


@dataclass(frozen=True)
class Answer:
    by_first_name: str
    text: str  # masked


@dataclass(frozen=True)
class ScriptPart:
    part: Part
    title: str
    text: str
    seconds: float


@dataclass(frozen=True)
class Script:
    parts: tuple[ScriptPart, ...]
    total_seconds: float
    version: str

    def as_json(self) -> dict[str, object]:
        at, chapters = 0.0, []
        for p in self.parts:
            chapters.append({"part": p.part, "at": round(at, 1)})
            at += p.seconds
        return {
            "parts": [
                {"part": p.part, "title": p.title, "text": p.text, "seconds": round(p.seconds, 1)}
                for p in self.parts
            ],
            "chapters": chapters,
            "total_seconds": round(self.total_seconds, 1),
            "version": self.version,
        }


def _files_text(files: Sequence[FileLine]) -> str:
    if not files:
        return ""
    n = len(files)
    count = f"{_NUMBERS[n] if n < len(_NUMBERS) else n} file{'s' * (n != 1)}"
    lines = []
    for f in files:
        what = f.description or (
            f"A {f.kind}" + (f", {f.pages} page{'s' * (f.pages != 1)}" if f.pages else "")
        )
        lines.append(what.rstrip(".") + "." + (f" {f.hidden}" if f.hidden else ""))
    return f"{count}: " + " ".join(lines)


def _worth_text(worth: Worth | None) -> str:
    if worth is None:
        return ""
    said = [f"{t.label}: {t.value}." for t in tiles(worth, None) if t.value not in ("Not given", "No change")]
    return " ".join(said)


def estimate(text: str) -> float:
    return len(text) / CHARS_PER_SECOND + PAUSE_SECONDS


def build(
    texts: Mapping[str, str],
    *,
    worth: Worth | None = None,
    files: Sequence[FileLine] = (),
    answers: Mapping[str, Sequence[Answer]] | None = None,
) -> Script:
    """The six parts in the idea's order (L-LISTEN/1). `texts` holds each part's masked text as the reviewer sees
    it; What it's worth and Attached come from the figures and the files when not given as text."""
    answers = answers or {}
    out: list[ScriptPart] = []
    for part in PARTS:
        body = texts.get(part, "") or ""
        if part == "cost" and not body.strip():
            body = _worth_text(worth)
        if part == "evidence" and not body.strip():
            body = _files_text(files)
        spoken = speakable(body) or _EMPTY[part]
        for a in answers.get(part, ()):
            spoken += f" {a.by_first_name} answered: {speakable(a.text)}"
        line = f"{PART_NAMES[part]}. {spoken}"
        out.append(ScriptPart(part, PART_NAMES[part], line, estimate(line)))
    digest = hashlib.sha256("\n".join(p.text for p in out).encode()).hexdigest()[:16]
    return Script(tuple(out), sum(p.seconds for p in out), digest)
