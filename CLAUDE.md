# The Garage · Ideas Platform — guide for Claude Code

This repo (`kfin-ideas-platform`) is the application code for KFintech's org-wide ideas platform, a sub-brand under The Garage. Any employee signs in with SSO and submits a problem, a fix or a business idea on a guided canvas. AI checks it for personal data, helps complete the canvas and finds colleagues working on the same thing. The review desk decides, the 1% Club core committee can see everything and veto, and accepted ideas go to the Garage delivery pipeline or a non-tech fix track.

**Launch:** org-wide at the new office inauguration, Friday 20 November 2026. **Owner:** Product & Strategy Lead, Domestic Business (product team owns the POC).

---

## Read these first, in this order

| File | Why |
|---|---|
| `docs/DECISIONS.md` | What has been decided and must not be re-opened without asking |
| `docs/DAY1_PLAN.md` | Blocks B1–B8, dates, and the acceptance tests that define "done" |
| `docs/ARCHITECTURE.md` (v0.3) | The full specification. Day-one sections: §2 data, §3.1–3.7 shared services, §4.1–4.4, §6, §7, §8, §9 |
| `docs/GARAGE_INHERITANCE.md` | Your first task: copy what this project needs from the Garage project |
| `agents/*/` | Draft prompts, schemas and configs for `gatekeeper`, `canvas-assist` and `judge` |
| `seed/company-repo/` | Starting content for the company repo (rules, taxonomy, glossary, comms templates, canvas examples) |
| `eval/golden/` | Golden-set format, synthetic cases and pass gates |

`docs/diagrams/ideas-platform-diagrams.html` has the three drawn diagrams (journey, layers, tech). Open it in a browser if you need the picture.

## Two repos, do not mix them up

| Repo | What it holds | Who writes it |
|---|---|---|
| `kfin-ideas-platform` (this one) | Code, migrations, agents, seed content, tests | You |
| `kfin-ideas` (company repo) | OKF Markdown knowledge bundle: ideas, clusters, decisions, rules, taxonomy | **Only the repo writer service**, from the outbox. Seeded once from `seed/company-repo/` |

In dev the company repo lives at `$COMPANY_REPO_PATH` (default `./.data/kfin-ideas`), created by `make seed`. Never hand-edit it in code paths; tests may read it.

## Non-negotiables

Stop and ask the user before changing any of these.

1. **Every model call goes through the gateway** (`run_agent` in `services/worker/gateway/`). No model SDK import anywhere else; CI enforces it.
2. **Tag before sending.** Personal and sensitive values become typed tags (`[[KFIN_EMPLOYEE_1]]`, `[[CLIENT_AMC_1]]`…) before any model call. The leak check re-runs the patterns on the tagged payload and aborts on any hit. Real values are restored only for viewers allowed to see them (§3.2).
3. **No idea text, attachment text or personal data in logs, traces, error messages, analytics or `llm_calls`.** Logs carry IDs only. A log-scrubber test must pass.
4. **Investor and customer identifiers are blocked at submission** (patterns in §4.2 step 2, then `gatekeeper`).
5. **Agents propose; people decide.** Agents never write to the company repo or change a stage on their own on day one. Autonomy (§5.6) is off at launch.
6. **Database only, never the repo or the search index:** core briefs, sealed scores, assessments, decision sheets, the people view, the pseudonym vault, contributor-to-employee mapping. Use row-level security where §2.5 says so.
7. **Submitters never see another person's raw text, files or name.** Match cards show `neutral_summary`, area tag, stage and count only (§4.2 step 7).
8. **Links are never fetched. Files are never opened before they pass the checks** (virus scan, then personal-data check).
9. **Kill switches are checked on every request** (§7.6) and every privileged action is written to `audit_log`.
10. **WCAG 2.1 AA** on every employee-facing screen (§7.7). `axe` runs in CI.
11. **Synthetic data only** in dev, UAT, tests, fixtures, examples and prompts. Never paste real employee, investor or client data anywhere in this repo.
12. **Garage:** copy only what `docs/GARAGE_INHERITANCE.md` lists. Never copy the whole `~/the-garage` folder, its Git history, secrets, tokens or anyone's personal notes, and never read projects in `~/the-garage` other than the Garage programme project.

## Stack (defaults; record any change in `docs/DECISIONS.md`)

