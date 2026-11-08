"""LLM gateway: the ONLY package allowed to import a model SDK (non-negotiable 1).

`run_agent(name, inputs, ref_id)` arrives in B4 with all nine steps of ARCHITECTURE §3.2: tag, leak check,
untrusted wrapping, cache, rate control, call and validate, tag check, store tagged, log.
CI enforces the import rule twice: ruff's banned-api list and `scripts/ci/check_no_model_sdk.py`.
"""
