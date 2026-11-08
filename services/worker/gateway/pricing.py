"""Cost in rupees for `llm_calls` (§3.2 step 9). US dollar list prices per million tokens on the Claude API
(Bedrock is billed by AWS at its own rates; this is the estimate the budget uses). Rate from settings."""

from __future__ import annotations

from core.config import get_settings

# model: (input, output, cache write 5 min, cache read) in USD per million tokens
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),  # prompts up to 100K tokens
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
}


def cost_inr(
    model: str, input_tokens: int, output_tokens: int, cache_write: int = 0, cache_read: int = 0
) -> float:
    if model.startswith("fake-"):
        return 0.0  # fake mode spends nothing
    base = model.removeprefix("anthropic.")
    p_in, p_out, p_write, p_read = PRICES.get(base, PRICES["claude-sonnet-5-5"])  # unknown: price high
    usd = (
        input_tokens * p_in + output_tokens * p_out + cache_write * p_write + cache_read * p_read
    ) / 1_000_000
    return round(usd * get_settings().llm_usd_to_inr, 4)
