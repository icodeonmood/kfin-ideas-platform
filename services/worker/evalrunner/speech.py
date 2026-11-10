"""Speech golden set for voice notes (DEC-096), `eval/golden/speech.jsonl`. Runs only with SPEECH_MODE=local, on the
server where the engine and its model files are (fake mode cannot measure an engine; hosted routes stay off).

Each case is a synthetic script in one language. Its recording, `eval/golden/speech/<id>.wav` (or .webm, .ogg,
.m4a), is made on the server by reading the script aloud or with a text-to-speech tool; a case with no recording
is skipped and counted. The recording goes through exactly what a voice note goes through: `gateway.speech`, then
`voice.numbers.normalise`, then `voice.service.leave_out_blocked`. A case passes when every expected phrase is in
the text (case-insensitive) and at least the expected number of values were left out. Gate: 80% of the cases that
are not advisory. Reports carry IDs and counts only, never the text.

Run with `python -m evalrunner.speech` (also called at the end of `make eval`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from core.config import REPO_ROOT, get_settings

ROOT = REPO_ROOT or Path.cwd()
GOLDEN = ROOT / "eval" / "golden"
FIXTURES = GOLDEN / "speech"
GATE = 0.8
MIME = {".wav": "audio/wav", ".webm": "audio/webm", ".ogg": "audio/ogg", ".m4a": "audio/mp4"}


def cases() -> list[dict[str, Any]]:
    lines = (GOLDEN / "speech.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def recording(case_id: str) -> tuple[bytes, str] | None:
    for suffix, mime in MIME.items():
        path = FIXTURES / f"{case_id}{suffix}"
        if path.exists():
            return path.read_bytes(), mime
    return None


def judge(case: dict[str, Any], text: str, left_out: int) -> list[str]:
    """What is wrong with one result (empty = pass). Names the expectation, never the heard text."""
    want = case["expected"]
    problems = [
        f"missing expected phrase {i + 1}"
        for i, phrase in enumerate(want["contains"])
        if phrase.lower() not in text.lower()
    ]
    if left_out < want.get("left_out_at_least", 0):
        problems.append(f"left out {left_out}, expected at least {want['left_out_at_least']}")
    return problems


def run() -> int:
    if get_settings().speech_mode != "local":
        print("speech: skipped (SPEECH_MODE is not local; the engine runs only on the server)")
        return 0
    from gateway import speech
    from voice.numbers import normalise
    from voice.service import leave_out_blocked

    results: list[dict[str, Any]] = []
    for case in cases():
        row: dict[str, Any] = {
            "id": case["id"],
            "language": case["language"],
            "advisory": bool(case.get("advisory")),
        }
        found = recording(case["id"])
        if found is None:
            row["skipped"] = "no recording"
        else:
            try:
                heard = speech.transcribe(*found)
            except speech.SpeechUnavailable as exc:
                row["error"] = exc.code
            else:
                text, left_out = leave_out_blocked(normalise(heard.text))
                row["problems"] = judge(case, text, left_out)
                row["passed"] = not row["problems"]
        results.append(row)
        print(
            f"speech {row['id']} {row['language']}: "
            + json.dumps({k: v for k, v in row.items() if k not in ("id", "language")})
        )
    gated = [r for r in results if not r["advisory"] and "skipped" not in r]
    rate = sum(1 for r in gated if r.get("passed")) / len(gated) if gated else 0.0
    skipped = sum(1 for r in results if "skipped" in r)
    print(f"speech: {rate:.0%} of {len(gated)} gated cases passed; {skipped} skipped for want of a recording")
    return 0 if gated and rate >= GATE else 1


if __name__ == "__main__":
    sys.exit(run())
