"""BLD-A197, L-AUTH.rules/1: the journeys run's provider answers a silent try as Entra ID does with no session."""

import importlib.util
import sys
from types import ModuleType

from tests import helpers

SCRIPT = helpers.ROOT / "scripts" / "ci" / "oidc_silent_shim.py"
CALLBACK = "http%3A%2F%2Flocalhost%3A3000%2Fauth%2Fcallback"


def _shim() -> ModuleType:
    spec = importlib.util.spec_from_file_location("oidc_silent_shim", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_l_auth_rules_1_a_silent_try_goes_back_to_the_callback_with_login_required() -> None:
    path = (
        "/default/authorize?prompt=none&response_type=code&client_id=ideas-platform"
        f"&redirect_uri={CALLBACK}&scope=openid+profile+email&state=st-1&nonce=n-1"
    )
    assert (
        _shim().silent_answer("GET", path)
        == "http://localhost:3000/auth/callback?error=login_required&state=st-1"
    )


def test_l_auth_rules_1_a_redirect_uri_with_a_query_keeps_it() -> None:
    path = "/default/authorize?prompt=none&redirect_uri=http%3A%2F%2Fapp%2Fcb%3Fx%3D1&state=s"
    assert _shim().silent_answer("GET", path) == "http://app/cb?x=1&error=login_required&state=s"


def test_bld_a197_everything_else_goes_on_to_the_mock() -> None:
    shim = _shim()
    # "Use single sign-on" (no prompt) and the mock's own login form and its post.
    assert shim.silent_answer("GET", f"/default/authorize?response_type=code&redirect_uri={CALLBACK}") is None
    assert shim.silent_answer("POST", f"/default/authorize?prompt=none&redirect_uri={CALLBACK}") is None
    assert shim.silent_answer("GET", f"/default/authorize?prompt=login&redirect_uri={CALLBACK}") is None
    # Discovery, keys and sign-out.
    assert shim.silent_answer("GET", "/default/.well-known/openid-configuration") is None
    assert shim.silent_answer("GET", "/default/jwks") is None
    assert shim.silent_answer("GET", "/default/endsession?prompt=none") is None
    # With nowhere to send it back, the mock answers its own error.
    assert shim.silent_answer("GET", "/default/authorize?prompt=none&state=s") is None
