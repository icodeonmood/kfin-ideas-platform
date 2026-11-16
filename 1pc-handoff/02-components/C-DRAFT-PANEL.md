---
id: C-DRAFT-PANEL
title: The draft, as a live document
rev: 1
status: baseline
source: reference/css/boards/Compose.css
depends_on: [C-DRAFT-LOADER, C-HIDDEN, C-CHIP, C-SKELETON]
last_delta: none
---

# C-DRAFT-PANEL: The draft, as a live document

The right-hand panel on Tell it (a peek sheet on phone): the draft the assistant builds from the person's words, part by part.

## `C-DRAFT-PANEL.anatomy` Anatomy

A tall glass card filling the right column. Header: "Your draft" on the left and a status on the right ("Forms as you write" → "Updating" → "Up to date"). Under it the loader strip while parts are building. Then, in fixed slots so nothing jumps: the title and summary as text; the four facts as a 2×2 grid of tiles (How often, Who it affects, What it's worth, Area), each with its label, value, why line and "Change" at its top right; the hidden-details bar; the similar-ideas line.

| Part | Shows | "Why" line under it |
|---|---|---|
| Title | A one-line title | "From your first sentence." |
| Summary | 2 to 3 sentences in plain words | none |
| How often | For example "About 40 calls a day at one branch" | "From your words: "about 40 calls a day"" |
| Who it affects | One or more groups | "Suggested because you mentioned investors and the branch." |
| What it's worth | One or more of: Saves time, Saves cost, Earns revenue, Cuts reliance on outside tools | "From your words: …" |
| Area | One area | "Suggested because it's about investors and the SMS they get." |
| Hidden details | `C-HIDDEN` | |
| Similar ideas | A quiet line: "2 similar ideas", "Colleagues raised something close…", opened on demand | |

Footer, pinned to the bottom of the card: "Move to Review" as a full-width button (56px), with a readiness line. Before the draft is ready: "Your draft needs a little more first." (button disabled). Ready: "Looks right? Check the sorting and send it."

## `C-DRAFT-PANEL.states` Part states

| State | Look |
|---|---|
| Waiting | Label + "Waiting for your words" in `--mute` |
| Updating | Skeleton in the slot; the header says "Updating" |
| Filled | Value + why line + a "Change" text button (label for screen readers: "Change the title", "Change How often") |
| Changed by the person | Value + "Your call" in place of the why line. The assistant never rewrites a part the person changed |
| Editing | The slot opens in place: a field or chip set, "Other" opens a free field, and "Done" bottom right with a green tick |

## `C-DRAFT-PANEL.behaviour` Behaviour

1. Only parts whose value changed update, each into its own slot. The panel never reflows as a whole.
2. Each update is announced once, politely.
3. Focusing a filled part underlines, in the person's own text, the phrase it came from.
4. "Change" on a part and a later message from the person can both alter the draft; the person's direct change wins (`L-DRAFT.pins`).
5. In the conversation, the assistant posts a short receipt of what it did after each message: "Drafted a title: "…"." "Sorted it under Investor service, affecting investors and KFin teams." "Noted how often: about 40 calls a day at one branch." "Marked it as saves time and saves cost." "Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10." Then one line: "Your draft is ready. Add a detail, or check it." and up to two suggestion buttons ("Add what you already tried", "Change the title").
6. Phone: the panel is a bottom sheet that peeks with the title and the loader, and opens fully on tap or drag.

## `C-DRAFT-PANEL.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Compose.css` (classes: `.dpanel`, `.drow`)
