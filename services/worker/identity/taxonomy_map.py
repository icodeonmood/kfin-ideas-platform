"""Map HR departments to LOBs and job titles to role families, from the company repo's taxonomy (§3.1).

- Department: exact match (case and spacing ignored) against `kfin.hr_departments` in taxonomy/lobs/*.md.
- Job title: the first role family, in taxonomy/roles/index.md order, with a `kfin.title_patterns` entry that
  matches at the start of a word in the title ("recruit" matches "Recruiter"; "hr" does not match "three").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from okf.frontmatter import parse


class TaxonomyError(ValueError):
    pass


def _space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass(frozen=True)
class TaxonomyMap:
    departments: dict[str, str]  # normalised department -> LOB-…
    roles: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]  # (ROLE-…, patterns) in index order

    def lob_for(self, department: str | None) -> str | None:
        return self.departments.get(_space(department)) if department else None

    def role_for(self, job_title: str | None) -> str | None:
        if not job_title:
            return None
        title = _space(job_title)
        for role_id, patterns in self.roles:
            if any(p.search(title) for p in patterns):
                return role_id
        return None


def load(repo: Path) -> TaxonomyMap:
    departments: dict[str, str] = {}
    for path in sorted((repo / "taxonomy" / "lobs").glob("LOB-*.md")):
        kfin = (parse(path.read_text(encoding="utf-8")).meta or {}).get("kfin") or {}
        for dep in kfin.get("hr_departments") or []:
            key = _space(str(dep))
            if key in departments and departments[key] != kfin["id"]:
                raise TaxonomyError(
                    f"HR department '{dep}' is listed under {departments[key]} and {kfin['id']}"
                )
            departments[key] = str(kfin["id"])

    index = (repo / "taxonomy" / "roles" / "index.md").read_text(encoding="utf-8")
    order = list(dict.fromkeys(re.findall(r"\((ROLE-[a-z0-9-]+)\.md\)", index)))
    roles: list[tuple[str, tuple[re.Pattern[str], ...]]] = []
    for role_id in order:
        path = repo / "taxonomy" / "roles" / f"{role_id}.md"
        kfin = (parse(path.read_text(encoding="utf-8")).meta or {}).get("kfin") or {}
        patterns = tuple(
            re.compile(r"(?<![a-z0-9])" + re.escape(_space(str(p)))) for p in kfin.get("title_patterns") or []
        )
        roles.append((role_id, patterns))
    if not roles or not departments:
        raise TaxonomyError("taxonomy has no LOB departments or role families")
    return TaxonomyMap(departments=departments, roles=tuple(roles))
