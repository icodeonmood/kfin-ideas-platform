# Seed content

`company-repo/` becomes the company repo (`kfin-ideas`) the first time `make seed` runs. After that, the company repo is the source of truth and this folder is only used for fresh environments (dev, UAT, tests).

Every file here is a **draft** (`verified: unverified`). The product team signs it off by **Monday 16 November** (§9.1). Sign-off means: check the content, then set `verified: human:<staff code>` and `status: stable`.

## Sign-off checklist

| Item | Where | Who | What to check |
|---|---|---|---|
| Categories and plays | `taxonomy/value/` | Product | Wording matches the canvas |
| Area tags (8) | `taxonomy/areas/` | Product | Enough to route; not too many |
| LOBs and functions, with HR department names | `taxonomy/lobs/` | HR, Product | Names match the HR directory exactly (`kfin.hr_departments`); committee per LOB |
| Role families, with job-title patterns | `taxonomy/roles/` | HR | Patterns catch the real titles; order (specific first) |
| Glossary (52 terms) | `taxonomy/glossary/` | Product | Confirm KFinKart (marked "to be confirmed"); add missing KFin system names and aliases |
| Rules | `rules/` | Product; core committee for scorecard and priority | Numbers in `routing.md` (shortlist 65, nomination 70) and `scorecard.md` anchors |
| Calendar | `rules/calendar.md` | HR | Replace assumed holidays with KFin's official 2026–27 list (O10) |
| Redirect links | `rules/redirects.md` | IT, HR, Admin | Real URLs for the IT helpdesk, HR portal, admin and intranet help |
| Compliance tiers | `rules/compliance-tier.md` | Product | Replaced from the Garage project during inheritance |
| Message templates | `comms/templates/` | HR | Tone and wording; set `hr_signed_off: true` |
| Canvas examples | `guidance/canvas/` | Product | Realistic, fully anonymised |
| Client organisations | `taxonomy/clients/` | Product, Sales | Every client name and common alias, so the gateway tags them; mark joint ventures and shared platforms `partner_sensitive` |
| Solutions catalogue | `company-repo/solutions/` | Product | Add Garage items shipped plus 10–20 known fixes, using `templates/solution.md` |

Never put real investor, client or employee data in any seed file.
