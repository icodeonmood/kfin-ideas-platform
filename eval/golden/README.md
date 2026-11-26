# Golden sets

Fixed test cases every agent must pass before a version reaches UAT or production (`make eval`, job `golden.eval`). A regression against the last passing version blocks the deploy (§5.5).

**Everything here is synthetic.** Personal-data values are placeholders (`{{PAN}}`, `{{PERSON_NAME}}` …) filled at run time by the generators in `generators.md`. Never commit real or real-looking identifiers, and never copy text from real submissions. When reviewer corrections suggest a new case, write a fresh synthetic version of it.

## Files

| File | Agent | Cases now | Target before go-live (17 Nov) | Pass gates |
|---|---|---|---|---|
| `gatekeeper.jsonl` | `gatekeeper` plus the pattern layer | 151: 61 must-block, 90 must-pass (BLD-C230) | 120: every pattern ×3 variants, 30 gatekeeper-layer personal-data cases, 10 per kind, 10 injection, 10 Hinglish or regional, 10 attachment-mode | Personal-data recall **100%** (pipeline: patterns + tagging + gatekeeper); false blocks **≤ 5%**; kind accuracy **≥ 85%** |
| `judge.jsonl` | `judge` | 40 sets: 123 labels, 41 "same" (BLD-C230) | 40 sets (about 120 labels) across MF, SIF, AIF/PMS, NPS, Corporate Registry, functions and business ideas | Precision of "same" **≥ 0.85**; recall of "same" **≥ 0.75** |
| `canvas_assist.jsonl` | `canvas-assist` | 9 | 25 | Submitter-field changes **0**; IDs outside the taxonomy slice **0**; `neutral_summary` leaks **0**; suggestions without the person's own words, or figures that do not follow from their numbers and the allowed assumptions, after the gateway **0** (DEC-095, DEC-097); area-tag accuracy **≥ 0.8** |
| `handover_draft.jsonl` | `handover-draft` (BLD-138) | 6 | 30 across build, fix and procurement, single ideas and groups | Unit accuracy **≥ 0.8**; numbers grounded **100%** (never a number nobody gave); objective on the fix track only **100%** |
| `role_themes.jsonl` | `role-themes` (BLD-139) | 4 | 20 roles across MF, Corporate Registry, NPS, distribution and functions, including roles where nothing recurs | Pair precision **≥ 0.8**; coverage **≥ 0.6**; names and descriptions card-safe (enforced by the gateway) |
| `attachments-pii/` (week 3) | attachment pipeline | — | 50 synthetic files across every format | Recall 100% |

Grow the sets by writing synthetic variants of the seed cases: other LOBs, other phrasings, Hinglish, typos, long and short texts. Claude Code can draft them; a product team member checks the expected labels.

When writing gatekeeper must-pass text, keep long digit runs away from the words the patterns look for: 6 or more digits within 30 characters of "folio", 9 or more near "a/c", "account" or "bank", 12 near "PRAN", or any date near "born", "birth" or "DOB" will block. Keep the must-pass count off a multiple of 20, so that "≤ 5%" and "< 5%" agree. In `judge.jsonl`, keep digit runs, "folio" and birth words out of cards and candidates, because the gateway's leak check scans the whole payload, cids included.

## Case formats

**gatekeeper.jsonl** — one JSON object per line:
```json
{"id": "GK-G01", "layer": "pattern|gatekeeper", "input": {"mode": "submission", "submission": {"one_line": "…", "details": "… {{PERSON_NAME}} …"}},
 "expected": {"block": true, "data_types": ["tagged_person_as_investor"], "kind": "idea_problem", "warn": false, "redirect": false, "hold": false}}
```
- `layer: pattern` cases must be caught by the pattern check before any model call (the gatekeeper is not called). `layer: gatekeeper` cases pass the patterns and must be caught by tagging plus `gatekeeper`.
- `block` is judged after thresholds from `rules/thresholds.md` are applied, exactly as production does.
- Placeholders such as `{{PERSON_NAME}}` and `{{COLLEAGUE_NAME}}` go through the real tagger, so the gatekeeper sees `[[PERSON_1]]` or `[[KFIN_EMPLOYEE_1]]` as it would in production. `{{COLLEAGUE_NAME}}` must be drawn from the synthetic `users` table so the tagger recognises it.

**judge.jsonl** — card, candidates and expected label per candidate `cid`.

**canvas_assist.jsonl** — input (or a pointer to an example in `agents/canvas-assist/examples/`) and `expected_properties`, checked by code, because suggestions vary in wording.

## Running

- `make eval` runs all sets with `LLM_MODE` from the environment. With `LLM_MODE=fake` it only checks the harness; real numbers need the real route in UAT.
- The runner writes `eval/reports/<agent>-<version>-<date>.json` and a one-line summary per agent: cases, pass rate per gate, regressions against the last passing report.
- Fixed seed for generators (`GOLDEN_SEED`, default 42) so runs are repeatable.
