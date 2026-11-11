"""The speech service's container (DEC-096, BLD-C015), read from infra/docker-compose.yml and the UAT overlay:
only the internal network it shares with the worker, a read-only root filesystem, a non-root user, no secrets of
the platform, the model read-only, and started only with its profile. No Docker needed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]


class _Loader(yaml.SafeLoader):
    """Reads Compose's !reset and !override tags as plain values."""


_Loader.add_multi_constructor(
    "!",
    lambda loader, suffix, node: (
        loader.construct_sequence(node)
        if isinstance(node, yaml.SequenceNode)
        else loader.construct_scalar(node)
    ),
)


def _compose(name: str) -> dict[str, Any]:
    return yaml.load((ROOT / "infra" / name).read_text(), Loader=_Loader)  # noqa: S506 - our own file, safe loader


def _networks(service: dict[str, Any]) -> list[str]:
    nets = service.get("networks", ["default"])
    return list(nets) if isinstance(nets, list) else list(nets.keys())


def test_the_speech_service_is_locked_down() -> None:
    sp = _compose("docker-compose.yml")["services"]["speech"]
    assert sp["profiles"] == ["speech"]  # dev and CI do not start it unless asked
    assert sp["read_only"] is True
    assert any(t.startswith("/tmp") for t in sp["tmpfs"])
    assert sp["user"] == "10002:10002"
    assert sp["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in sp["security_opt"]
    assert "ports" not in sp  # nothing published
    assert "env_file" not in sp  # nothing from .env
    assert set(sp["environment"]) <= {
        "SPEECH_ENGINE", "SPEECH_MODEL_PATH", "SPEECH_THREADS", "SPEECH_MEMORY_MB", "SPEECH_TIMEOUT_S",
        "SPEECH_SERVICE_TOKEN", "SPEECH_PORT",
    }  # fmt: skip
    assert all(v.endswith(":ro") for v in sp["volumes"])
    assert "healthcheck" in sp


def test_it_shares_only_an_internal_network_with_the_worker() -> None:
    c = _compose("docker-compose.yml")
    assert _networks(c["services"]["speech"]) == ["speech"]
    assert c["networks"]["speech"]["internal"] is True  # no route out
    on_speech = sorted(n for n, s in c["services"].items() if "speech" in _networks(s))
    assert on_speech == ["speech", "worker"]  # not Postgres, the store, the scanner, mail or the web app
    assert "default" in _networks(c["services"]["worker"])


def test_the_web_app_never_gets_the_speech_token() -> None:
    for name in ("docker-compose.yml", "uat/compose.uat.yml"):
        web = _compose(name)["services"]["web"]
        assert "SPEECH_SERVICE_TOKEN" not in (web.get("environment") or {}), name


def test_uat_keeps_it_locked_down_and_takes_its_model_read_only() -> None:
    sp = _compose("uat/compose.uat.yml")["services"]["speech"]
    assert set(sp) <= {"environment", "volumes"}  # no ports, networks or env files added
    assert all(v.endswith(":ro") for v in sp["volumes"])
    assert set(sp["environment"]) == {"SPEECH_SERVICE_TOKEN"}
