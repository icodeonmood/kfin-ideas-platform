"""AT-B1-07: the rules loader parses the YAML block in every rule file and validates it against its schema;
a scorecard whose weights don't sum to 100 fails with a configuration error."""

import shutil
import subprocess
from pathlib import Path

import pytest

from rules import RulesConfigError, load_all, load_rule
from rules.loader import RULE_PATHS

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    dest = tmp_path / "kfin-ideas"
    shutil.copytree(SEED, dest)
    return dest


def _edit(repo: Path, rel: str, old: str, new: str) -> None:
    path = repo / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture text not found in {rel}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_every_seed_rule_file_loads() -> None:
    rules = load_all(SEED)
    assert set(rules) == set(RULE_PATHS)
    assert set((SEED / "rules").glob("*.md")) - {SEED / "rules" / "index.md"} == {
        SEED / p for p in RULE_PATHS.values() if p.startswith("rules/")
    }, "a rules/*.md file exists that the loader does not know about"
    assert rules["thresholds"].data["gatekeeper"]["personal_data_block"] == 0.5
    assert rules["scorecard"].version == "1.0"


def test_scorecard_weights_must_sum_to_100(repo: Path) -> None:
    _edit(repo, "rules/scorecard.md", "financial_value:\n    weight: 30", "financial_value:\n    weight: 35")
    with pytest.raises(RulesConfigError) as err:
        load_rule(repo, "scorecard")
    assert "sum to 105, not 100" in str(err.value)
    with pytest.raises(RulesConfigError):
        load_all(repo)


def test_schema_violation_names_the_field(repo: Path) -> None:
    _edit(repo, "rules/thresholds.md", "personal_data_block: 0.5", "personal_data_block: 1.5")
    with pytest.raises(RulesConfigError) as err:
        load_rule(repo, "thresholds")
    assert "gatekeeper.personal_data_block" in str(err.value)


def test_missing_rule_is_a_config_error_not_a_guess(repo: Path) -> None:
    (repo / "rules" / "sla.md").unlink()
    with pytest.raises(RulesConfigError) as err:
        load_rule(repo, "sla")
    assert "missing" in str(err.value)


def test_two_yaml_blocks_are_refused(repo: Path) -> None:
    path = repo / "rules" / "points.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n```yaml\nversion: '9.9'\n```\n", encoding="utf-8")
    with pytest.raises(RulesConfigError) as err:
        load_rule(repo, "points")
    assert "exactly one" in str(err.value)


def test_past_versions_replay_from_git(repo: Path) -> None:
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@localhost"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "seed"], check=True)
    first = subprocess.run(
        [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    _edit(repo, "rules/scorecard.md", "divergence_flag_points: 2", "divergence_flag_points: 3")
    subprocess.run([*git, "commit", "-qam", "change"], check=True)
    assert load_rule(repo, "scorecard", ref=first).data["divergence_flag_points"] == 2
    assert load_rule(repo, "scorecard").data["divergence_flag_points"] == 3
