# The Garage · Ideas Platform — guide for Claude Code

This repo (`kfin-ideas-platform`) is the application code for KFintech's org-wide ideas platform, the 1% Club, a sub-brand under The Garage. Any employee signs in with SSO and shares a problem in their own words (Tell it), checks the draft the assistant builds from those words, with customers' personal details hidden (Check it), and sends it (Send it). The review desk decides (Picked, Not now, Not picked) with a reason the sharer reads; the Ones Committee can extend or reverse a decision inside its window. Picked ideas get a build team, shipped ideas are measured, and the people behind them become Ones. Since 16 Nov 2026 the product is built to the design handoff pack in `1pc-handoff/` (DEC-102).

**Launch:** org-wide at the new office inauguration, Friday 20 November 2026. **Owner:** Product & Strategy Lead, Domestic Business (product team owns the POC).

---

## Read these first, in this order

| File | Why |
|---|---|
| `1pc-handoff/README.md`, then `00-overview/PRODUCT.md` | The design and behaviour spec: the source of truth for how the product looks, moves, reads and behaves (DEC-102). Read the README once |
| `docs/SHIP_PLAN_1PC.md` | The plan for shipping the pack: lanes, checkpoints, data, retirements |
| `docs/DECISIONS.md` | What has been decided and must not be re-opened without asking |
| `docs/DAY1_PLAN.md` | **History. Do not read it.** Blocks B1 to B8 are done; the plan now is `docs/SHIP_PLAN_1PC.md` (BLD-G001) |
| `docs/ARCHITECTURE.md` (v0.3) | **Read only the section a non-negotiable cites.** The pack wins on product behaviour (DEC-102) |
| `docs/GARAGE_INHERITANCE.md` | Your first task: copy what this project needs from the Garage project |
| `agents/*/` | Draft prompts, schemas and configs for `gatekeeper`, `canvas-assist` and `judge` |
| `seed/company-repo/` | Starting content for the company repo (rules, taxonomy, glossary, comms templates, canvas examples) |
| `eval/golden/` | Golden-set format, synthetic cases and pass gates |

`docs/diagrams/ideas-platform-diagrams.html` has the three drawn diagrams (journey, layers, tech). Open it in a browser if you need the picture.

## Design handoff (1% Club)

The design and behaviour spec lives in `1pc-handoff/`. It is the source of truth for how the product looks, moves, reads and behaves.

- First time on this repo: read `1pc-handoff/README.md` once, then `00-overview/PRODUCT.md`.
- Do not read the whole pack for a task. Find the module by ID in `1pc-handoff/manifest.json` (it lists every module, its file, what it depends on and what uses it) and open only that file.
- IDs: `S-` screens, `C-` components, `F-` foundations, `J-` journeys, `L-` back-end logic, `E-`/`A-` contracts, `V-` validation, `P-` product. Anchors look like `S-R2.panel`; numbered lines like `S-R2.panel/3`.
- When asked to "apply D-00NN": open `1pc-handoff/CHANGELOG.md`, read that entry only, open the files under its **Read** line at the named anchors, make the change, run the `V-ACC` tests it names. The module files already describe the new state; the entry's Old column tells you what to look for in the code.
- When two sources disagree: the latest CHANGELOG entry wins. After that, the module file wins on behaviour (rules, states, validation, data); the prototype board and its screenshot win on look (layout, spacing, colour, exact copy).
- The prototype boards are a design artefact. Take values, copy and behaviour from them; never copy their structure or their demo logic. Build from `01-foundations/tokens.json` and `reference/computed/components.md`.
- Exact wording for every screen and state is in `1pc-handoff/reference/copy/<Board>.md`. Do not rewrite copy.
- Lines marked `OPEN:` or `NOT DRAWN:` give a default. Build the default; do not invent a different one. They are all listed in `00-overview/GAPS.md`.
- Keep `00-overview/REPO-MAPPING.md` current: when you build or move a screen, component or service, update its row.
- Everyone named on the boards is a fictional demo person. Never seed production with them.
- In code, reference the module ID in the test name and in the commit message (for example "Implements S-R2.panel, L-REVIEW.panel; tests V-ACC.review/1–6").

## Two repos, do not mix them up

| Repo | What it holds | Who writes it |
|---|---|---|
| `kfin-ideas-platform` (this one) | Code, migrations, agents, seed content, tests | You |
| `kfin-ideas` (company repo) | Read-only configuration: `rules/`, `taxonomy/`, `comms/` templates | Seeded from `seed/company-repo/`; changed by the programme team without a release. Since DEC-106 nothing writes ideas, clusters, decisions or appeals to it |

In dev the company repo lives at `$COMPANY_REPO_PATH` (default `./.data/kfin-ideas`), created by `make seed`. Never hand-edit it in code paths; tests may read it.

## Non-negotiables

