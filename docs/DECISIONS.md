# Decisions

What has been decided, by whom, and why. Claude Code adds build decisions at the bottom (next free ID, newest last). Anything in **Product decisions** needs the product lead's agreement to change.

**Status:** `Decided` — settled. `Default` — applied until the named owner confirms or overrides. `Open` — see `ARCHITECTURE.md` §11.

## Product decisions

| ID | Date | Decision | Why | Status | Owner |
|---|---|---|---|---|---|
| DEC-001 | 6 Nov 2026 | The platform is a **sub-brand under The Garage** ("The Garage · Ideas"), not a separate programme | The Garage already runs delivery; one brand keeps the path from idea to shipped product visible | Decided | Product lead |
| DEC-002 | 6 Nov 2026 | **Org-wide on day one**, launched at the new office inauguration (~20 Nov 2026) | Launch moment and leadership visibility | Decided | Product lead |
| DEC-003 | 6 Nov 2026 | Three kinds of submission: **problem**, **problem with a solution**, **business idea** | Not everyone has a fix; business ideas need different questions | Decided | Product lead |
| DEC-004 | 6 Nov 2026 | **Category** is the submitter's call: cost saving, new revenue, both, not sure yet. **Play**: process improvement, upsell, cross-sell, new product, other | Committees sort first on value to KFintech; the submitter knows best | Decided | Product lead |
| DEC-005 | 6 Nov 2026 | The canvas is a **thinking aid**, not a form: plain questions, "why we ask", real examples, strength meter that guides and never blocks, assistant suggests and the person decides | People should ask themselves the right questions and come back to improve ideas | Decided | Product lead |
| DEC-006 | 6 Nov 2026 | **Attachments allowed** (up to 5 research files), plus references as links or notes on whether it is solved elsewhere and KFintech's advantage | Research already done saves weeks later | Decided | Product lead |
| DEC-007 | 6 Nov 2026 | **Build-vs-buy and priority classification** are produced for the core committee only, stored in the database only | Vendor names, prices and priority judgements are commercially sensitive | Decided | Product lead |
| DEC-008 | 6 Nov 2026 | **Personal data is replaced with typed tags** that say what the value is before any model call, and restored only when an authorised viewer sees the final artefact | Keeps real values away from the model while the model can still reason | Decided | Product lead, InfoSec |
| DEC-009 | 6 Nov 2026 | Review, shortlisting and acceptance are owned by the **1% Club core committee** | One accountable body | Decided | Product lead |
| DEC-010 | 7 Nov 2026 | **Review desk decides; the core committee sees everything and can veto** within 5 working days, with a reason. The submitter hears only the final outcome | Speed at launch volume with committee control; vetoes become learning | Decided | Product lead |
| DEC-011 | 6 Nov 2026 | Individual committee assessments are **sealed** and **collated** for the final discussion; the platform **learns** from committee decisions through proposals a named person approves | Independent judgement first; transparent learning | Decided | Product lead |
| DEC-012 | 6 Nov 2026 | Path after the preliminary review: **invitation to present** (pitch, then Q&A) → **accepted** → **working group** and **1% Club** | Acceptance is earned in the room, not by score alone | Decided | Product lead |
| DEC-013 | 7 Nov 2026 | **No fixed pitch or Q&A timings** for now; the core committee sets them later in `rules/routing.md` | Learn from the first sessions | Decided | Product lead |
| DEC-014 | 7 Nov 2026 | **No product buddy.** Only contributors present | Ownership stays with the people who raised it | Decided | Product lead |
| DEC-015 | 7 Nov 2026 | Matches are framed as **Find your crew** and **In the Garage**, never "duplicate" or "already solved" | A match should feel like an invitation to team up | Decided | Product lead |
| DEC-016 | 7 Nov 2026 | Recognition path after acceptance: **work → create → showcase → perks and rewards → mentor the next 1%**. Perks are proposals until HR and Finance approve | Recognition is more than points | Decided (perks pending O9) | Product lead, HR, Finance |
| DEC-017 | 7 Nov 2026 | **Appeals** against core committee decisions are heard by 3 rotating core committee members (conflicted members and the brief owner excluded). **No outside seat for now**; switchable later (`appeals.outside_seat`) | Keep it simple at launch; option preserved | Decided | Product lead |
| DEC-018 | 7 Nov 2026 | **Comeback routes dropped** (no demand route, no sponsor route). Appeals are the only route; a declined idea can be resubmitted after 12 months | Fewer paths, clearer rules | Decided | Product lead |
| DEC-019 | 6 Nov 2026 | A **communication module** tells every stakeholder what happened, why, what next and by when; key moments are signed by a person | Silence kills participation | Decided | Product lead |
| DEC-020 | 6 Nov 2026 | Knowledge lives in a **company repo** in Open Knowledge Format (OKF v0.2); search (RAG) is an index rebuilt from it; the app database holds operations | Durable, auditable, portable memory; search can be rebuilt any time | Decided | Product lead |
| DEC-021 | 8 Nov 2026 | App code repo is `kfin-ideas-platform` at `~/rome/kfin-ideas-platform`; it **copies what it needs** from the Garage project (`docs/GARAGE_INHERITANCE.md`) | Shareable repo outside the private workspace; no runtime dependency | Decided | Product lead |
| DEC-022 | 8 Nov 2026 | Day-one attachments: virus scan and text-layer personal-data check; images and scanned pages held as "awaiting check" until OCR in week 3; `attachment-digest` in week 3 (D3) | Fits the 8 working days left after Diwali without weakening checks | Decided | Product lead |
| DEC-023 | 8 Nov 2026 | Scan progress by **polling** on day one; server-sent events in week 3 | Simpler and enough for launch | Decided | Product lead |
| DEC-024 | 8 Nov 2026 | **Three launch modes** (Full, Capture first, Preview) chosen at go/no-go on 17 and 19 Nov (§9.3) | The date holds even if an approval is late | Decided | Product lead |
| DEC-025 | 8 Nov 2026 | The **strength score** people see is computed by code from the rubric; `canvas-assist` only suggests the next two additions | Same score everywhere; explainable | Decided | Product lead |
| DEC-026 | 8 Nov 2026 | Match cards show only a `neutral_summary` written by `canvas-assist` (no tags, names or client names), area tag, stage and count | Submitters never see others' raw text | Decided | Product lead |

