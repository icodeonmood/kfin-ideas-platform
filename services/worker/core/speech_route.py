"""Whether the speech route voice uses is ready (DEC-108, BLD-A185). One answer for the go/no-go report and the
startup smoke check, so they never disagree. Switch states and setting names only, never a value."""

from __future__ import annotations

from core.config import Settings


def key_set(s: Settings) -> bool:
    """The Sarvam key is in the worker's env. Lane C's Sarvam client names it `sarvam_api_key`; until c/sarvam is on
    main the setting is `speech_hosted_key`. Only whether it is set is ever read out."""
    name = "sarvam_api_key" if "sarvam_api_key" in type(s).model_fields else "speech_hosted_key"
    return bool(str(getattr(s, name, "")).strip())  # once renamed, only the name lane C's client reads counts


def voice_problem(
    voice_on: bool, hosted_on: bool, speech_mode: str, engine_url: str, approval: str, key: bool
) -> str | None:
    """None when voice can work as switched (off counts); otherwise what stops it."""
    if not voice_on:
        return None
    if speech_mode == "sarvam":
        missing = [
            what
            for what, ok in (
                ("speech.hosted off", hosted_on),
                ("no SPEECH_HOSTED_APPROVAL", bool(approval.strip())),
                ("no Sarvam key in the worker's env", key),
            )
            if not ok
        ]
        return (
            f"on with SPEECH_MODE sarvam but {', '.join(missing)}, so every recording is refused"
            if missing
            else None
        )
    if speech_mode == "local":
        return None if engine_url else "on with SPEECH_MODE local and no isolated speech service (BLD-C012)"
    return f"on with SPEECH_MODE {speech_mode or 'unset'}; set the Sarvam route or switch it off"


def hosted_problem(hosted_on: bool, approval: str, key: bool) -> str | None:
    """None unless `speech.hosted` is on without its approval reference or the key."""
    if not hosted_on:
        return None
    if not approval.strip():
        return "on without an approval reference; set SPEECH_HOSTED_APPROVAL"
    if not key:
        return "on without the Sarvam key in the worker's env"
    return None
