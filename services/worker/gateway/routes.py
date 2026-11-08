"""Model routes: `fake` (examples, no key), `anthropic` (Claude API) and `bedrock` (Amazon Bedrock Mantle). The route
is set by `LLM_MODE`, per InfoSec (D1). This is the only file that imports the model SDK (non-negotiable 1).

Request shape for the current models (BLD-070):
- JSON output through structured outputs (`output_config.format`); constraints the API does not accept (lengths,
  ranges, item counts, patterns) are stripped from the schema sent and enforced by the gateway's own validation.
- No `temperature`: Claude Haiku 5.5 and Sonnet 5.5 reject non-default sampling. Determinism comes from fixed
  prompts, examples and the cache; drafting variety is not needed on day one.
- Thinking off for the latency budgets: `disabled` on Haiku 5.5, `between_tools` on Sonnet 5.5 (which rejects
  `disabled`). Effort per agent config.
- The system prompt and examples are one cached block.
- Claude API, Sonnet: server-side refusal fallback (`fallbacks: "default"`); Bedrock has none, so a decline is an
  agent failure and the caller takes its fallback path.
"""

from __future__ import annotations

import copy
import json
import math
import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

from core.config import get_settings
from gateway.spec import AgentSpec

UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$schema", "$id", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
        "minLength", "maxLength", "minItems", "maxItems", "uniqueItems", "pattern",
    }
)  # fmt: skip
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class RouteError(Exception):
    """The route failed. `code` is safe to log and store; no provider message is kept (it may echo input)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Refused(RouteError):
    def __init__(self) -> None:
        super().__init__("refusal")


@dataclass
class RouteResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    stop_reason: str = "end_turn"


class Route(Protocol):
    name: str

    def call(
        self, spec: AgentSpec, system: str, messages: list[dict[str, Any]], inputs: dict[str, Any]
    ) -> RouteResult: ...


def api_schema(schema: dict[str, Any]) -> dict[str, Any]:
    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in UNSUPPORTED_SCHEMA_KEYS}
        if isinstance(node, list):
            return [strip(x) for x in node]
        return node

    return strip(copy.deepcopy(schema))  # type: ignore[no-any-return]


def thinking_for(model: str, mode: str) -> dict[str, str] | None:
    if mode != "off":
        return {"type": "adaptive"}
    if "sonnet-5-5" in model:
        return {"type": "between_tools"}
    if "haiku" in model:
        return {"type": "disabled"}
    return None  # other models: leave the default


def build_request(
    spec: AgentSpec, system: str, messages: list[dict[str, Any]], *, bedrock: bool
) -> dict[str, Any]:
    model = spec.model
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": api_schema(spec.schema)}}
    if spec.effort:
        output_config["effort"] = spec.effort
    req: dict[str, Any] = {
        "model": f"anthropic.{model}" if bedrock else model,
        "max_tokens": spec.max_tokens,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
        "output_config": output_config,
    }
    thinking = thinking_for(model, spec.thinking)
    if thinking:
        req["thinking"] = thinking
    if not bedrock and get_settings().llm_refusal_fallback and "sonnet-5-5" in model:
        req["betas"] = [FALLBACK_BETA]
        req["fallbacks"] = "default"
    return req


def _result_from(response: Any) -> RouteResult:
    if response.stop_reason == "refusal":
        raise Refused()
    text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
    u = response.usage
    return RouteResult(
        text=text,
        model=str(response.model),
        input_tokens=int(u.input_tokens or 0),
        output_tokens=int(u.output_tokens or 0),
        cache_write_tokens=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        cache_read_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
        stop_reason=str(response.stop_reason),
    )


class _SdkRoute:
    name = "sdk"
    bedrock = False

    def __init__(self) -> None:
        self._client: Any = None
        self._lock = threading.Lock()

    def _make_client(self) -> Any:
        raise NotImplementedError

    def client(self) -> Any:
        with self._lock:
            if self._client is None:
                self._client = self._make_client()
            return self._client

    def call(
        self, spec: AgentSpec, system: str, messages: list[dict[str, Any]], inputs: dict[str, Any]
    ) -> RouteResult:
        import anthropic

        req = build_request(spec, system, messages, bedrock=self.bedrock)
        client = self.client().with_options(timeout=spec.timeout_s, max_retries=1)
        try:
            create = client.beta.messages.create if "betas" in req else client.messages.create
            response = create(**req)
        except anthropic.APITimeoutError:
            raise RouteError("timeout") from None
        except anthropic.RateLimitError:
            raise RouteError("rate_limited") from None
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise RouteError("auth") from None
        except anthropic.BadRequestError:
            raise RouteError("bad_request") from None
        except anthropic.APIStatusError as exc:
            raise RouteError("server_error" if exc.status_code >= 500 else "api_error") from None
        except anthropic.APIConnectionError:
            raise RouteError("connection") from None
        except Exception:  # anything else from the SDK: a code only, never its message
            raise RouteError("sdk_error") from None
        return _result_from(response)


class AnthropicRoute(_SdkRoute):
    name = "anthropic"

    def _make_client(self) -> Any:
        import anthropic

        return anthropic.Anthropic()  # credentials from the environment (vault-injected in UAT and prod)


class BedrockRoute(_SdkRoute):
    name = "bedrock"
    bedrock = True

    def _make_client(self) -> Any:
        from anthropic import AnthropicBedrockMantle

        return AnthropicBedrockMantle(aws_region=get_settings().aws_region)


# ---- fake ---------------------------------------------------------------------------------------------------

FAKE_SCRIPT: deque[Any] = deque()  # tests push outputs (dict or str) or exceptions, consumed in order
_FAKE_LATENCY = {  # median and 95th percentile seconds, per tier (AT-B4-09)
    "fast": (0.8, 1.8),
    "reasoning": (2.6, 4.6),
}


def _fake_sleep(tier: str) -> None:
    if get_settings().llm_fake_latency != "realistic":
        return
    median, p95 = _FAKE_LATENCY[tier]
    sigma = math.log(p95 / median) / 1.645
    time.sleep(min(random.lognormvariate(math.log(median), sigma), p95 * 2))


class FakeRoute:
    """Schema-valid outputs without a model (LLM_MODE=fake). A scripted item wins; then an example whose input
    equals the tagged input; then an output built from the input by `gateway.fakes` for that agent."""

    name = "fake"

    def call(
        self, spec: AgentSpec, system: str, messages: list[dict[str, Any]], inputs: dict[str, Any]
    ) -> RouteResult:
        from gateway import fakes

        _fake_sleep(spec.tier)
        if FAKE_SCRIPT:
            item = FAKE_SCRIPT.popleft()
            if isinstance(item, BaseException):
                raise item
            text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        else:
            text = json.dumps(fakes.output_for(spec, inputs), ensure_ascii=False)
        prompt_chars = len(system) + sum(len(str(m.get("content", ""))) for m in messages)
        return RouteResult(
            text=text,
            model=f"fake-{spec.model}",
            input_tokens=prompt_chars // 4,
            output_tokens=len(text) // 4,
        )


_routes: dict[str, Route] = {}


def get_route() -> Route:
    mode = get_settings().llm_mode
    if mode not in _routes:
        if mode == "fake":
            _routes[mode] = FakeRoute()
        elif mode == "anthropic":
            _routes[mode] = AnthropicRoute()
        elif mode == "bedrock":
            _routes[mode] = BedrockRoute()
        else:
            raise RouteError("unknown_route")
    return _routes[mode]