## Defaults awaiting confirmation (from ARCHITECTURE "Defaults applied")

| ID | Default | Confirm with |
|---|---|---|
| D1 | Provider-neutral gateway; Anthropic API or AWS Bedrock, whichever InfoSec clears; zero data retention; agreed region | InfoSec |
| D2 | KFin private infrastructure, India region, containers | IT, InfoSec |
| D4 | Ideas visible org-wide; submitter can choose "committee only" with a reason | Product |
| D5 | Scorecard and priority weights as in `rules/`; 1% Club = accepted after presenting | Core committee, HR, Finance |
| D6 | Next.js + Postgres 16/pgvector + Python worker | Tech |
| D8 | Blind scoring | Core committee |
| D9 | People view for admins and committees only; each person sees their own | HR |

## Build defaults (Claude Code may revise; record the change below)

| ID | Default | Reason |
|---|---|---|
| BLD-001 | SQL migrations with `dbmate`; Kysely with generated types in TypeScript; psycopg 3 in Python | One schema source for two languages |
| BLD-002 | `LLM_MODE=fake` in tests (outputs from `agents/<name>/examples/`) | Tests never need a key or network |
| BLD-003 | `EMBEDDINGS_MODE=hash` in tests; BGE-M3 in UAT and prod | Fast deterministic tests |
| BLD-004 | Dev services: MinIO, ClamAV, a mock OIDC server, Mailpit | Local stack mirrors production roles |
| BLD-005 | One personal-data pattern file (YAML) loaded by both TypeScript and Python, with shared test vectors | Browser and server must agree |
| BLD-006 | Kill switches cached for 10 seconds | Fast to flip, cheap to check |

## Decisions made during the build

