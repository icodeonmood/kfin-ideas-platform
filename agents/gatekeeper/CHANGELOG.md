# gatekeeper changelog

| Version | Date | Change | Golden-set result |
|---|---|---|---|
| 0.1.0 | 8 Nov 2026 | First draft from the architecture handoff (v0.3) | Not run yet |
| 0.2.0 | 9 Nov 2026 | Runtime only, prompt unchanged: `temperature` replaced by `effort: low` and `thinking: off`, because Claude Haiku 5.5 and Sonnet 5.5 reject non-default sampling (BLD-070) | Harness passes in fake mode; real-route numbers in UAT |
| 0.2.0 (no bump) | 23 Nov 2026 | Golden set grown to 151 cases, 61 must-block and 90 must-pass (BLD-C230); no prompt or config change | Fake-mode harness in CI; real-route numbers from `make eval-live` (BLD-C229) |
