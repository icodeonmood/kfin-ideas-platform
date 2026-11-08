"""OKF validator: conformance, trust-field shapes and the KFin profile (AT-B1-03, validator half)."""

from pathlib import Path

from okf.validate import main, validate_bundle

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _codes(root: Path) -> set[str]:
    return {i.code for i in validate_bundle(root) if i.level == "error"}


def test_seed_bundle_is_conformant() -> None:
    assert main([str(SEED), "--quiet"]) == 0


def test_file_without_type_fails(tmp_path: Path) -> None:
    _write(tmp_path, "index.md", '---\nokf_version: "0.2"\n---\n# Root\n')
    _write(tmp_path, "notes/index.md", "# Notes\n")
    _write(tmp_path, "notes/no-type.md", "---\ntitle: Missing type\n---\nBody\n")
    assert main([str(tmp_path)]) != 0
    assert "E002" in _codes(tmp_path)


def test_file_without_frontmatter_fails(tmp_path: Path) -> None:
    _write(tmp_path, "plain.md", "# Just markdown\n")
    assert "E001" in _codes(tmp_path)


def test_trust_fields_must_follow_spec(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.md",
        "---\ntype: note\nverified: human:REV-0001\n"
        "generated: {by: 'agent:scan@1.3', at: '2026-11-08'}\n---\n",
    )
    codes = _codes(tmp_path)
    assert {"E010", "E011"} <= codes


def test_good_trust_fields_pass(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.md",
        "---\ntype: note\nstatus: stable\n"
        "generated: {by: canvas-assist/0.1.0, at: '2026-11-08T10:00:00+05:30'}\n"
        "verified: [{by: 'human:REV-0001', at: '2026-11-09T10:00:00+05:30'}]\n"
        "sources: [{id: SUB-2026-000001, resource: 'submission:SUB-2026-000001'}]\n---\nBody\n",
    )
    assert _codes(tmp_path) == set()


def test_reserved_files(tmp_path: Path) -> None:
    _write(tmp_path, "sub/index.md", "---\ntype: index\n---\n# Sub\n")
    _write(tmp_path, "log.md", "# Log\n\n## 2026-11-01\n* old\n\n## 2026-11-08\n* new\n")
    codes = _codes(tmp_path)
    assert "E003" in codes  # index.md below the root must not carry frontmatter
    assert "E004" in codes  # log entries must be newest first


def test_idea_file_name_and_header(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ideas/2026/11/IDEA-2026-000001.md",
        "---\ntype: idea\nkfin:\n  id: IDEA-2026-000002\n  stage: flying\n  kind: problem\n"
        "  category: cost_saving\n  contributor: CTR-abc123\n  visibility: org\n---\n",
    )
    codes = _codes(tmp_path)
    assert "K002" in codes  # file name must equal kfin.id
    assert "K003" in codes  # stage "flying" is not a workflow stage