| ID | Date | Decision | Reason | Alternative considered | Reversible? |
|---|---|---|---|---|---|
| BLD-007 | 8 Nov 2026 | Garage source for inheritance is `~/the-garage/Product-Manager-Skills` (main checkout, commit `b7138ec`). Its two worktrees (`.worktrees/fable5`, `.worktrees/irta-dip`) also matched the folder search but are branches of the same project; the four contract schemas are byte-identical on every branch and on `main` (`902e66d`). Only `handoff`, `spec`, `status` and `audit` schemas copied; the six `dw-*` schemas belong to Dream Walker, an unrelated tool | Exactly one project holds the delivery harness; the choice of checkout does not change the contract | Wait for the user to pick a worktree | Yes: re-run inheritance from another checkout |
| BLD-008 | 8 Nov 2026 | When the platform creates a Garage Notion entry (§4.8), it leaves `pipeline-started` empty and sets `gate-status: clear` | Garage contract: `pipeline-started` is the Phase 04 start timestamp, written by the Garage's `in-build` event. The contract wins | Set it to the handover date, as §4.8 had it | Yes |
| BLD-009 | 8 Nov 2026 | The platform-created Notion page is adopted by the Garage's own `spec-approved` sync, which finds pages by `feature-slug`. The Garage's delivery folder must use the slug the platform wrote (`<slug>-cl0012`). After that, `mode`, `compliance-tier`, `product` and `feature-type` follow the PM's `handoff.md` | Matches the Garage's lookup-then-create rule; avoids duplicate pages without writing Garage files | Let the Garage create the page and link it back by hand | Yes |
| BLD-010 | 8 Nov 2026 | `rules/compliance-tier.md` (seed) replaced with the Garage's tier rules: adds AMC integrations, SEBI/PFRDA/RBI surface and regulated products (LAMF, NPS, SIF, IRIS transaction flows) to **standard**. Our own qualify triggers (`AREA-compliance`, submitter-named risk) kept under `platform_standard_if_any` | Garage contract wins for tiers; our extras only make items more cautious | Keep the architecture draft | Yes |
| BLD-011 | 8 Nov 2026 | Week-6 handover pack must carry the Garage `owner` (PM identifier). The platform never writes `handoff.md`, `status.md` or anything in a Garage `delivery/` folder | Garage write authority: `handoff.md` PM-only, `status.md` pipeline-only | Platform pre-fills `handoff.md` | Yes |
| BLD-012 | 8 Nov 2026 | `source-cluster` stays a platform addition to the Garage Notion database. The Garage's `notion-setup-agent` defines 17 properties, so the product lead must add `source-cluster` there as property 18 (Garage project change, week 4, §9.1) | A fresh Garage setup would otherwise lack the property `garage.sync` needs | Match on `feature-slug` suffix only | Yes |
| BLD-013 | 8 Nov 2026 | No Garage brand assets (logo, colour or type tokens) exist in the Garage project. The web app uses plain neutral styling, flagged for design. No other design system substituted | `GARAGE_INHERITANCE.md` item 8 "if not found" | Borrow tokens from another project in the workspace | Yes |
| BLD-014 | 8 Nov 2026 | No Garage feature-brief template exists; §4.8 brief fields (problem, users, opportunity, constraints) stand, and they match the Garage's 01-discover output. The skills library's generic PRD template is not copied | Item 6 "if not found"; no copying "just in case" | Copy the 659-line PRD template | Yes |
| BLD-015 | 8 Nov 2026 | No "Claude Playbook" document exists. `docs/inherited/claude-playbook.md` summarises the nearest conventions; `agents/` drafts stay authoritative | Item 7 "if not found" | — | Yes |
| BLD-016 | 8 Nov 2026 | Provenance for an inherited OKF file (`rules/compliance-tier.md`) goes in frontmatter (`kfin.inherited_from`) and as the first body line, not as the file's first line | OKF requires the file to open with `---` frontmatter; a leading comment would break every parser | Leading HTML comment as `GARAGE_INHERITANCE.md` rule 5 says literally | Yes |
