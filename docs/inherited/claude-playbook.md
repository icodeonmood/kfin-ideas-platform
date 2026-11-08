<!-- inherited-from: Product-Manager-Skills/CLAUDE.md (skill anatomy, tone rules, quality checklist only), Product-Manager-Skills/.claude/agents/phase-05-build.md, phase-06-test.md, phase-07-review.md, notion-sync-agent.md and Product-Manager-Skills/docs/plans/garage-whitepaper.md §9 @ b7138ec on 2026-11-08; do not edit by hand, re-run the inheritance step -->

# Claude playbook conventions (summary)

**There is no document called "Claude Playbook" in the Garage project.** The nearest equivalents are the conventions the Garage's own agents follow and the skills library's writing rules. They are summarised here in our words. The drafts in `agents/` stay authoritative for this repo (`docs/GARAGE_INHERITANCE.md`, item 7, "if not found").

## Agent shape

- **One job per agent.** Each agent has a single responsibility and a fixed input and output contract. (Ours: `agents/<name>/prompt.md`, `schema.json`, `config.yaml`.)
- **Fixed output contract, checked by code.** Garage phase agents always return the same fields (`status`, `gate-recommendation`, `notes`, `cap-reached`). Ours return schema-validated JSON through the gateway.
- **No hard-coded product values in the prompt or agent file.** Everything specific comes in at run time. (Ours: thresholds from `rules/`, taxonomy slices from the router.)
- **Load conventions before acting; never guess.** The build agent reads the target repo's `CLAUDE.md` before writing anything.
- **Leave a record before returning.** A Garage phase that returns without writing its audit entry has not finished. (Ours: every call writes an `llm_calls` row, without text.)

## Prompt writing

From the skills library's writing rules, the parts that apply to agent prompts:

| Do | Don't |
|---|---|
| Write so an agent can act without asking questions: self-contained, terms defined | Assume context the agent does not have |
| Short sentences, active voice, numbered steps where order matters | Filler, hedging, moralising |
| Name the trade-off and take a stance | List options without a recommendation |
| Give concrete examples, good and bad | Generic examples |
| Make it skimmable: headings and tables carry most of the meaning | Long prose |

Their quality check before calling a prompt done: agent-ready, self-contained, at least one concrete example, opinionated, skimmable, no fluff.

## Retries, caps and failure

- **Cap retries.** Garage phases stop after 3 iterations and hand the decision to a person. (Ours: one retry with the validation error, then `AgentFailed` and the fallback path, §3.2 step 6.)
- **Fail loudly, keep going safely.** Sync failures are written down with a full snapshot so they can be replayed; the main flow continues. (Ours: `scan.async`, outbox replay.)
- **Severity classes for review findings:** Critical blocks, Major needs a person to know, Minor is advisory.

## Examples, evaluation and versioning

- **Acceptance criteria carry their test input and expected output**, with fixtures for complex cases. (Ours: golden sets in `eval/golden/`, synthetic only.)
- **The contract file is changed first, then the code.** A schema change starts in the schema file. (Ours: `schema.json` and `config.yaml` version bump, `CHANGELOG.md` line, `make eval` before merge.)
- **Versions are semver strings; Git history is the audit trail.** No extra version fields where Git already records the change.
- **Gated by default until trust is earned.** Autonomy is switched on per action type only after a track record. (Ours: §5.6, off at launch.)

Not carried over: anything about the skills library's own authoring process, its contributors or its release history.
