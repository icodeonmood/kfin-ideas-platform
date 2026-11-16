---
id: P-DECISIONS
title: Decisions taken, promises awaiting sign-off, open questions
rev: 1
status: baseline
source: reference/prototype/Handoff.dc.html
depends_on: []
last_delta: none
---

# Decisions, sign-offs and open questions

## `P-DECISIONS.taken` Decisions that shape the build

| # | Decision | Effect on the build |
|---|---|---|
| 1 | The product is problem-first. A fix is optional. | The main action is "Share a problem". Nothing about the fix blocks sending. |
| 2 | The assistant pre-fills the sorting; the sharer confirms or changes it (13 Nov 2026; supersedes DEC-004 and DEC-094 in the repo's decision log). | Sorting needs one explicit confirmation before sending. A changed value counts as confirmed. `L-SORT`. |
| 3 | The review desk decides on the committee's behalf; the committee can view everything and reverse within its window. | The sharer hears the desk's decision at once. `L-DECIDE`, `L-COMMITTEE`. |
| 4 | No appeals, no "demand route", no "sponsor route". | No appeal UI or API. The decision and its reason are shown instead. |
| 5 | Customer personal details are hidden automatically, in the person's draft and in everything shared; their own text box keeps their words unchanged. | `L-HIDE`. "Show it" needs a reason and is logged. |
| 6 | Similar ideas are offered before sending. | `L-SIMILAR`; decided on Check it. |
| 7 | Merging is a request to the other idea's lead. If the lead declines, the sharer sends theirs on its own. | `L-MERGE`. |
| 8 | The review desk can merge ideas and team the sharers up without a request. The committee can reverse it for 30 days. | `L-MERGE.desk`. |
| 9 | One list of what waits on you: the Inbox. "Needs you" is its tab. | No separate notifications or conversations list. `L-INBOX`. |
| 10 | Questions from the desk are answered only on the Answer screen. | Everywhere else they show as a card with an "Answer the questions" button, never a free-text box. |
| 11 | One conversation per idea. | `S-08`. No global chat. |
| 12 | No snackbars or toasts, and no Undo messages. The screen itself shows what changed; field errors and warnings sit under their field. | `C-FIELD-MSG`. The `.snack` rules in the prototype kit are dead code. |
| 13 | The team-up sheet, the merge sheet and the preview pop-up have one button; the cross closes them. No "Cancel". | `F-SPACE.cta/3`. Inline editors and the fix sheet still show "Cancel" as drawn; see open question 13. |
| 14 | Forward actions sit at the end of the flow, bottom right; never top, never left. | `F-SPACE.cta`. |
| 15 | Warm colour means "needs you"; avatar rings are neutral except where the tier is the subject. | `F-COLOR.principles/4`, `F-COLOR.tiers`. |
| 16 | The reviewer's main path is to decide. Asking the sharer first is optional and folded away. | `S-R2.panel`. |
| 17 | The Wall shows a short summary to everyone; the person's own words stay with them and the review desk. The sharer can hide their name on the Wall. | `P-PRODUCT.privacy`, `S-H6`. |
| 18 | Phone is the same responsive web app. A native app is "coming soon". | `F-SPACE.breakpoints`. |
| 19 | Three choices stay switchable for A/B testing: S1 how the draft is built, S2 when similar ideas are decided, S3 whether the phone starts with typing or voice. | Build the default; keep the alternative behind a feature flag. See `P-DECISIONS.experiments`. |

## `P-DECISIONS.experiments` Simulators (feature flags)

| Flag | Screen | Default (build first) | Alternative (behind the flag) | Decided by |
|---|---|---|---|---|
| S1 | `S-04`, `S-04B` | Live draft beside the text | Interview: after the first telling, up to three short skippable questions (how often, who feels it most, any rough size), then the draft | Draft completeness against time to submit and drop-off |
| S2 | `S-05` | Quiet nudge: similar ideas are one part of Check it | Check first: on a strong match, the comparison comes before the rest of Check it | Duplicates reaching the review desk against completion rate |
| S3 | `S-04` on phone | Type first, with a large mic | Voice first: listening starts at once, "Type instead" in the dock | Phone completion and how often people correct the transcript |

Every flag must log exposure and the deciding metrics.

## `P-DECISIONS.signoff` Promises that need sign-off before launch

| # | Promise shown in the product | Owner |
|---|---|---|
| 1 | Drafts are kept for 30 days, then archived, never deleted silently. | Product |
| 2 | The review desk decides within 5 working days and usually replies within a working day. | Review desk lead |
| 3 | A withdrawn idea can be restored at any time. | Product |
| 4 | Idea ownership wording: KFintech owns what employees share; the sharer keeps the credit. Not shown in the flow today; the declaration at Submit covers personal data and own work. | Legal |
| 5 | The 1% Club email address, the Teams app, the IT service desk extension and the sign-in address (placeholders on the boards). | IT |
| 6 | The native app's launch date ("Coming soon"). | Product |
| 7 | The Ones Committee's window: 30 days, extendable 30 days at a time up to 3 months. Confirmed 15 Nov 2026. | Product |
| 8 | Animation library licence (`F-MOTION.build/2`). | Legal |
| 9 | Notifications reach people on Teams and by email. | IT |

## `P-DECISIONS.open` Open questions

Build the stated default; do not block on these.

| # | Question | Default to build | Raised in |
|---|---|---|---|
| 1 | Layout between 641px and 1100px wide is not drawn. | `F-SPACE.breakpoints` | `F-SPACE` |
| 2 | Tier 6 "Blue flame" has a violet ring and tier 7 "Star" a blue one. Intended? | As drawn | `F-COLOR.tiers` |
| 3 | Do the review desk and committee need designed phone layouts? | Responsive stacking only | `P-ROUTES` |
| 4 | Who reviews an idea shared by a reviewer? | Any other reviewer; never the sharer | `P-PRODUCT.roles` |
| 5 | What "Popular" means on the Wall's Just in list. | Colleagues who opened the idea in the last 7 days | `S-WALL.justin` |
| 6 | What "Ones" means as a sort on Just in. | Number of Ones on the idea's crew | `S-WALL.justin` |
| 7 | Should the Ones Committee be able to start a merge, not only reverse one? | No; desk only | `L-MERGE` |
| 8 | Pack-of-cards transition on the phone crew screen. | Phone keeps its full-screen swipe | `C-CREW-DECK` |
| 9 | How tiers are earned and what points are awarded for. The boards show the outcome, not the formula. | Configurable table; see `L-ONES.open` | `L-ONES` |
| 10 | Which languages voice and text input support at launch. The boards say "any language" and show Telugu typed up in English. | English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi | `L-DRAFT` |
| 12 | File size limit and allowed types differ: 15 MB and a wide type list in the prompt box; 25 MB and "screenshots, photos, PDFs or spreadsheets" on Check it and Edit. | One configurable limit (start at 25 MB) and one type list (the wider one); help text rendered from configuration | `C-FILE.uploader` |
| 13 | Should the fix sheet, the Edit page and inline editors also drop "Cancel", like the team-up and merge sheets? | Keep "Cancel" where drawn | `S-05.fix` |
| 14 | The phone boards for Tell it and Check it use an earlier structure than the desktop boards (a single text field; one long page). Some phone copy differs. | Desktop rules and copy win; phone keeps its drawn layout. Each screen's `phone` section says how | `S-04.phone`, `S-05.phone` |
| 15 | The older design record mentions a 50-character minimum; the boards use 30. | 30 | `L-DRAFT.parts/3` |
| 11 | Retention of raw words, voice clips and unmasked details. | Raw words kept with the idea; voice audio deleted after transcription; unmasked details never stored outside the sharer's own draft | `L-HIDE` |
