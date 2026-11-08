"""Synthetic HR directory for dev, UAT and tests (B2): 200 people across the seed LOBs and role families.

Deterministic from GOLDEN_SEED. Employee IDs are `SYN-00001`…; emails use the reserved domain
`kfintech.example`, so no synthetic person can collide with a real address. Names are random pairings of
common given names and surnames. The first rows are fixed personas, one per role in the §3.1 matrix, so
people can sign in as a reviewer, a committee member or an admin in dev.
"""

from __future__ import annotations

import csv
import importlib
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from core.config import REPO_ROOT
from identity.hr_import import HEADER
from okf.frontmatter import parse

sys.path.insert(0, str((REPO_ROOT or Path.cwd()) / "eval" / "golden"))
generators = importlib.import_module("generators")

DOMAIN = "kfintech.example"
LOCATIONS = ("Hyderabad", "Mumbai", "Chennai", "Bengaluru", "Kolkata", "Jaipur")

# Job titles per role family, written so the seed's title patterns map them (and two marketing titles that
# deliberately map to nothing, so dev data exercises the taxonomy-proposal path).
TITLES: dict[str, tuple[str, ...]] = {
    "leader": ("Head - Operations", "Vice President", "Director - Client Service", "General Manager"),
    "qa": ("QA Engineer", "Test Lead"),
    "support": ("Support Engineer", "System Administrator"),
    "infosec": ("Security Analyst", "SOC Analyst"),
    "engineer": ("Software Engineer", "Senior Developer", "Solution Architect"),
    "product": ("Product Manager", "Product Owner"),
    "analyst": ("Business Analyst", "Functional Analyst"),
    "rm": ("Relationship Manager", "Sales Executive", "Key Account Manager"),
    "service": ("Client Service Executive", "Investor Service Associate"),
    "compliance": ("Compliance Officer", "Risk Analyst", "Company Secretary"),
    "finance": ("Finance Executive", "Accounts Associate"),
    "hr": ("HR Business Partner", "Talent Acquisition Specialist", "Learning Specialist"),
    "admin": ("Admin Executive", "Facilities Coordinator"),
    "lead": ("Team Lead - Operations", "Operations Manager", "Supervisor"),
    "ops": ("Executive - Operations", "Processing Associate", "Senior Associate"),
    "unmapped": ("Marketing Manager", "Content Specialist"),
}

# LOB -> (headcount, role mix). One leader per LOB is added on top of the mix.
LOBS: dict[str, tuple[int, tuple[str, ...]]] = {
    "LOB-mf": (40, ("ops", "ops", "ops", "lead", "service", "rm")),
    "LOB-sif": (8, ("ops", "ops", "lead", "service")),
    "LOB-nps": (18, ("ops", "ops", "lead", "service")),
    "LOB-alternatives": (10, ("ops", "lead", "rm")),
    "LOB-corporate-registry": (18, ("ops", "ops", "lead", "service")),
    "LOB-digital-platforms": (14, ("engineer", "product", "analyst", "rm")),
    "LOB-international": (8, ("ops", "lead", "rm")),
    "LOB-technology": (24, ("engineer", "engineer", "qa", "support", "analyst")),
    "LOB-product-strategy": (8, ("product", "analyst")),
    "LOB-infosec": (5, ("infosec",)),
    "LOB-hr": (6, ("hr",)),
    "LOB-finance": (8, ("finance",)),
    "LOB-compliance-legal": (7, ("compliance",)),
    "LOB-admin": (5, ("admin",)),
    "LOB-marketing": (4, ("unmapped",)),
    "LOB-sales": (9, ("rm",)),
    "LOB-shared-operations": (8, ("service", "ops")),
}


@dataclass(frozen=True)
class Persona:
    employee_id: str
    lob: str
    family: str
    roles: tuple[tuple[str, str | None], ...]  # (role, scope)
    label: str


