<!-- inherited-from: Product-Manager-Skills/docs/plans/garage-whitepaper.md (§1, §2, §4, §6, §7, §9, §10), Product-Manager-Skills/docs/Using the Garage Delivery Pipeline.md and Product-Manager-Skills/.claude/agents/phase-0{4..9}-*.md @ b7138ec on 2026-11-08; do not edit by hand, re-run the inheritance step -->

# Product Agent OS conventions (summary)

A summary, in our words, of how the Garage organises delivery work. It tells us what the Garage expects when an accepted idea arrives (week 6), and which of its habits this repo follows. Nothing here overrides this repo's `CLAUDE.md`.

## What the Garage is

The Garage is KFintech's AI-assisted delivery system. Work moves through four stages: S1 discover and align (people lead), S2 shape and design (AI drafts, people review), S3 validate and gate (gated approval), S4 launch and track (people lead). People own the entry and exit; AI does the work in between.

Two pipelines carry a feature. The **PM pipeline** (phases `01-discover`, `02-shape`, `03-gate`) ends with a hash-locked, gated `spec.md`. A human trigger (`/showtime`) then starts the **dev pipeline** (`04-handoff` to `09-deploy`), which builds, tests, reviews, QAs and deploys. The phase list and gate values are in `contracts/garage/phases.yaml`.

## What a Product Agent OS is

Any product repository made ready for AI delivery with two additions and one registration:

| Part | Purpose |
|---|---|
| `CLAUDE.md` at the repo root | Conventions, stack, test framework, PR standards. The build phase reads it first and follows it rather than guessing |
| `delivery/<feature-slug>/` | One folder per feature in flight: `spec.md`, `handoff.md`, `status.md`, `audit.md`, and `delta.md` for v2.0+ |
| A registered delivery root | The pipeline engine (shared, lives in the Garage project) finds the folder through its own machine-local config |

The engine is shared across all products; each Product Agent OS is only a landing zone. Existing source code is not moved.

## The handoff contract: who writes what

| File | Writer | Rule |
|---|---|---|
| `spec.md` | PM only | Hash recorded at the 03 gate and checked at every phase boundary; any edit after the gate halts the pipeline |
| `handoff.md` | PM only | Pipeline control fields (product, feature type, mode, compliance tier, owner, build mode, target). The pipeline reads, never writes |
| `status.md` | Pipeline only | Current phase, gate log, blockers, Notion sync state. The PM reads it to approve, never writes it |
| `audit.md` | Phase agents | Each phase appends one entry (skills, MCPs, tools used) **before** it returns |

Schemas in `contracts/garage/schemas/` are authoritative. Where the Garage's own guides show different field values, the schema wins (the Garage says so itself).

## How work moves and where it stops

- Each gate is a named person's approval, recorded with who approved and when. QA sign-off is always a person, in every mode.
- **Gated** mode stops at every gate. **Autonomous** mode runs on "pass" and stops on blocked or Major+ findings. Standard compliance tier defaults to gated.
- Retries are capped at 3 per phase; at the cap the pipeline stops and hands the decision to the PM.
- Review findings are classed Critical, Major or Minor. Critical blocks; Major needs the PM to know; Minor is advisory.
- The compliance tier is re-reviewed on every run (`tier-reviewed-date` must be current).

## Naming

- Feature slugs are kebab-case and equal the delivery folder name. The Notion page is found by this slug.
- Branches for delivery work are `delivery/<feature-slug>`, built in a separate worktree, merged with `--no-ff`.
- Spec versions are semver strings (`"1.0"`); v2.0+ builds can be deltas against an approved `delta.md`.

## Tracking

Notion is the Garage's tracking layer, never its control plane: `status.md` is the truth. Sync is fire-and-forget; failures are written down with a full field snapshot and replayed by an hourly reconciler with backoff. Notion fields are in `contracts/garage/notion-delivery-pipeline.md`.

## What this repo takes from these conventions

| Garage convention | How this repo applies it |
|---|---|
| One authoritative contract file, updated first | `contracts/garage/` is copied, never edited by hand; `docs/DECISIONS.md` records any difference |
| Writers are fixed per file | The repo writer is the only writer of the company repo; agents only propose |
| Every phase leaves an audit entry before returning | Every block ends with a `BUILD_LOG.md` entry; every privileged action writes `audit_log` |
| Gates are people, recorded by name | Review desk decides; core committee can veto; reviewer codes recorded on every decision |
| Failure snapshots and replay | Outbox rows are replayable and idempotent on event ID; `scan.async` retries on a fixed schedule |
| No product-specific values hard-coded in shared logic | Thresholds, routes and wording live in the company repo's `rules/` and `comms/` |
| The platform only **reads** Garage state | `garage.sync` reads Notion; the platform never writes `handoff.md`, `status.md` or Garage phases |
