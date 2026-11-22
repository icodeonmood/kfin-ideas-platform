# gatekeeper changelog

| Version | Date | Change | Golden-set result |
|---|---|---|---|
| 0.1.0 | 8 Nov 2026 | First draft from the architecture handoff (v0.3) | Not run yet |
| 0.2.0 | 9 Nov 2026 | Runtime only, prompt unchanged: `temperature` replaced by `effort: low` and `thinking: off`, because Claude Haiku 5.5 and Sonnet 5.5 reject non-default sampling (BLD-070) | Harness passes in fake mode; real-route numbers in UAT |
| 0.2.0 (unchanged) | 22 Nov 2026 | No prompt or config change. UAT runs `LLM_MODE=fake` at launch, so the real-route numbers come from `make eval-live` (BLD-C229): the golden set on the real model route and a throwaway database, run by the product lead (or on the launch server, BLD-A245) | Real-route numbers from `make eval-live`'s paste block |
