"""The delivery pipeline's phases, copied from `contracts/garage/phases.yaml` (the worker image does not carry the
contracts folder; a test keeps the two in step). `shown_as` is the plain wording people see (§4.9). Employees never
see the pipeline's name: on the wall and in My ideas the stage reads "Being built", then "Shipped" (DEC-035, DEC-038).
"""

from __future__ import annotations

PHASES: tuple[tuple[str, str], ...] = (
    ("01-discover", "Discovery"),
    ("02-shape", "Writing the spec"),
    ("03-gate", "Spec review"),
    ("04-handoff", "Building: handoff"),
    ("05-build", "Building: build"),
    ("06-test", "Building: test"),
    ("07-review", "Building: review"),
    ("08-qa", "Building: QA"),
    ("09-deploy", "Building: deploy"),
    ("handed-off", "With the development team"),
    ("shipped", "Shipped"),
)
PHASE_IDS = tuple(p for p, _ in PHASES)
SHOWN_AS = dict(PHASES)
GATE_STATUS = ("clear", "blocked")

PRODUCTS = ("iris", "lamf", "guardian", "api-marketplace", "ai-tooling", "sif-aif-pms", "mf-central", "other")
FEATURE_TYPES = ("kfintech-product", "ai-tooling")
COMPLIANCE_TIERS = ("standard", "express")
TRACKS = ("build", "fix", "procurement")

# The success metric's unit (§4.8): a fixed list, so packs hold codes and numbers only.
METRIC_UNITS = (
    "minutes per case",
    "hours a month",
    "days to complete",
    "cases a month",
    "errors a month",
    "calls a month",
    "per cent",
    "rupees a month",
    "rupees a year",
)


def shown_as(phase: str | None) -> str | None:
    return SHOWN_AS.get(phase or "")


# The steps from handoff to deploy are one step for contributors and sponsors, "Being built" (§4.9 with BLD-157):
# messages use these plain words and go out only when they change. The build team keeps the detailed step on the
# delivery page (`shown_as`).
BUILDING = ("04-handoff", "05-build", "06-test", "07-review", "08-qa", "09-deploy")


def plain_step(phase: str | None) -> str | None:
    return "Being built" if phase in BUILDING else shown_as(phase)
