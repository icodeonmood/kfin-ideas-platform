---
id: C-PREVIEW
title: Preview pop-up for an idea
rev: 1
status: baseline
source: reference/css/preview-popup.css
depends_on: [C-PILL, C-AVATAR, C-BUTTON, F-MOTION]
last_delta: none
---

# C-PREVIEW: Preview pop-up for an idea

A quick look at someone else's idea without leaving the screen.

## `C-PREVIEW.anatomy` Anatomy

Centred pop-up, 560px wide (full width less 28px on phone, rising from the bottom), radius 28px, glass (`F-COLOR.glass`), over a frosted backdrop. Max height: window less 48px; scrolls inside, no visible scrollbar.

1. **Band** (radius 20px, 10px inset from the pop-up edge, gradient hue 1 or hue 2 from `F-COLOR.gradients`, white text): status pill and the reference on one row; the title (500 28px / 1.12); a meta line (area, city, and on the review side when it was shared).
2. **Close**: a 40px round button at the top right of the band, white 22% fill, label "Close the preview".
3. **Why it matches**: one blue-wash line with a spark icon: "Close match: the same R07 SMS and the same calls".
4. **Sections** (white 82% tiles, radius 20px): "The problem, in their words" (500 18px); then, by context:
   - sharer's view (`S-05`, `S-06`): "They're looking for";
   - reviewer's view (`S-R2`): "Next to Kavya's", a three-row comparison (How often, Who it affects, What it's worth) with one column per idea.
5. **Crew**: faces + "Ravi Nair leads it, 4 on its crew".
6. Sharer's view only: a note, "Teaming up adds you to their crew. Your draft stays yours."
7. **Footer**: "Open the full idea" (text, left) and exactly one button (right): "Team up" for a sharer, "Merge" for a reviewer. After the action it is replaced by a green status ("Waiting for Ravi", "Merged").

## `C-PREVIEW.behaviour` Behaviour

1. Opens from "Preview" or from the idea's title. Arrives on the spring; the backdrop fades.
2. Focus moves into the pop-up; Escape, the cross and a click on the backdrop close it; focus returns to the opener.
3. The footer button closes the preview and opens the next step (`C-SHEET-TEAMUP` or `C-SHEET-MERGE`) for the same idea.
4. Mounted at the page root, not inside a glass panel (`F-COLOR.glass/3`).

Data: `A-API.idea-preview`.

## `C-PREVIEW.reference` Reference (generated)

- Source rules in the prototype: `reference/css/preview-popup.css` (classes: `.pvwrap`, `.pvm`)
- Used on: `S-04`, `S-04B`, `S-05`, `S-06`, `S-R2`
