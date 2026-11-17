# draft-part changelog

| Version | Date | Change | Golden-set result |
|---|---|---|---|
| 0.1.0 | 17 Nov 2026 | First version (L-DRAFT.parts, BLD-C072): replaces `canvas-assist` for the live draft. One agent asked once per part (title and summary, how often, who it affects, what it's worth, area), the parts in parallel. Every answer quotes the person's own words, checked by the gateway with the DEC-095 rules from `grounding.py` (re-ask once, then drop); an English copy of a voice note or another language is context only (DEC-108) | Fake-mode harness passes (no-stack test); real-route numbers in UAT |
| 0.1.1 | 17 Nov 2026 | Examples only: the who-it-affects list uses L-SORT's labels ("AMC clients", "Issuer and corporate clients"); when `rules/sorting.md` is present its lists are the ones offered, with the cues from `rules/drafting.md` | Fake-mode harness passes |
