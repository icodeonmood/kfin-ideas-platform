"""Restore on view (ARCHITECTURE §3.2 step 8). Outputs are stored with tags; real values come back only when a
person who may see them views the artefact. Everyone else sees a neutral label ("a colleague", "an AMC
client"). A tag the vault does not know for this scope is left exactly as it is (it was flagged at the gateway).
The decision of who may see what is made by the caller from §3.1 (web: `src/server/restore.ts`).
"""

from __future__ import annotations

from typing import Any, Literal

from pii.tagger import TAG_RE

Mode = Literal["real", "neutral"]

NEUTRAL = {
    "KFIN_EMPLOYEE": "a colleague",
    "CONTRIBUTOR": "a contributor",
    "REVIEWER": "a reviewer",
    "MEMBER": "a committee member",
    "PERSON": "a person",
    "INVESTOR_NAME": "an investor",
    "CLIENT_AMC": "an AMC client",
    "CLIENT_ISSUER": "an issuer client",
    "CLIENT_FUND_MANAGER": "a fund manager client",
    "CLIENT_PENSION": "a pension client",
    "CLIENT_PARTNER": "a partner organisation",
    "PAN": "a PAN",
    "AADHAAR": "an Aadhaar number",
    "PHONE": "a phone number",
    "EMAIL": "an email address",
    "ACCOUNT_NUMBER": "an account number",
    "CARD_NUMBER": "a card number",
    "FOLIO_NUMBER": "a folio number",
    "DEMAT_ACCOUNT": "a demat account",
    "PRAN": "a PRAN",
    "DATE_OF_BIRTH": "a date of birth",
    "IFSC": "an IFSC",
    "ARN": "an ARN",
    "EUIN": "an EUIN",
}


def restore(payload: Any, mapping: dict[str, tuple[str, str]], mode: Mode) -> Any:
    def swap(m: Any) -> str:
        tag = m.group(0)
        if tag not in mapping:
            return str(tag)  # unknown or altered: left unrestored
        type_, value = mapping[tag]
        return value if mode == "real" else NEUTRAL.get(type_, "a detail")

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return TAG_RE.sub(swap, node)
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        return node

    return walk(payload)


def neutralise(payload: Any, types: dict[str, str]) -> Any:
    """Neutral labels without opening the vault (tag -> type is enough)."""
    return restore(payload, {t: (typ, "") for t, typ in types.items()}, "neutral")
