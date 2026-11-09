# judge changelog

| Version | Date | Change | Golden-set result |
|---|---|---|---|
| 0.1.0 | 8 Nov 2026 | First draft from the architecture handoff (v0.3) | Not run yet |
| 0.2.0 | 9 Nov 2026 | Runtime only, prompt unchanged: `temperature` replaced by `effort: medium` and `thinking: off`, because Claude Haiku 5.5 and Sonnet 5.5 reject non-default sampling (BLD-070) | Harness passes in fake mode; real-route numbers in UAT |
| 0.2.1 | 8 Nov 2026 | Runtime only: `past_corrections` wrapped as untrusted input, as for canvas-assist (B4 review) | Harness passes in fake mode |
| 0.2.2 | 9 Nov 2026 | Prompt quotes the new match heading "Colleagues are on this" (1% Club rename, DEC-035/038); no change to labels or rules | Run with the brand pass (`make eval`) |
