#!/usr/bin/env python3
"""CI rule (BLD-A161): decision IDs stay unique while several sessions add them in parallel.

Checks docs/DECISIONS.md, reading only the first cell of each table row:
- every DEC and BLD ID is well formed and used once;
- new build IDs carry a lane letter registered in the lanes table (BLD-A161, BLD-B230, BLD-C001);
- plain-number build IDs stop where lanes A and B left them, and lettered A and B IDs carry on after that.

Exit 0 = clean, 1 = a problem (one line each). Usage: python scripts/ci/check_decision_ids.py [DECISIONS.md]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Where the plain numbers stopped when lane letters came in. Lane A used BLD-001 to 199, lane B 200 to 299.
# Lettered IDs in these lanes continue after the last plain one, so BLD-A157 can never be mistaken for BLD-157.
PLAIN_STOP = {"A": (range(1, 200), 160), "B": (range(200, 300), 229)}

ROW = re.compile(r"^\|\s*([^|]*?)\s*\|")
DEC_ID = re.compile(r"^DEC-(\d{3,})$")
PLAIN_ID = re.compile(r"^BLD-(\d{3})$")
LANE_ID = re.compile(r"^BLD-([A-Z])(\d{3,})$")
LANE_LETTER = re.compile(r"^[A-Z]$")
HOW = "see the note at the top of docs/DECISIONS.md"


def problems(text: str) -> list[str]:
    found: list[str] = []
    seen: dict[str, int] = {}
    lanes: dict[str, int] = {}
    lettered: list[tuple[int, str, str, int]] = []

    for n, line in enumerate(text.splitlines(), 1):
        match = ROW.match(line)
        if not match:
            continue
        cell = match.group(1)
        if LANE_LETTER.match(cell):
            if cell in lanes:
                found.append(f"line {n}: lane {cell} is registered twice (first on line {lanes[cell]})")
            lanes.setdefault(cell, n)
            continue
        if not cell.startswith(("DEC-", "BLD-")):
            continue

        if dec := DEC_ID.match(cell):
            key = f"DEC-{int(dec.group(1))}"
        elif plain := PLAIN_ID.match(cell):
            number = int(plain.group(1))
            key = f"BLD-{number}"
            if not any(number in used and number <= stop for used, stop in PLAIN_STOP.values()):
                found.append(f"line {n}: {cell} has no lane letter; new build IDs look like BLD-C001 ({HOW})")
        elif lane := LANE_ID.match(cell):
            letter, number = lane.group(1), int(lane.group(2))
            key = f"BLD-{letter}{number}"
            lettered.append((n, cell, letter, number))
        else:
            found.append(f"line {n}: {cell} is not a decision ID (DEC-096, BLD-C001)")
            continue

        if key in seen:
            found.append(f"line {n}: {cell} is already used on line {seen[key]}")
        seen.setdefault(key, n)

    for n, cell, letter, number in lettered:
        if letter not in lanes:
            found.append(f"line {n}: {cell} uses lane {letter}, which is not in the lanes table ({HOW})")
        if letter in PLAIN_STOP and number <= PLAIN_STOP[letter][1]:
            found.append(
                f"line {n}: lane {letter} carries on from BLD-{letter}{PLAIN_STOP[letter][1] + 1}, not {cell}"
            )
    return found


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2] / "docs" / "DECISIONS.md"
    found = problems(path.read_text(encoding="utf-8"))
    for problem in found:
        print(f"{path.name} {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
