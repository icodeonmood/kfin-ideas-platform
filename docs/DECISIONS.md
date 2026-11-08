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
| | | | | | |
