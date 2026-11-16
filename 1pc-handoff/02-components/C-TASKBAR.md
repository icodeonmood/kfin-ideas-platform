---
id: C-TASKBAR
title: Task bar: steps, save status, Save and close
rev: 1
status: baseline
source: reference/css/boards/Review.css
depends_on: [F-COLOR, F-MOTION]
last_delta: none
---

# C-TASKBAR: Task bar: steps, save status, Save and close

## `C-TASKBAR.anatomy` Anatomy

A sticky bar across the top of the content area on task screens: 64px tall, `rgba(246,246,244,.55)` with blur, 1px bottom border. Left to right: the task title ("Share a problem", 500 17px display), the three steps, then at the right the save status and "Save and close" (line button → Home).

## `C-TASKBAR.steps` Steps

"Tell it", "Check it", "Send it". Two looks are drawn:

- On Tell it (`S-04`, `S-04B`): three labelled bars side by side; the current step's bar is ink, the others grey.
- On Check it (`S-05`): three nodes joined by short lines: a ticked ring for a done step, a filled ink disc with the number for the current step, a hollow numbered ring for a step to come.

`OPEN:` the two screens show the same three steps in two styles. Default: build both as drawn; the product owner to choose one.

| Step state | Reads as |
|---|---|
| Done | "Tell it, done" |
| Current | "Check it" with `aria-current="step"` |
| To come | "3 Send it" |

A done step is a link back to it. On `S-04` the steps and the draft panel appear only after the first message (`S-04.empty`).

## `C-TASKBAR.save` Save status

A small sync icon plus words, in a polite live region:

| State | Words | Icon |
|---|---|---|
| Not yet typed | "Saves as you type" | grey |
| Saving | "Saving…" | blue, pulsing |
| Saved | "Saved at 1:38 pm" | green |
| Offline | "Unsaved, you're offline" | amber, with a warning note under the bar |
| Edit mode, changed | "Unsaved changes" | amber |

Rules: `L-DRAFT.autosave`.

## `C-TASKBAR.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Review.css` (classes: `.tbar`, `.saved`)
- Resolved values as painted: `reference/computed/components.md`, section `C-TASKBAR` (bar, save status)
- Used on: `S-04`, `S-04B`, `S-05`, `S-06B`
