"""L-HIDE.files: customers' details in the text of a file (lane C, BLD-C105 to BLD-C107).

The file's text layer (OCR for images and scanned pages, cells for spreadsheets) goes through the same detection
and the same store as every other text (`hide.core.hide_into`): each value sealed in the vault under the idea's
scope, a `hidden_details` row per detail with `source = 'file'` and the attachment id, never the value anywhere
else. A file has no "your words" copy: `file` is not a sealed source.

What comes back is kinds and page numbers only, for the file row's two lines (`reference/copy/Edit.md`,
`reference/copy/DeskIdea.md`):
- `found_line`: "Found a phone number on page 2. Nobody can open it until it’s hidden." (C-FILE.row, the
  personal-data state), shown to the person who added the file;
- `hidden_note`: "A phone number on page 2 is hidden." or "Folio hidden" (L-HIDE.files/4), the line the review
  desk's file rows and the sharer's answer rows read (`attachments.hidden_note`).
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from core.db import Conn
from hide import detect
from hide.core import hide_into

GATEKEEPER_MAX_CHARS = 8_000  # about 2,000 tokens: a longer file is checked by the patterns and names only
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
        starts.append(pos)
        where.append(location)
        parts.append(text)
        pos += len(text) + len(_SEP)
    return _SEP.join(parts), starts, where


def hide_file(conn: Conn, idea_uuid: str, pieces: list[tuple[str, str]], *, by: str, att_id: str) -> FileFinds:
    """Detect and store the details in a file's text, in the caller's transaction. Re-running it on the same file
    (a retry) keeps the same rows. `by` is the users.id of whoever added the file: the one person who may read the
    values. Returns kinds and pages only."""
    text, starts, where = _join([(w, t) for w, t in pieces if t and t.strip()])
    done = hide_into(
        conn, idea_uuid, text, by=by, source="file", source_id=att_id,
        gatekeeper=len(text) <= GATEKEEPER_MAX_CHARS, seal=False,
    )  # fmt: skip
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
        conn, idea_uuid, name, by=by, source="file", source_id=f"{att_id}{NAME_SUFFIX}", gatekeeper=False, seal=False
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
    """L-HIDE.files/4: "A phone number on page 2 is hidden." for one kind on one page; otherwise the labels, as the
    answer rows have it: "Folio hidden", "Folio number, PAN and phone number hidden"."""
    if not finds.count:
        return None
    kinds = finds.kinds
    if len(kinds) == 1 and finds.page is not None:
        noun = detect.noun(kinds[0], article=True)
        return f"{noun[0].upper()}{noun[1:]} on page {finds.page} is hidden."
    if len(kinds) == 1:
        return f"{detect.config().labels[kinds[0]]} hidden"
    return f"{detect.kinds_line(kinds)} hidden"
