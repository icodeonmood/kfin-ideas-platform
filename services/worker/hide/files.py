"""L-HIDE.files: customers' details in the text of a file (lane C, BLD-C105 to BLD-C107).

The file's text layer (OCR for images and scanned pages, cells for spreadsheets) goes through the same detection
and the same store as every other text (`hide.core.hide_into`): each value sealed in the vault under the idea's
scope, a `hidden_details` row per detail with `source = 'file'` and the attachment id, never the value anywhere
else. A file has no "your words" copy: `file` is not a sealed source.

The gatekeeper reads every file, however long (non-negotiable 4, DEC-103): `gate_for` asks it about the text one
piece at a time (about 8,000 characters, overlapping so a name cut by a boundary is whole in the next piece), each
piece through the gateway (`run_agent`, which tags the patterns' finds before sending), and every value it names is
then hidden wherever it appears in the file. When it cannot run, the file waits (`GatekeeperWaits`): the check job
tries again, and the file is never `checked` on the patterns alone. That holds whoever switched `ai.all` or
`agent.gatekeeper` off, a person or a process: a file never skips the gatekeeper, so it is never opened by the crew
without it (BLD-C107, lane E's check of non-negotiable 4, 18 Nov).

What comes back is kinds and page numbers only, for the file row's lines (`reference/copy/Edit.md`,
`reference/copy/DeskIdea.md`):
- `found_line`: "Found a phone number on page 2. Nobody can open it until it’s hidden." (C-FILE.row, the
  personal-data state), shown to the person who added the file;
- `hidden_note`: "A phone number on page 2 is hidden." or "Folio hidden" (L-HIDE.files/4), only once a black-out
  has hidden the regions in the stored copy ("Hide it for me", not built: DEC-107). A file with a detail found and
  nothing blacked out has no hidden note.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from core.db import Conn
from hide import detect
from hide.core import hide_into, scope_for

CHUNK_CHARS = 8_000  # about 2,000 tokens: what the gatekeeper reads at once
CHUNK_OVERLAP = 200  # a name or a number cut by a piece's end is whole at the start of the next
GATEKEEPER_SWITCHES = ("ai.all", "agent.gatekeeper")
_SEP = "\n\n"
_PAGE = re.compile(r"^page (\d+)\b")
NAME_SUFFIX = ":name"  # the file name's details are stored under `<attachment id>:name`


@dataclass(frozen=True)
class FileFinds:
    """What the check hid in one file: each detail's kind and page (None when the place is not a page)."""

    found: list[tuple[str, int | None]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.found)

    @property
    def kinds(self) -> list[str]:
        return list(dict.fromkeys(k for k, _ in self.found))

    @property
    def page(self) -> int | None:
        """The one page every detail is on, if there is exactly one."""
        pages = {p for _, p in self.found}
        return next(iter(pages)) if len(pages) == 1 else None

    def codes(self) -> list[dict[str, object]]:
        """For `attachments.checks`: kinds and pages only, never a value or the text around it."""
        return [{"kind": k, "page": p} for k, p in self.found]

    @classmethod
    def from_codes(cls, codes: object) -> FileFinds:
        out: list[tuple[str, int | None]] = []
        for c in codes if isinstance(codes, list) else []:
            if isinstance(c, dict) and c.get("kind") in detect.KINDS:
                page = c.get("page")
                out.append((str(c["kind"]), int(page) if isinstance(page, int) else None))
        return cls(out)


def page_of(location: str) -> int | None:
    """ "page 2", "page 2 comment", "page 2 (scanned)" -> 2; anything else (a slide, a cell, a ZIP member) -> None."""
    m = _PAGE.match(location)
    return int(m.group(1)) if m else None


def _join(pieces: list[tuple[str, str]]) -> tuple[str, list[int], list[str]]:
    starts: list[int] = []
    where: list[str] = []
    parts: list[str] = []
    pos = 0
    for location, text in pieces:
        if not (text and text.strip()):
            continue
        starts.append(pos)
        where.append(location)
        parts.append(text)
        pos += len(text) + len(_SEP)
    return _SEP.join(parts), starts, where


def text_of(pieces: list[tuple[str, str]]) -> str:
    """The file's text as hide reads it: its pieces joined, empty ones left out."""
    return _join(pieces)[0]


def chunks(text: str) -> list[tuple[int, str]]:
    """(offset, piece) for the gatekeeper: pieces of at most `CHUNK_CHARS`, each overlapping the one before by
    `CHUNK_OVERLAP`."""
    if not text.strip():
        return []
    out: list[tuple[int, str]] = []
    start = 0
    while True:
        out.append((start, text[start : start + CHUNK_CHARS]))
        if start + CHUNK_CHARS >= len(text):
            return out
        start += CHUNK_CHARS - CHUNK_OVERLAP


class GatekeeperWaits(Exception):
    """The gatekeeper could not read a file's text (the gateway failed or timed out, or is held off by its own
    automatic switch-off or the day's budget), and no person switched it off: the file stays `checking` and the
    check job tries again. Carries the gateway's code only."""


def switched_off_by_person(changed_by: str | None) -> bool:
    """True only for a person's switch-off. Every automatic actor writes `changed_by` as `process:<name>` (the
    gateway's own switch-off, the eval runner on a golden-set regression, the watcher), and an unknown actor (NULL)
    is treated as automatic too: an automatic switch-off is a failure to wait out, never a choice to skip the
    gatekeeper (non-negotiable 4, DEC-103, BLD-C107)."""
    return bool(changed_by) and not str(changed_by).startswith("process:")


