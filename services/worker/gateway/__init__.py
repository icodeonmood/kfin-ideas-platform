"""LLM gateway: the ONLY package allowed to import a model SDK (non-negotiable 1).

`run_agent(name, inputs, ref_id)` runs the nine steps of ARCHITECTURE §3.2 (see `gateway/core.py`).
CI enforces the import rule twice: ruff's banned-api list and `scripts/ci/check_no_model_sdk.py`.
"""

from gateway.core import (
    AgentFailed,
    AgentSwitchedOff,
    LeakAbort,
    RateLimited,
    ValidatedOutput,
    run_agent,
)

__all__ = ["AgentFailed", "AgentSwitchedOff", "LeakAbort", "RateLimited", "ValidatedOutput", "run_agent"]