| Layer | Choice |
|---|---|
| Web app and API | Next.js (App Router), TypeScript strict, server-side route handlers for `/api/*` |
| Worker | Python 3.12, FastAPI for `/internal/*`, job runner on the `jobs` table (`SELECT … FOR UPDATE SKIP LOCKED`) |
| Database | Postgres 16 with `pgvector` and `pg_trgm`; SQL migrations in `db/migrations/` applied with `dbmate` |
| DB access | Kysely (typed, generated types) in TypeScript; psycopg 3 in Python |
| Models | Claude through the gateway. Fast tier `claude-haiku-5-5`, reasoning tier `claude-sonnet-5-5`. Route (Anthropic API or AWS Bedrock) is set by env, per InfoSec (D1) |
| Embeddings | BGE-M3, self-hosted in the worker (1024 dimensions) |
| Personal-data detection | Shared pattern rules (one source, used by TypeScript and Python) + Microsoft Presidio with KFin recognisers |
| File store | S3-compatible (MinIO in dev): `quarantine` and `clean` buckets |
| Virus scan | ClamAV in dev; KFin's standard scanner in UAT and prod |
| Identity | Microsoft Entra ID (OIDC); a mock OIDC server in dev |
| Email | Mailpit in dev; Microsoft Graph service mailbox in UAT and prod |
| Tests | pytest, Vitest, Playwright (end-to-end), `@axe-core/playwright` |

**Dev and test modes** (set in `.env`):
- `LLM_MODE=fake` returns schema-valid outputs from `agents/<name>/examples/`, so tests never need a key. `anthropic` and `bedrock` call the real route.
- `EMBEDDINGS_MODE=hash` gives deterministic fake vectors for tests; `bge-m3` loads the real model.
- `OIDC_MODE=mock` or `entra`.

## Target layout (create it in B1)

```
kfin-ideas-platform/
├── CLAUDE.md  KICKOFF.md  Makefile  .env.example
├── docs/                ARCHITECTURE.md, DAY1_PLAN.md, DECISIONS.md, GARAGE_INHERITANCE.md, BUILD_LOG.md, inherited/, diagrams/
├── contracts/garage/    copied from the Garage project (handoff schemas, pipeline properties, phases)
├── apps/web/            Next.js app: pages, components, /api route handlers, RBAC, kill-switch middleware
├── services/worker/
│   ├── gateway/         run_agent: tag, leak check, wrap, cache, rate control, validate, tag check, restore, log
│   ├── pii/             pattern rules (shared vectors), Presidio recognisers, tagger, vault
│   ├── scan/  match/  embeddings/  index/  repo_writer/  attachments/  comms/  sla/  rules/  jobs/
├── agents/<name>/       prompt.md, schema.json, config.yaml, examples/, CHANGELOG.md
├── db/migrations/       numbered SQL files
├── seed/company-repo/   initial content of kfin-ideas
├── eval/golden/         golden sets, generators, runner
└── infra/               docker-compose.yml (postgres+pgvector, minio, clamav, mock-oidc, mailpit, worker, web)
```

## Commands (create the Makefile in B1)

| Command | Does |
|---|---|
| `make up` / `make down` | Start or stop the local stack |
| `make migrate` | Apply migrations |
| `make seed` | Create the local company repo from `seed/company-repo/`, validate it, index it, load synthetic users |
| `make test` | Unit and integration tests |
| `make e2e` | Playwright end-to-end and accessibility checks |
| `make eval` | Golden sets for every agent; fails on regression |
| `make lint` | ESLint, Prettier, ruff, mypy, the OKF validator, the no-SDK-outside-gateway rule, the log-scrubber test |

## How to work

1. Work block by block in `docs/DAY1_PLAN.md`. Do not start a block until the previous block's acceptance tests pass, unless the plan says the blocks can overlap.
2. At the end of each block: run `make lint test e2e` (and `make eval` from B4), tick the block in `DAY1_PLAN.md`, and add a dated entry to `docs/BUILD_LOG.md`: what is done, what was deferred, anything the user must do.
3. When the spec is unclear, take the simpler reading that keeps every non-negotiable, write it in `docs/DECISIONS.md` (next ID, date, decision, reason, alternative) and carry on. If it touches a non-negotiable, stop and ask.
4. If a block runs more than half a day late, propose a cut from the drop order in §9.2 rather than squeezing quality.
5. Small commits with clear messages. Never commit `.env`, data folders, model weights or anything from `~/the-garage` that is not listed for copying.
6. Agent changes: bump the version in `config.yaml`, add a `CHANGELOG.md` line, and run `make eval` before merging.

## Stop and ask the user when

- you need real credentials, real employee data, or access to any KFin system;
- you want to read anything in `~/the-garage` beyond what `docs/GARAGE_INHERITANCE.md` lists;
- a non-negotiable would have to bend;
- a dependency from another team (IT, InfoSec, HR, Legal) blocks a block. Say which item in §9.1 and what the fallback is.

## Words on screen

Employees are not engineers. All UI copy, messages and help text use plain Indian business English, short sentences and no internal jargon. Use the platform's own words: **canvas**, **In the Garage** and **Find your crew** for matches, **review desk**, **1% Club core committee**. Never show a submitter "duplicate", "rejected" or "already solved". Message wording comes from `comms/templates/` in the company repo, which HR signs off.