def _off_on_purpose(conn: Conn) -> bool | None:
    """None while `ai.all` and `agent.gatekeeper` are both on; True when a person switched one of them off; False
    when only an automatic switch-off (the gateway, the eval runner, the watcher, or an unknown actor) holds it off
    (that is a failure, not a choice)."""
    from core import killswitch

    if all(killswitch.is_on(name, conn) for name in GATEKEEPER_SWITCHES):
        return None
    rows = conn.execute(
        "SELECT changed_by FROM kill_switches WHERE name = ANY(%s) AND state = 'off'",
        (list(GATEKEEPER_SWITCHES),),
    ).fetchall()
    return any(switched_off_by_person(r["changed_by"]) for r in rows)


def _placed(text: str, named: dict[str, str], *, switched_off: bool = False) -> detect.Gate:
    """Every value the gatekeeper named, wherever it appears in the whole text (a piece names it once)."""
    found: dict[tuple[int, int, str], detect.Found] = {}
    for value, kind in named.items():
        for s, e in detect.occurrences(text, value):
            found.setdefault((s, e, kind), detect.Found(s, e, kind, value, "gatekeeper"))
    finds = sorted(found.values(), key=lambda f: (f.start, f.end))
    return detect.Gate(finds, "switched_off", True) if switched_off else detect.Gate(finds)


def gate_for(conn: Conn, idea_uuid: str, text: str) -> detect.Gate:
    """The gatekeeper's finds in a file's text, asked piece by piece (`chunks`), each value it names placed wherever
    it appears in the whole text. Call it before taking any lock: each piece is a model call.

    Raises `GatekeeperWaits` whenever the gatekeeper cannot read a piece: the gateway failed, or `ai.all` or
    `agent.gatekeeper` is switched off, whoever switched it (a person or a process). A file never skips the
    gatekeeper (non-negotiable 4): it waits in `checking` and the check job tries again."""

    def held() -> None:
        if _off_on_purpose(conn) is not None:  # switched off, by a person or a process: wait, never skip
            raise GatekeeperWaits("switched_off")

    held()
    scope = scope_for(idea_uuid)
    named: dict[str, str] = {}
    for _offset, piece in chunks(text):
        with conn.transaction():  # its own savepoint, as `hide_into` asks it (BLD-C067)
            gate = detect.gatekeeper_finds(conn, piece, scope)
        for f in gate.finds:
            named.setdefault(f.value, f.kind)
        held()  # switched off while the file was read
        if gate.skipped:
            raise GatekeeperWaits(gate.skipped)
    return _placed(text, named)


def hide_file(
    conn: Conn,
    idea_uuid: str,
    pieces: list[tuple[str, str]],
    *,
    by: str,
    att_id: str,
    gate: detect.Gate | None = None,
) -> FileFinds:
    """Detect and store the details in a file's text, in the caller's transaction. Re-running it on the same file
    (a retry) keeps the same rows. `by` is the users.id of whoever added the file: the one person who may read the
    values. `gate`: `gate_for` on this text, asked before the caller took its locks (asked here when not given; it
    may raise `GatekeeperWaits`). Returns kinds and pages only."""
    text, starts, where = _join(pieces)
    if gate is None:
        gate = gate_for(conn, idea_uuid, text)
    done = hide_into(conn, idea_uuid, text, by=by, source="file", source_id=att_id, seal=False, gate=gate)
    found: list[tuple[str, int | None]] = []
    for span in done.spans:
        i = bisect.bisect_right(starts, int(span["start"])) - 1
        found.append((str(span["kind"]), page_of(where[i]) if i >= 0 else None))
    return FileFinds(found)


def hide_name(conn: Conn, idea_uuid: str, name: str, *, by: str, att_id: str) -> str:
    """A file name or a link is shown on every row that lists the file: its details are hidden like any text
    (patterns, names and the idea's hidden values; no model call, so adding a file never waits on one). Returns the
    masked copy, which is what is stored and shown."""
    done = hide_into(
        conn,
        idea_uuid,
        name,
        by=by,
        source="file",
        source_id=f"{att_id}{NAME_SUFFIX}",
        gatekeeper=False,
        seal=False,
    )
    return done.masked


def forget(conn: Conn, att_id: str) -> None:
    """A removed file's details go with it (the vault keeps the idea's values for its other texts)."""
    conn.execute(
        "DELETE FROM hidden_details WHERE source = 'file' AND source_id = ANY(%s)",
        ([att_id, f"{att_id}{NAME_SUFFIX}"],),
    )


# ---- the words (reference/copy/Edit.md, DeskIdea.md; hide/config.yaml nouns, articles and labels) ----------------


def _listed(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def found_line(finds: FileFinds) -> str | None:
    """C-FILE.row, personal data found: "Found a phone number on page 2. Nobody can open it until it’s hidden."
    Several kinds are listed with their articles; the page is said only when every detail is on one page."""
    if not finds.count:
        return None
    what = _listed([detect.noun(k, article=True) for k in finds.kinds])
    where = f" on page {finds.page}" if finds.page is not None else ""
    return f"Found {what}{where}. Nobody can open it until it’s hidden."


def hidden_note(finds: FileFinds) -> str | None:
    """L-HIDE.files/4, after a black-out only ("Hide it for me", not built: DEC-107): "A phone number on page 2 is
    hidden." for one kind on one page; otherwise the labels, as the answer rows have it: "Folio hidden", "Folio
    number, PAN and phone number hidden". Never for a file whose details were found and not blacked out."""
    if not finds.count:
        return None
    kinds = finds.kinds
    if len(kinds) == 1 and finds.page is not None:
        noun = detect.noun(kinds[0], article=True)
        return f"{noun[0].upper()}{noun[1:]} on page {finds.page} is hidden."
    if len(kinds) == 1:
        return f"{detect.config().labels[kinds[0]]} hidden"
    return f"{detect.kinds_line(kinds)} hidden"
