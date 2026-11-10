# canvas-assist changelog

| Version | Date | Change | Golden-set result |
|---|---|---|---|
| 0.1.0 | 8 Nov 2026 | First draft from the architecture handoff (v0.3) | Not run yet |
| 0.2.0 | 9 Nov 2026 | Runtime only, prompt unchanged: `temperature` replaced by `effort: medium` and `thinking: off`, because Claude Haiku 5.5 and Sonnet 5.5 reject non-default sampling (BLD-070) | Harness passes in fake mode; real-route numbers in UAT |
| 0.2.1 | 10 Nov 2026 | Runtime only: `past_corrections` is wrapped as untrusted input (reviewer notes carry text from people), from the B4 review | Harness passes in fake mode |
| 0.3.0 | 11 Nov 2026 | Only the person's own words (DEC-095, BLD-C020): every suggestion and the neutral summary carry `evidence`, 1 to 3 exact quotes from the person's own text; the gateway checks each quote, re-asks once, then drops what is still unsupported. No outside numbers in estimates; risks the person did not name go to the reviewer as flags. Examples 01 and 02 rewritten to match; golden cases CA-05 to CA-07 | Fake-mode harness passes (no-stack test); real-route numbers in UAT |
