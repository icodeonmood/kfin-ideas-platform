"""P-PRODUCT.promises come from the company repo's rules/promises.md (BLD-A181): one source for every lane, changed
without a release. The stack test reads them through the worker, as the web app does."""

import httpx
import pytest

from core.config import get_settings

WORKER = get_settings().worker_url.rstrip("/")


@pytest.mark.stack
def test_the_promises_come_from_the_company_repo() -> None:
    assert httpx.get(f"{WORKER}/internal/config/promises", timeout=10).status_code == 401
    r = httpx.get(
        f"{WORKER}/internal/config/promises",
        headers={"X-Internal-Token": get_settings().internal_api_token},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["review"]["decide_by_working_days"] == 5
    assert body["questions"]["answer_default_days"] in body["questions"]["answer_options_days"]
    assert body["sign_in"] == {
        "code_digits": 6,
        "code_valid_minutes": 10,
        "code_tries": 3,
        "resend_after_seconds": 45,
    }