# Fixed dev personas (employee IDs to type at the mock sign-in). Review desk = product team (open point O4).
PERSONAS: tuple[Persona, ...] = (
    Persona("SYN-00001", "LOB-technology", "lead", (("admin", None),), "Admin"),
    Persona("SYN-00002", "LOB-product-strategy", "product", (("reviewer", None),), "Review desk"),
    Persona("SYN-00003", "LOB-product-strategy", "product", (("reviewer", None),), "Review desk"),
    Persona("SYN-00004", "LOB-product-strategy", "analyst", (("reviewer", None),), "Review desk"),
    Persona("SYN-00005", "LOB-product-strategy", "analyst", (("reviewer", None),), "Review desk"),
    Persona(
        "SYN-00006",
        "LOB-mf",
        "leader",
        (("core_committee", None), ("core_chair", None)),
        "Core committee chair",
    ),
    Persona("SYN-00007", "LOB-technology", "leader", (("core_committee", None),), "Core committee"),
    Persona("SYN-00008", "LOB-finance", "leader", (("core_committee", None),), "Core committee"),
    Persona("SYN-00009", "LOB-nps", "leader", (("core_committee", None),), "Core committee"),
    Persona("SYN-00010", "LOB-compliance-legal", "leader", (("core_committee", None),), "Core committee"),
    Persona("SYN-00011", "LOB-infosec", "infosec", (("infosec", None),), "InfoSec"),
    Persona("SYN-00012", "LOB-hr", "hr", (("hr", None),), "HR"),
    Persona(
        "SYN-00013",
        "LOB-corporate-registry",
        "leader",
        (("lob_committee", "LOB-corporate-registry"),),
        "LOB committee",
    ),
    Persona("SYN-00014", "LOB-sales", "leader", (("appeal_panel", None),), "Appeal panel"),
    Persona("SYN-00015", "LOB-mf", "ops", (("working_group", "WG-0001"),), "Working group"),
    Persona("SYN-00016", "LOB-sif", "leader", (("sponsor", "CL-0001"),), "Sponsor"),
    Persona("SYN-00017", "LOB-mf", "ops", (), "Contributor"),
)


def _departments(repo: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in sorted((repo / "taxonomy" / "lobs").glob("LOB-*.md")):
        kfin = (parse(path.read_text(encoding="utf-8")).meta or {}).get("kfin") or {}
        out[str(kfin["id"])] = [str(d) for d in kfin.get("hr_departments") or []]
    return out


def generate(repo: Path, seed: int | None = None) -> list[dict[str, str]]:
    rng = random.Random(int(os.environ.get("GOLDEN_SEED", "42")) if seed is None else seed)
    departments = _departments(repo)
    people: list[dict[str, str]] = []
    used_names: set[str] = set()

    def person(employee_id: str, lob: str, family: str) -> dict[str, str]:
        name = generators.person_name(rng)
        while name in used_names:
            name = generators.person_name(rng)
        used_names.add(name)
        first, last = name.lower().split(" ", 1)
        return {
            "employee_id": employee_id,
            "name": name,
            "email": f"{first}.{last.replace(' ', '')}.{employee_id[-3:]}@{DOMAIN}",
            "department": rng.choice(departments[lob]),
            "job_title": rng.choice(TITLES[family]),
            "location": rng.choice(LOCATIONS),
            "manager_employee_id": "",
            "_lob": lob,
            "_family": family,
        }

    for p in PERSONAS:
        people.append(person(p.employee_id, p.lob, p.family))
    counts = {lob: sum(1 for x in people if x["_lob"] == lob) for lob in LOBS}
    n = len(people)
    for lob, (headcount, mix) in LOBS.items():
        families = (
            ["leader"] if not any(x["_lob"] == lob and x["_family"] == "leader" for x in people) else []
        )
        families += [mix[i % len(mix)] for i in range(max(0, headcount - counts[lob] - len(families)))]
        for family in families:
            n += 1
            people.append(person(f"SYN-{n:05d}", lob, family))

    # Managers: each LOB's leader manages its leads; leads manage everyone else, round robin.
    for lob in LOBS:
        members = [x for x in people if x["_lob"] == lob]
        leaders = [x for x in members if x["_family"] == "leader"]
        leads = [x for x in members if x["_family"] == "lead"] or leaders
        for i, x in enumerate(members):
            if x["_family"] == "leader":
                continue
            boss = (
                leaders[0] if x["_family"] == "lead" and leaders else leads[i % len(leads)] if leads else None
            )
            if boss is not None and boss is not x:
                x["manager_employee_id"] = boss["employee_id"]
    return people


def write_csv(people: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(people)
    return path