Stop and ask the user before changing any of these.

1. **Every model call goes through the gateway** (`run_agent` in `services/worker/gateway/`). No model SDK import anywhere else; CI enforces it.
2. **Tag before sending.** Personal and sensitive values become typed tags (`[[KFIN_EMPLOYEE_1]]`, `[[CLIENT_AMC_1]]`…) before any model call. The leak check re-runs the patterns on the tagged payload and aborts on any hit. Real values are restored only for viewers allowed to see them (§3.2).
   - Exception (DEC-108): voice audio goes to Sarvam untagged; all text is masked first, and every transcript is masked as it returns. The product lead confirmed it on 17 Nov 2026 with the DPO's approval.
3. **No idea text, attachment text or personal data in logs, traces, error messages, analytics or `llm_calls`.** Logs carry IDs only. A log-scrubber test must pass.
4. **Customers' personal details are hidden from everyone but the person who typed them** (DEC-103, `L-HIDE`). Patterns, then `gatekeeper`, run on every message, transcript, edit and file before any other service sees the text. Every other person, service, model, index and log receives only the masked copy. The unmasked value is stored encrypted in a worker-only table, readable by the sharer alone. "Show it" needs one of the three reasons and is logged. Until "Hide it for me" is solid for a file's type, a file with a detail found can still be sent: it is marked as holding a customer detail and opens only for the sharer, the review desk and the Ones Committee, never for the crew, in previews or for anyone else (DEC-107).
5. **Agents propose; people decide.** Agents never write to the company repo or change a stage on their own on day one. Autonomy (§5.6) is off at launch.
6. **Database only, never the repo or the search index:** the sharer's unmasked words and hidden values, the pseudonym vault, contributor-to-employee mapping, points. The web role is revoked from the worker-only tables, and the pinned privilege test lists them.
7. **Who sees what follows `P-PRODUCT.privacy`** (DEC-104). A person's raw words go only to them, the review desk and the Ones Committee; everyone else, previews and match cards included, sees the short summary. Names show unless the sharer hides theirs from the Wall. Checked files and the conversation are for the sharer, crew, desk and committee. Points are private to the person.
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

1. Work to your lane's scope and checkpoints in `docs/SHIP_PLAN_1PC.md`.
2. At the end of each block: run `make lint test e2e` (and `make eval` from B4), and add a dated entry to `docs/BUILD_LOG.md`: what is done, what was deferred, anything the user must do.
3. When the spec is unclear, take the simpler reading that keeps every non-negotiable, write it in `docs/DECISIONS.md` (the next ID in your lane, date, decision, reason, alternative) and carry on. If it touches a non-negotiable, stop and ask.
4. If a block runs more than half a day late, propose a cut from the drop order in §9.2 rather than squeezing quality.
5. Small commits with clear messages. Never commit `.env`, data folders, model weights or anything from `~/the-garage` that is not listed for copying.
6. Agent changes: bump the version in `config.yaml`, add a `CHANGELOG.md` line, and run `make eval` before merging.
7. Decision IDs while several sessions build at once: read the note at the top of `docs/DECISIONS.md` before you write one.
   - Build decisions carry your lane's letter (`BLD-A161`, `BLD-C001`). A new session claims the next free letter in the lanes table there, on `main`, before its first build decision.
   - Product decisions keep one sequence (`DEC-096`, and on). Add them only on `main`, straight after `git pull --rebase`, and push at once.
   - `make lint` fails on a duplicate, malformed or unregistered ID.

## Stop and ask the user when

- you need real credentials, real employee data, or access to any KFin system;
- you want to read anything in `~/the-garage` beyond what `docs/GARAGE_INHERITANCE.md` lists;
- a non-negotiable would have to bend;
- a dependency from another team (IT, InfoSec, HR, Legal) blocks a block. Say which item in §9.1 and what the fallback is.

## Words on screen

Employees are not engineers. All UI copy, messages and help text use plain Indian business English, short sentences and no internal jargon. The platform is called **1% Club** on every screen, email and poster; "The Garage" is the internal project name and appears only as "Part of The Garage" in the Landing footer (`S-01`). The words are the pack's (`1pc-handoff/01-foundations/F-COPY.md`, `F-COPY.vocabulary`): **Share a problem**, **Tell it, Check it, Send it**, **your words**, **draft**, **sorting**, **similar ideas**, **Team up**, **crew**, **lead**, **review desk**, **Ones Committee**, **Picked / Not now / Not picked**, **Needs you**, the stages **Shared, Checked and matched, Reviewed, Built, Shipped**, **the Wall**, **Inbox** and **conversation**. Never say "duplicate", "rejected", "already solved", "appeal" or "invalid". Exact copy per screen and state is in `1pc-handoff/reference/copy/`; message wording comes from `comms/templates/`, which HR signs off.
