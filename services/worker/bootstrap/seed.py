"""`make seed`: create the company repo from seed/company-repo, validate it, check the rules, index it, and
load the synthetic HR directory (200 people) with the dev personas' roles.

Safe to re-run: an existing company repo is left alone (it is the source of truth after the first run);
the HR import is an upsert; persona grants are idempotent and only applied in dev and test.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from bootstrap.synthetic_hr import PERSONAS, generate, write_csv
from core.config import REPO_ROOT, get_settings
from core.db import connect
from identity.codes import emp_id_hash
from identity.grants import grant
from identity.hr_import import import_rows, read_csv
from identity.taxonomy_map import load as load_taxonomy
from index.indexer import Indexer
from okf.validate import validate_bundle
from repo_writer.git import Git
from rules import RulesConfigError, load_all

SEED_MESSAGE = (
    "Seed company repo from kfin-ideas-platform/seed/company-repo\n\nactor: system\nevent: repo.seeded\n"
)
OVERLAY_MESSAGE = (
    "Dev overlay: synthetic content for dev and test\n\nactor: system\nevent: repo.dev_overlay\n"
)


def create_company_repo(seed_dir: Path, dest: Path, author: str, overlay_dir: Path | None = None) -> bool:
    """Copy the seed (plus, in dev and test, the dev overlay) into `dest` and make one commit. Returns False if
    a company repo already exists."""
    git = Git(dest, author)
    if git.is_repo():
        if git.head() is None:
            raise SystemExit(f"{dest} is a Git repo with no commits; remove it or run `make clean-data`")
        return False
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} exists and is not empty; refusing to overwrite it")
    shutil.copytree(seed_dir, dest, dirs_exist_ok=True)
    if overlay_dir is not None:
        _copy_overlay(overlay_dir, dest)
    git.init()
    git.commit_all(SEED_MESSAGE)
    return True


def _copy_overlay(overlay_dir: Path, dest: Path) -> int:
    if get_settings().is_production_like or not overlay_dir.exists():
        return 0
    added = 0
    for src in sorted(overlay_dir.rglob("*.md")):
        rel = src.relative_to(overlay_dir)
        if rel == Path("README.md"):
            continue
        target = dest / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            added += 1
    return added


def apply_dev_overlay(overlay_dir: Path, dest: Path, author: str) -> int:
    """For a company repo created before the overlay existed: add missing dev-only files in one commit. Never
    outside dev and test. Returns the number of files added."""
    added = _copy_overlay(overlay_dir, dest)
    if added:
        Git(dest, author).commit_all(OVERLAY_MESSAGE)
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, default=(REPO_ROOT or Path.cwd()) / "seed" / "company-repo")
    args = parser.parse_args(argv)
    settings = get_settings()
    dest = Path(settings.company_repo_path)

    overlay_dir = args.seed_dir.parent / "dev-overlay"
    created = create_company_repo(args.seed_dir, dest, settings.repo_writer_author, overlay_dir)
    print(f"company repo: {'created' if created else 'already exists'} at {dest}")
    overlay = 0 if created else apply_dev_overlay(overlay_dir, dest, settings.repo_writer_author)
    if overlay:
        print(f"dev overlay: {overlay} synthetic files added")

    errors = [i for i in validate_bundle(dest) if i.level == "error"]
    if errors:
        for issue in errors:
            print(issue)
        print("company repo is not valid OKF; fix the seed or the repo before continuing")
        return 1
    print("okf: valid")

    try:
        rules = load_all(dest)
    except RulesConfigError as exc:
        for problem in exc.problems:
            print(f"CONFIG ERROR {problem}")
        return 1
    print(f"rules: {len(rules)} files loaded")

    result = Indexer(settings).run_once(rebuild=created)
    print(f"index: {len(result.upserted)} files indexed at {result.to_commit}")
    return seed_people(dest)


def seed_people(repo: Path) -> int:
    """Synthetic HR directory plus, in dev and test, the persona role grants."""
    settings = get_settings()
    csv_path = write_csv(generate(repo), Path(settings.company_repo_path).parent / "hr" / "synthetic-hr.csv")
    with connect(autocommit=True) as conn:
        r = import_rows(conn, read_csv(csv_path), load_taxonomy(repo))
        print(
            f"hr import: {r.rows} people ({r.created} new, {r.updated} updated, {r.deactivated} deactivated); "
            f"{len(r.unmapped_departments) + len(r.unmapped_titles)} unmapped values sent to the review desk"
        )
        if settings.app_env not in {"dev", "test"}:
            print("persona roles: skipped outside dev and test")
            return 0
        print("dev personas (sign in with the employee ID as the username):")
        for p in PERSONAS:
            user = conn.execute(
                "SELECT id FROM users WHERE emp_id_hash = %s", (emp_id_hash(p.employee_id),)
            ).fetchone()
            assert user is not None
            for role, scope in p.roles:
                grant(conn, str(user["id"]), role, scope, actor="system", reason="dev persona (synthetic)")
            roles = ", ".join(f"{r}{f' ({s})' if s else ''}" for r, s in p.roles) or "contributor only"
            print(f"  {p.employee_id}  {p.label:22} {roles}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
