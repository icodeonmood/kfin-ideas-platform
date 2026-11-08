<!-- inherited-from: Product-Manager-Skills/config/schemas/spec.schema.yaml, Product-Manager-Skills/docs/plans/garage-whitepaper.md (§3, §4, §7) and Product-Manager-Skills/delivery/ai-product-evals/spec.md (structure only) @ b7138ec on 2026-11-08; do not edit by hand, re-run the inheritance step -->

# PM conventions (summary)

What the Garage expects a feature brief and a spec to contain, in our words. `brief-writer` (week 6) and the handover pack (ARCHITECTURE §4.8) follow this. The machine contract itself is `contracts/garage/schemas/spec.schema.yaml`.

## The feature brief (phase 01-discover output)

The Garage's discovery phase produces a **feature brief with four parts: problem, user, opportunity, constraints**. This is exactly the brief ARCHITECTURE §4.8 asks `brief-writer` to draft from a cluster, so §4.8 needs no change. The Garage has **no separate brief template file**; discovery skills (problem framing, proto-persona, jobs to be done) shape the content.

## The spec (phase 02-shape and 03-gate output)

`spec.md` is Markdown with YAML frontmatter. Frontmatter: `version` (semver string), `prior-version` (blank for 1.0), `status: s3-gated` once gated, `gated-date`, `spec-hash` (SHA-256 of the body).

Body sections, all required, in this order:

| Section | Rule |
|---|---|
| Changelog | Only for version 2.0 and later. Table: Section, Change type (Added, Modified, Removed), Summary |
| Problem statement | One clear paragraph: root cause and user impact. No solution language |
| User | Persona and job to be done |
| Opportunity | Why now: the market or platform condition that makes it worth building |
| Scope | Table with In and Out columns. Explicit out-of-scope prevents creep |
| User stories and acceptance criteria | Table: Story, Criterion, Blocking, Test input, Expected output or fixture path |
| Architecture notes | Key decisions, dependencies, integration points. Not a full design |
| Edge cases | Named failure modes with expected behaviour |
| Success metrics | Measurable outcomes, leading and lagging |
| Open questions | Table: Question, Owner, Deadline, Blocking. Must exist even if empty. Any `Blocking: true` row stops the pipeline |

## Writing rules we carry over

- **Problem before solution.** The problem statement never names the fix.
- **Every criterion is testable**: give the input and the expected output. Mark which criteria block.
- **Scope is two-sided.** Say what is out as plainly as what is in.
- **Open questions have an owner and a date**, and say whether they block.
- **Shaping skills add to an existing spec; they do not overwrite it.** (Same principle as our canvas: the assistant fills gaps, never replaces the person's answer.)
- **Specs are locked by hash at the gate.** A changed spec needs a new gate.
- **Write for a reader who has no context**: short sentences, active voice, define terms, no filler.

## How the handover pack maps to it (for week 6)

| Spec section | Comes from (ARCHITECTURE) |
|---|---|
| Problem statement | Cluster combined problem statement (§4.4) |
| User | Canvas "who it touches" across members; roles affected |
| Opportunity | Impact estimate (§4.5) and contributors' "why KFintech" |
| Scope | Draft by `brief-writer`; the Garage PM owns the final version |
| Acceptance criteria, architecture notes, edge cases | Written by the Garage PM in phases 02–03, not by this platform |
| Success metrics | Handover success metric: baseline, target, how measured (§4.8) |
| Open questions | Cluster open questions (§4.4) |

The platform drafts the **brief**; the Garage PM writes `spec.md` and `handoff.md` (PM-only files). The platform never writes into the Garage's `delivery/` folder.

Not copied: the PM skills library's generic PRD template (`skills/prd-development/template.md`, 659 lines). It is a general-purpose PRD template, not the Garage brief, and the inheritance rules forbid copying extra material "just in case".
