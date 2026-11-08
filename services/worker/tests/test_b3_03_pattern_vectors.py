"""AT-B3-03 (Python half): every pattern in §4.2 step 2 blocks or warns as specified on the shared generated
vectors; masked Aadhaar is allowed; a KFin-domain email only warns. The TypeScript half
(apps/web/tests/unit/pattern-vectors.test.ts) must reproduce the `python` matches exactly."""

from pii.vectors import build


def test_vectors_meet_their_expectations() -> None:
    data = build(n=20)
    assert data["count"] >= 300
    wrong = []
    for v in data["vectors"]:
        blocks = any(m["action"] == "block" for m in v["python"])
        warns = any(m["action"] == "warn" for m in v["python"]) and not blocks
        ids = {m["pattern"] for m in v["python"]}
        exp = v["expect"]
        if blocks != exp["blocks"] or (exp["warns"] and not warns) or (not exp["warns"] and warns):
            wrong.append(f"{v['id']}: blocks={blocks} warns={warns}")
        elif exp["patterns"] and not ids & set(exp["patterns"]):
            wrong.append(f"{v['id']}: found {sorted(ids)}")
    assert wrong == []


def test_every_pattern_is_exercised() -> None:
    from pii.patterns import load_rules

    seen = {m["pattern"] for v in build(n=20)["vectors"] for m in v["python"]}
    assert {p.id for p in load_rules().patterns} <= seen
