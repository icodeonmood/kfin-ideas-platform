"""Worker internal API: the token is required (BLD-048), and the canvas config carries the rubric and the six
"what good looks like" examples from the company repo (§4.1)."""

import httpx
import pytest

from core.config import get_settings

pytestmark = pytest.mark.stack

WORKER = get_settings().worker_url.rstrip("/")


def test_internal_api_needs_the_token() -> None:
    assert httpx.get(f"{WORKER}/internal/canvas-config", timeout=10).status_code == 401
    assert (
        httpx.get(
            f"{WORKER}/internal/canvas-config", headers={"X-Internal-Token": "wrong"}, timeout=10
        ).status_code
        == 401
    )
    assert httpx.get(f"{WORKER}/internal/health", timeout=10).status_code == 200  # healthcheck stays open


def test_canvas_config_comes_from_the_company_repo() -> None:
    r = httpx.get(
        f"{WORKER}/internal/canvas-config",
        headers={"X-Internal-Token": get_settings().internal_api_token},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["canvas"]["one_line_max_words"] == 20 and body["canvas"]["details_min_chars"] == 50
    assert set(body["canvas_strength"]) >= {
        "what_it_is",
        "who_it_touches",
        "whats_it_worth",
        "evidence",
        "solved_elsewhere",
    }
    assert [e["slug"] for e in body["examples"]] == [
        "what-is-it", "who-it-touches", "whats-it-worth", "solved-elsewhere", "your-solution", "your-research",
    ]  # fmt: skip
    assert all(e["weak"] and e["strong"] and e["why"] for e in body["examples"])
    assert body["rules_version"]["thresholds"] == "1.0"
