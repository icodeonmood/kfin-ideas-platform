"""OKF v0.2 conformance validator with the KFin profile.

Conformance (SPEC §11): every non-reserved .md file has a parseable frontmatter block with a non-empty
`type`; `index.md` and `log.md` follow §8 and §9.
Trust, lifecycle and provenance shapes (SPEC §5, §7) are errors here, because our own writer produces them
and the indexer derives trust tiers from them.
KFin profile: file name equals `kfin.id` for typed concepts, the idea header schema (ARCHITECTURE §2.2),
and the comms rules' template references.

Usage: python -m okf.validate <bundle-dir>     (exit 0 = no errors; warnings are printed but allowed)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from okf.frontmatter import FrontmatterError, parse

SCHEMAS = Path(__file__).with_name("schemas")

ACTOR = re.compile(r"^(?:human:[A-Za-z0-9._-]+|process:[A-Za-z0-9._-]+|[A-Za-z0-9._-]+/[A-Za-z0-9._+-]+)$")
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")
LOG_HEADING = re.compile(r"^##\s+(\S+)\s*$")
STATUSES = {"draft", "stable", "deprecated"}

# Concept types whose file name must equal kfin.id ("one concept per file; file names are the ID").
ID_NAMED_TYPES = {
    "idea",
    "cluster",
    "theme",
    "decision",
    "handover",
    "appeal",
    "solution",
    "lob",
    "role-family",
    "area-tag",
    "glossary-term",
    "client-org",
}


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning"
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.code} {self.path}: {self.message}"


@lru_cache(maxsize=1)
def _idea_validator() -> Draft202012Validator:
    schema = json.loads((SCHEMAS / "idea.kfin.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _is_datetime_with_offset(value: Any) -> bool:
    if isinstance(value, datetime):
        return value.tzinfo is not None
    if isinstance(value, date):
        return False
    return isinstance(value, str) and bool(ISO_DATETIME.match(value))


def _check_actor_event(entry: Any, field: str, rel: str, issues: list[Issue], *, need_at: bool) -> None:
    if not isinstance(entry, dict):
        issues.append(Issue("error", "E011", rel, f"`{field}` entries must be mappings with `by` and `at`"))
        return
    by = entry.get("by")
    if not isinstance(by, str) or not ACTOR.match(by):
        issues.append(
            Issue(
                "error",
                "E010",
                rel,
                f"`{field}.by` must be an actor (human:<id>, process:<id> or tool/version)",
            )
        )
    at = entry.get("at")
    if at is None and need_at:
        issues.append(Issue("error", "E011", rel, f"`{field}.at` is required"))
    elif at is not None and not _is_datetime_with_offset(at):
        issues.append(
            Issue("error", "E010", rel, f"`{field}.at` must be an ISO 8601 datetime with a UTC offset")
        )


def check_concept_meta(meta: dict[str, Any], rel: str) -> list[Issue]:
    """Checks on one concept's frontmatter (no filesystem access), shared with the repo writer."""
    issues: list[Issue] = []
    typ = meta.get("type")
    if not isinstance(typ, str) or not typ.strip():
        issues.append(Issue("error", "E002", rel, "frontmatter has no non-empty `type`"))
    for key in ("title", "description", "resource"):
        if key in meta and not isinstance(meta[key], str):
            issues.append(Issue("error", "E015", rel, f"`{key}` must be a string"))
    if "tags" in meta and not (
        isinstance(meta["tags"], list) and all(isinstance(t, str) for t in meta["tags"])
    ):
        issues.append(Issue("error", "E015", rel, "`tags` must be a list of strings"))
    if "generated" in meta:
        gen = meta["generated"]
        if not isinstance(gen, dict) or "by" not in gen:
            issues.append(Issue("error", "E010", rel, "`generated` must be a mapping with `by`"))
        else:
            _check_actor_event(gen, "generated", rel, issues, need_at=False)
    if "verified" in meta:
        ver = meta["verified"]
        entries = ver if isinstance(ver, list) else [ver]
        if isinstance(ver, str):
            issues.append(
                Issue(
                    "error",
                    "E011",
                    rel,
                    "`verified` must be {by, at} or a list of them; omit it when unverified",
                )
            )
        else:
            for e in entries:
                _check_actor_event(e, "verified", rel, issues, need_at=True)
    if "status" in meta and meta["status"] not in STATUSES:
        issues.append(Issue("error", "E012", rel, "`status` must be draft, stable or deprecated"))
    if "stale_after" in meta and not _is_datetime_with_offset(meta["stale_after"]):
        issues.append(
            Issue("error", "E013", rel, "`stale_after` must be an ISO 8601 datetime with a UTC offset")
        )
    if "sources" in meta:
        src = meta["sources"]
        if not isinstance(src, list) or not all(isinstance(s, dict) and s.get("resource") for s in src):
            issues.append(
                Issue("error", "E014", rel, "`sources` must be a list of mappings, each with `resource`")
            )
    kfin = meta.get("kfin")
    if kfin is not None and not isinstance(kfin, dict):
        issues.append(Issue("error", "K001", rel, "`kfin` must be a mapping"))
        kfin = None
    if kfin is not None and isinstance(typ, str):
        if typ in ID_NAMED_TYPES:
            stem = Path(rel).stem
            if kfin.get("id") != stem:
                issues.append(Issue("error", "K002", rel, f"`kfin.id` must equal the file name ({stem})"))
        if typ == "idea":
            for err in sorted(_idea_validator().iter_errors(kfin), key=lambda e: list(e.path)):
                where = ".".join(str(p) for p in err.path) or "kfin"
                issues.append(Issue("error", "K003", rel, f"idea header: kfin.{where}: {err.message}"))
    return issues


