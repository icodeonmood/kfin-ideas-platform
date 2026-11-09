# What to take from the Garage project

The Ideas Platform is a sub-brand under The Garage and hands accepted ideas to the Garage delivery pipeline. It must speak the Garage's language (phases, properties, compliance tiers, handoff contract) and follow its working conventions. This repo **copies what it needs** from the Garage project. It does not link to it, vendor it or depend on it at runtime.

## Ground rules

The owner's workspace folder ("the Garage" workspace) is `~/the-garage` on this Mac. If that path does not exist, ask the user where it is; do not search the home folder.


1. **Read-only.** Never write, move or delete anything under `~/the-garage`.
2. **Only the Garage programme project.** `~/the-garage` is the owner's personal workspace with many unrelated projects. Look only inside the folder that holds the Garage programme (the delivery harness: `config/schemas/`, `delivery/`, the Product Agent OS `CLAUDE.md`). Do not open other projects.
3. **Find the folder by name, not by reading.** Use a shallow search for folder names only, for example:
   ```
   find ~/the-garage -maxdepth 5 -type d \( -path '*/config/schemas' -o -name delivery \) -not -path '*/node_modules/*' -not -path '*/.git/*'
   ```
   If exactly one project contains both, use it. If there are several candidates, or none, list what you found and ask the user which folder to use.
4. **Copy only the items in the table below.** Never copy `.env` files, tokens, Notion or API secrets, personal notes, `~/CLAUDE.md`, Git history, or whole folders "just in case".
5. **Mark provenance.** Every copied or summarised file starts with:
   ```
   <!-- inherited-from: <path relative to ~/the-garage> @ <git commit short SHA or "no-git"> on <YYYY-MM-DD>; do not edit by hand, re-run the inheritance step -->
   ```
   (Use `#` comments for YAML and a `"$comment"` key for JSON.)
6. **Summarise conventions, copy contracts.** Machine contracts (schemas, property names, phase lists) are copied exactly. Working conventions (how CLAUDE.md, prompts and specs are written) are summarised in our own words in `docs/inherited/`, so no personal context travels with them.

## What to take

| # | Item | Look for (in the Garage project) | Put it here | Used by | If not found |
|---|---|---|---|---|---|
| 1 | Handoff contract | `config/schemas/*` (feature brief, handoff or pipeline-entry schemas) | `contracts/garage/schemas/` (exact copy) | Handover pack and Garage entry (§4.8, week 6); `brief-writer` | Keep §4.8 as the contract; note it in the report |
| 2 | Delivery Pipeline properties | The Notion Delivery Pipeline property names, types and allowed values, wherever they are defined (schema, config, docs) | `contracts/garage/notion-delivery-pipeline.md` (exact names and values in a table) | `garage.sync` (§4.9), handover (§4.8) | Use the names in §4.8 and §4.9 |
| 3 | Phases and gate statuses | Phase list (`01-discover` … `09-deploy`, `handed-off`, `shipped`) and gate-status values | `contracts/garage/phases.yaml` | Plain-language phase table (§4.9); status on the idea page | Use the §4.9 table |
| 4 | Compliance tiers | Standard and express tier rules | Replace `seed/company-repo/rules/compliance-tier.md` (keep its YAML shape; record the source) | Qualify gate (§4.5) and handover (§4.8) | Keep the draft in the seed |
| 5 | Product Agent OS conventions | The Garage `CLAUDE.md` and the `delivery/` folder conventions: folder layout, how work moves between phases, review gates, naming | `docs/inherited/product-agent-os.md` (summary) | How this repo's `CLAUDE.md`, agents and pull requests are organised | Note it; follow this repo's `CLAUDE.md` |
| 6 | PM skills conventions | Spec, PRD or feature-brief templates and writing rules | `docs/inherited/pm-conventions.md` (summary) plus the brief template under `contracts/garage/templates/` (exact copy) | `brief-writer` (week 6); handover pack | Use §4.8 fields |
| 7 | Claude Playbook conventions | Prompt structure, examples, eval and versioning rules | `docs/inherited/claude-playbook.md` (summary) | `agents/*` prompts, `CHANGELOG.md`, `eval/golden/` | Keep the drafts in `agents/` |
| 8 | ~~The Garage brand assets (if they exist)~~ **Superseded 9 Nov 2026:** nothing is copied. The platform carries its own brand, 1% Club (DEC-027 to DEC-052): rules in `docs/BRAND.md`, mark files in `apps/web/public/brand/`, tokens in `apps/web/src/app/globals.css` | — | — | UI header lockup "1% Club" with the Spark mark. Employees never see "Garage" (DEC-035) | — |

## After copying

1. Compare items 1–4 with `docs/ARCHITECTURE.md` §4.8 and §4.9. **For handover, phases and properties, the Garage contract wins.** Record each difference in `docs/DECISIONS.md` and, if a field name changes, update the architecture table in the same commit.
2. Write `docs/inherited/REPORT.md`:

   | # | Item | Found at | Copied to | Commit | Differences from ARCHITECTURE | Action |
   |---|---|---|---|---|---|---|

3. Show the user the report table and wait only if something blocks B1. Otherwise carry on to B1.

## Re-running

Re-run this step before week 6 (handover build) and whenever the Garage contract changes. Overwrite the copies, keep the provenance header current, and add a line to `docs/inherited/REPORT.md` with the date and what changed.
