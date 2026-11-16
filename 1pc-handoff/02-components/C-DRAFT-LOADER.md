---
id: C-DRAFT-LOADER
title: Draft loader (six services, one bar)
rev: 1
status: baseline
source: reference/css/draft-loader.css
depends_on: [C-SKELETON, F-MOTION]
last_delta: none
---

# C-DRAFT-LOADER: Draft loader (six services, one bar)

Building a draft takes a few seconds and is done by six independent services. The loader shows that as one bar that never stops moving forward, while each part of the draft shows its own skeleton.

## `C-DRAFT-LOADER.anatomy` Anatomy

A glass strip at the top of the draft panel (radius 20px, blue-tinted, max-height 96px):

1. Top line: "Building your draft" (500 14px) on the left; on the right a count and estimate in tabular figures: "2 of 6 ready, about 2 seconds left".
2. A tube: 10px tall, fully rounded, inset shadow. The fill is a blue gradient (`#7088FF` → `#395DED` → `#2B4BCD`) with a glow, a light that sweeps along it every 1.25s, and a 16px glass bead at its head.
3. Phone: only the tube (8px, 14px bead), under the sheet's peek.

## `C-DRAFT-LOADER.maths` How the bar moves

The six parts and their mean response times (p50 over the last 7 days, read from monitoring; prototype values shown):

| Part | Mean | Weight (share of summed means) |
|---|---|---|
| Similar ideas | 2.6s | 30% |
| Title and summary | 1.8s | 21% |
| What it's worth | 1.5s | 17% |
| Who it affects | 1.2s | 14% |
| How often | 0.9s | 10% |
| Area | 0.7s | 8% |

1. All six are called together the moment the words arrive.
2. While a part is pending, its progress is `0.9 × (1 − e^(−t ÷ mean))`: always rising, never full on its own.
3. When a part answers, it counts as 1 and its value fades into its slot.
4. Bar = sum of `weight × progress`. So it never pauses and never moves back. It is capped at 97% until all six are in.
5. Estimate = the largest `mean − t` among pending parts: "about N seconds left"; under a second: "almost there".
6. A part past 1.5 × its mean replaces the estimate with its own line: "still looking for similar ideas", "the title is taking longer", and so on.
7. When all six are in: the bar fills, the bead pops once (500ms), the line reads "All 6 parts are in", and after a short hold the strip folds away (380ms). The header changes to "Up to date".
8. "Move to Review" waits for all six.
9. The loader runs again, the same way, each time the person adds to their words; only parts being rebuilt show skeletons.

## `C-DRAFT-LOADER.failure` When a part fails or stalls

`NOT DRAWN:` the canvas shows a slow part but not a failed one. Defaults:

1. A part that errors or exceeds 10 × its mean stops counting as pending: its slot shows "Couldn't work this out. Add it yourself." with a "Change" button, and the bar treats it as answered.
2. If similar ideas fails, the draft is still ready; Check it shows the similar-ideas part as "Couldn't check for similar ideas. The review desk will." (`L-SIMILAR.failure`).
3. Nothing here ever blocks typing.

## `C-DRAFT-LOADER.a11y` Accessibility

`role="progressbar"` with `aria-valuenow` updated at most once a second and `aria-valuetext` equal to the visible line. With reduced motion: no sweep, no bead pulse; the fill still grows.

Contract: `A-API.draft-stream`. Back end: `L-DRAFT.parts`.

## `C-DRAFT-LOADER.reference` Reference (generated)

- Source rules in the prototype: `reference/css/draft-loader.css` (classes: `.dload`)
- Resolved values as painted: `reference/computed/components.md`, section `C-DRAFT-LOADER` (box, track)
- Used on: `S-04`, `S-04B`