def _check_index(meta: dict[str, Any] | None, rel: str, is_root: bool) -> list[Issue]:
    if meta is None:
        return []
    if not is_root:
        return [
            Issue(
                "error",
                "E003",
                rel,
                "index.md must not have frontmatter (only the bundle root may carry okf_version)",
            )
        ]
    extra = sorted(set(meta) - {"okf_version"})
    issues = []
    if "okf_version" not in meta:
        issues.append(Issue("warning", "W003", rel, "bundle-root index.md should declare okf_version"))
    if extra:
        issues.append(
            Issue(
                "error",
                "E003",
                rel,
                f"bundle-root index.md frontmatter may only hold okf_version, found {extra}",
            )
        )
    return issues


def _check_log(meta: dict[str, Any] | None, body: str, rel: str) -> list[Issue]:
    issues: list[Issue] = []
    if meta is not None:
        issues.append(Issue("error", "E004", rel, "log.md must not have frontmatter"))
    dates: list[str] = []
    for line in body.split("\n"):
        m = LOG_HEADING.match(line)
        if m:
            try:
                date.fromisoformat(m.group(1))
            except ValueError:
                issues.append(Issue("error", "E004", rel, "log.md date headings must be YYYY-MM-DD"))
                continue
            dates.append(m.group(1))
    if dates != sorted(dates, reverse=True):
        issues.append(Issue("error", "E004", rel, "log.md entries must be newest first"))
    return issues


def _check_comms(root: Path, metas: dict[str, dict[str, Any]]) -> list[Issue]:
    """comms/rules.md: every event's template exists (error for day-one events, warning otherwise)."""
    rel = "comms/rules.md"
    rules_file = root / rel
    if not rules_file.is_file():
        return []
    m = re.search(r"```yaml\n(.*?)```", rules_file.read_text(encoding="utf-8"), re.DOTALL)
    if not m:
        return [Issue("error", "K004", rel, "no yaml block found")]
    import yaml

    block = yaml.safe_load(m.group(1)) or {}
    issues = []
    for event, spec in (block.get("events") or {}).items():
        template = (spec or {}).get("template")
        path = f"comms/templates/{template}.md"
        if template and path not in metas:
            level = "error" if spec.get("day_one") else "warning"
            issues.append(
                Issue(level, "K004", rel, f"event {event} uses template {template}, which does not exist")
            )
    return issues


def validate_bundle(root: Path) -> list[Issue]:
    root = root.resolve()
    issues: list[Issue] = []
    metas: dict[str, dict[str, Any]] = {}
    folders_with_md: set[Path] = set()
    folders_with_index: set[Path] = set()
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.relative_to(root).parts:
            continue
        rel = path.relative_to(root).as_posix()
        folders_with_md.add(path.parent)
        try:
            doc = parse(path.read_text(encoding="utf-8"))
        except (FrontmatterError, UnicodeDecodeError) as exc:
            issues.append(Issue("error", "E001", rel, str(exc)))
            continue
        if path.name == "index.md":
            folders_with_index.add(path.parent)
            issues.extend(_check_index(doc.meta, rel, path.parent == root))
        elif path.name == "log.md":
            issues.extend(_check_log(doc.meta, doc.body, rel))
        elif doc.meta is None:
            issues.append(Issue("error", "E001", rel, "concept file has no frontmatter block"))
        else:
            metas[rel] = doc.meta
            issues.extend(check_concept_meta(doc.meta, rel))
    for folder in sorted(folders_with_md - folders_with_index):
        rel = folder.relative_to(root).as_posix() or "."
        issues.append(Issue("warning", "W001", rel, "folder has no index.md"))
    issues.extend(_check_comms(root, metas))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an OKF v0.2 bundle (KFin profile).")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--quiet", action="store_true", help="print errors only")
    args = parser.parse_args(argv)
    if not args.bundle.is_dir():
        print(f"ERROR   not a folder: {args.bundle}")
        return 2
    issues = validate_bundle(args.bundle)
    errors = [i for i in issues if i.level == "error"]
    for issue in issues:
        if issue.level == "error" or not args.quiet:
            print(issue)
    files = sum(1 for p in args.bundle.rglob("*.md") if ".git" not in p.parts)
    print(f"okf: {files} files, {len(errors)} errors, {len(issues) - len(errors)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
