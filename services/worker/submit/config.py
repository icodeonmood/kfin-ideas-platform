"""Configuration lane C's sorting and sending read: the sorting lists and review routing (`rules/sorting.md`), the
promises (`rules/promises.md`, BLD-A181) and the declaration beside Submit and Save. The rules are read from the
company repo on each call (the loader caches nothing), so a change there needs no release (L-AUDIT config)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from onepc import enums
from rules import load_rule

# L-SUBMIT.pre/5: the declaration is shown beside the button; pressing it is the acceptance, recorded with the text
# version and the time. A change to either sentence needs a new version.
DECLARATION_VERSION = "1pc-2026-11"
DECLARATION = {
    "submit": "By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own "
    "work or you’ve credited others.",
    "save": "By saving, you confirm there’s no customer personal data in it or its files, and it’s your own work or "
    "you’ve credited others.",
}

KINDS_ON_CHECK_IT = ("problem", "business_idea")  # E-ENUMS.kind: Check it offers two; `fix` is derived
BRINGS: tuple[str, ...] = enums.values("brings")
NOT_SURE = "not_sure"


@dataclass(frozen=True)
class Lists:
    affects_shown: tuple[str, ...]
    affects_more: tuple[str, ...]
    areas_shown: tuple[str, ...]
    areas_more: tuple[str, ...]
    helpers: tuple[str, ...]
    routing_areas: dict[str, tuple[str, ...]]

    @property
    def affects(self) -> tuple[str, ...]:
        return self.affects_shown + self.affects_more

    @property
    def areas(self) -> tuple[str, ...]:
        return self.areas_shown + self.areas_more

    def affects_label(self, value: object) -> str | None:
        """The configured spelling of a group, matched without regard to case; None if it is not on the list."""
        return _match(value, self.affects)

    def area_label(self, value: object) -> str | None:
        return _match(value, self.areas)


def _match(value: object, options: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    folded = " ".join(value.split()).casefold()
    return next((o for o in options if o.casefold() == folded), None)


def lists() -> Lists:
    data = load_rule(get_settings().company_repo_path, "sorting").data
    return Lists(
        affects_shown=tuple(data["affects"]["shown"]),
        affects_more=tuple(data["affects"]["more"]),
        areas_shown=tuple(data["areas"]["shown"]),
        areas_more=tuple(data["areas"]["more"]),
        helpers=tuple(data["helpers"]),
        routing_areas={k: tuple(v) for k, v in (data["review_routing"]["areas"] or {}).items()},
    )


def promises() -> dict[str, Any]:
    return dict(load_rule(get_settings().company_repo_path, "promises").data)


def public_config() -> dict[str, Any]:
    """What `GET /config` shows from lane C's side (A-API.config): the sorting lists with the words their controls
    carry, the declaration, and the windows and clocks the copy names."""
    li = lists()
    p = promises()
    kind_labels = enums.labels("kind")
    brings_labels = enums.labels("brings")
    return {
        "sorting": {
            "affects": {
                "choice": "multi",
                "rule": "Pick all that apply",
                "shown": list(li.affects_shown),
                "all": list(li.affects),
                "search_link": "Search all groups",
                "search_label": f"Someone else? Search all {len(li.affects)}",
            },
            "kind": {
                "choice": "one",
                "rule": "Pick one",
                "options": [{"value": k, "label": kind_labels[k]} for k in KINDS_ON_CHECK_IT],
            },
            "area": {
                "choice": "one",
                "rule": "Pick one",
                "shown": list(li.areas_shown),
                "all": list(li.areas),
                "search_link": "Search all areas",
                "search_label": f"Another area? Search all {len(li.areas)}",
            },
            "brings": {
                "choice": "multi",
                "rule": "Pick all that apply",
                "options": [{"value": b, "label": brings_labels[b]} for b in BRINGS],
                "exclusive": NOT_SURE,
            },
            "helpers": list(li.helpers),
        },
        "declaration": {"version": DECLARATION_VERSION, **DECLARATION},
        "windows": {
            "review_working_days": int(p["review"]["decide_by_working_days"]),
            "edit_window_days": int(p["edit_window"]["max_days"]),
        },
    }
