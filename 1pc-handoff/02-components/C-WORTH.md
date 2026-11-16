---
id: C-WORTH
title: What it's worth: view and edit
rev: 1
status: baseline
source: reference/css/boards/DeskIdea.css
depends_on: [C-FIELD, C-CHIP]
last_delta: none
---

# C-WORTH: What it's worth: view and edit

The size of an idea's benefit, in four measures, any mix.

## `C-WORTH.view` View

Chips for kind and area ("A problem to fix", "Investor service"), then four tiles:

| Measure | Example | Empty |
|---|---|---|
| Time saved | "70 to 150 hours a month" | "Not given" |
| Cost saved | "about ₹25,000 a month" | "Not given" |
| Revenue | "… a month" | "Not given" |
| Outside tools | "No change" / "Partly less reliance" / "Fully less reliance" | "No change" |

On the sharer's side (Check it step "Sorting", Edit) the same idea is captured as "What it would bring" (pick all that apply): Saves time, Saves cost, Earns revenue, Cuts reliance on outside tools, Not sure yet; and inside the fix sheet as a rough size (a range is fine).

## `C-WORTH.edit` Reviewer's revision (`S-R2`)

"Revise and recategorise" opens the editor in place: three fields (hours a month, cost a month, revenue a month), "Outside tools" (None, Partly, Fully), "What kind it is" (A problem to fix, A new business idea), "Area" (Investor service, Operations, Distributor experience, Corporate registry, Technology), and an optional note ("For example, the 40 calls are across three branches, so I scaled it up"). Actions: "Cancel" (text) and "Save" at the bottom right. The line beside them: "Kavya sees what you changed, with your note."

After saving, a changed tile is marked and shows the original: "was 70 to 150 hours a month". The sharer sees both figures side by side on their Status page.

Rules: `L-WORTH`.

## `C-WORTH.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/DeskIdea.css` (classes: `.wv`)
