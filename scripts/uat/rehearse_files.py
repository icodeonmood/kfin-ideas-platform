"""BLD-A239: three synthetic files on FROM (launch-2026-11-20-r3) for the upgrade rehearsal, through r3's own code.

`scripts/uat/rehearse-upgrade.sh` (REHEARSE_APP_ENV=prod, phase `files-from`) pipes this file into FROM's running
worker, after the synthetic HR import:

    docker exec -i kfin-ideas-uat-rehearsal-worker-1 python - plant < scripts/uat/rehearse_files.py

It is never imported by the app. Each file goes in as the web app sends one: a draft by `draft.store.create` (behind
`POST /internal/drafts`), then the file by `attachments.files.accept` (behind `POST /internal/files`), as a synthetic
person (SYN-, `@kfintech.example`). r3's own worker then checks them, with AI off:

- D, dead by waits: a plain synthetic text file. Its check waits on the gatekeeper, so r3 ends it `upload_failed`
  (`check_failed`, no `gatekeeper` key, the quarantine copy kept) after its last try.
- W, waiting on its last try: the same, but its last try is 6 hours away, so r3 never runs it before the upgrade.
- V, a real failure: the EICAR antivirus test string (harmless), assembled here at run time, so the repo never
  holds it whole. r3's scanner ends it `infected`.

The one direct write is to the jobs table, a rehearsal-only shortcut for r3's 81-minute backoff: D's and W's
`file.check` job is set to its last try (`attempts = max_attempts - 1`), due now (D) or in 6 hours (W). Nothing is
written to `ideas` or `attachments` by hand.

Prints IDs and states only: never the file's text, its name or a person's name (non-negotiable 3). The lines
`files: <D|W|V> <file id> ...` are read back by the rehearsal; anything else it prints is for people.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from attachments import files, store
from core.config import get_settings
from core.db import connect
from desk.store import code_of
from draft.store import Device, Owner, create
from identity.codes import emp_id_hash

PEOPLE = {"D": "SYN-00010", "W": "SYN-00011", "V": "SYN-00012"}  # synthetic people from the HR file of 20
NAMES = {"D": "rehearsal-d.md", "W": "rehearsal-w.md", "V": "rehearsal-v.md"}
TEXT = {
    "D": b"Synthetic rehearsal file D. No personal data.\n",
    "W": b"Synthetic rehearsal file W. No personal data.\n",
}
EICAR_HALVES = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*")
LAST_TRY = {"D": "0 seconds", "W": "6 hours"}
DEVICE = Device.of("laptop", "rehearsal-a239")


class Stop(Exception):
    """The phase stops: the message names IDs and states only."""


def _person(conn: Any, employee_id: str) -> Owner:
    row = conn.execute(
        "SELECT id FROM users WHERE emp_id_hash = %s AND active", (emp_id_hash(employee_id),)
    ).fetchone()
    if row is None:
        raise Stop(f"{employee_id} is not an active person: did people-prod import the synthetic HR file?")
    user_id = str(row["id"])
    code = code_of(conn, user_id)
    if code is None:
        raise Stop(f"{employee_id} has no contributor code")
    return Owner(user_id, code)


def _data(which: str) -> bytes:
    return "".join(EICAR_HALVES).encode("ascii") if which == "V" else TEXT[which]


def _add(conn: Any, which: str) -> tuple[str, str]:
    """A draft for the person, then the file on it: (draft id, file id)."""
    owner = _person(conn, PEOPLE[which])
    draft_id, _ = create(conn, owner, DEVICE, channel="web")
    try:
        item = files.accept(
            conn, user_id=owner.user_id, name=NAMES[which], data=_data(which), draft_id=draft_id
        )
    except files.FileRefused as exc:
        raise Stop(f"{which}: r3 refused the file ({exc.status} {exc.code})") from None
    return draft_id, str(item["id"])


def _last_try(conn: Any, which: str, att_id: str) -> None:
    """The rehearsal-only shortcut (see the module's note): only a queued job is moved, so a try already running ends
    first and this one follows it."""
    deadline = time.monotonic() + 120
    while True:
        row = conn.execute(
            "UPDATE jobs SET attempts = max_attempts - 1, run_at = now() + %s::interval "
            "WHERE type = 'file.check' AND payload->>'attachment_id' = %s AND state = 'queued' RETURNING id",
            (LAST_TRY[which], att_id),
        ).fetchone()
        if row is not None:
            return
        if time.monotonic() > deadline:
            raise Stop(f"{which} {att_id}: its file.check job was not queued within 120 s")
        time.sleep(1)


def _row(conn: Any, att_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT file_state, checks, store_key FROM attachments WHERE id = %s", (att_id,)
    ).fetchone()
    if row is None:
        raise Stop(f"{att_id} is gone")
    return dict(row)


def _ended(conn: Any, which: str, att_id: str, seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while True:
        row = _row(conn, att_id)
        if row["file_state"] != "checking":
            return row
        if time.monotonic() > deadline:
            raise Stop(f"{which} {att_id}: still checking after {seconds} s")
        time.sleep(2)


def plant() -> None:
    quarantine = get_settings().s3_bucket_quarantine
    with connect(autocommit=True) as conn:
        made = {which: _add(conn, which) for which in ("D", "W", "V")}
        for which in ("D", "W"):
            _last_try(conn, which, made[which][1])
        for which, (draft_id, att_id) in made.items():
            print(f"files: {which} {att_id} on draft {draft_id} of {PEOPLE[which]}", flush=True)

        att = made["D"][1]
        d = _ended(conn, "D", att, 180)
        checks = d["checks"] or {}
        if d["file_state"] != "upload_failed" or checks.get("result") != "check_failed":
            raise Stop(
                f"D {att}: {d['file_state']} ({checks.get('result')}), not upload_failed (check_failed)"
            )
        if "gatekeeper" in checks:
            raise Stop(f"D {att}: its checks have a gatekeeper key")
        if not d["store_key"] or not store.exists(quarantine, d["store_key"]):
            raise Stop(f"D {att}: no quarantine copy")
        print(
            f"files: D {att} upload_failed (check_failed, no gatekeeper key, quarantine copy kept)",
            flush=True,
        )

        att = made["W"][1]
        w = _row(conn, att)
        if w["file_state"] != "checking":
            raise Stop(f"W {att}: {w['file_state']}, not checking")
        print(f"files: W {att} checking (its last try is in 6 hours)", flush=True)

        att = made["V"][1]
        v = _ended(conn, "V", att, 300)
        if v["file_state"] != "infected":
            raise Stop(f"V {att}: {v['file_state']}, not infected")
        print(f"files: V {att} infected", flush=True)


def main(argv: list[str]) -> int:
    if argv != ["plant"]:
        print("usage: python - plant < scripts/uat/rehearse_files.py", file=sys.stderr)
        return 2
    try:
        plant()
    except Stop as exc:
        print(f"STOPPED: files-from: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
