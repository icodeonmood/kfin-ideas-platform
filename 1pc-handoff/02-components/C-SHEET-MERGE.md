---
id: C-SHEET-MERGE
title: Merge sheet (review desk)
rev: 1
status: baseline
source: reference/css/boards/DeskIdea.css
depends_on: [C-FIELD, C-BUTTON, C-FIELD-MSG]
last_delta: none
---

# C-SHEET-MERGE: Merge sheet (review desk)

The review desk merges two similar ideas and can team the sharers up without a request.

## `C-SHEET-MERGE.anatomy` Anatomy

Centred sheet, 560px, radius 28px, solid white, over a 32% ink scrim with a light blur. A close cross at the top right ("Close without merging").

1. Title: "Merge with IDEA-2026-001412?"
2. Line, following the choice below: "Kavya's idea joins Ravi's. Both stay credited, and from now on the review desk decides on one idea."
3. **"Which idea leads"** (single choice, two option rows; the selected row has a 1.5px `--blue` ring and `--wash` fill):
   - "{lead}'s leads, IDEA-…" with "Shared 2 November, 4 on its crew". Selected by default when it was shared first or has the larger crew.
   - "{sharer}'s leads, IDEA-…" with "Shared Saturday, just Kavya so far".
4. **"Team them up"** (a tick box row, ticked by default): "Kavya joins Ravi's crew without a request. Both are told why."
5. **"Note to both sharers"**: text area, 3 rows, pre-filled ("You both found the same R07 calls in Hyderabad. One team, one fix, with both your names on it."). Under 20 characters on send: error "Tell both why, in a line or two."
6. Small print: "Both get it in their Inbox. The Ones Committee sees the merge for 30 days and can reverse it."
7. **One button**, bottom right: "Merge and tell both".

## `C-SHEET-MERGE.after` After merging

The "Similar ideas" card shows a green banner in place: "Merged: Kavya's idea is now part of IDEA-2026-001412, and both are credited. Kavya is on Ravi's crew. Both were told in their Inbox. The Ones Committee can reverse it within 30 days." The merged row shows a "Merged" pill instead of the Merge button.

Opens from "Merge" on a similar-idea row or from the preview's footer button. Dialog rules as `C-PREVIEW.behaviour/2`. Rules: `L-MERGE.desk`.

## `C-SHEET-MERGE.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/DeskIdea.css` (classes: `.mgsheet`)
- Resolved values as painted: `reference/computed/components.md`, section `C-SHEET-MERGE` (sheet, option, scrim)
- Used on: `S-R2`
