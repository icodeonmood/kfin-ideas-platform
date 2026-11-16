---
id: C-SKELETON
title: Loading skeletons and spinner
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR, F-MOTION]
last_delta: none
---

# C-SKELETON: Loading skeletons and spinner

1. `C-SKELETON/1` A part that is loading shows a skeleton in the exact place and size its content will take: radius 8px bars, `#E9E9E6` to `#F1F1EE` shimmer moving left over 1.4s. Inside the draft loader the shimmer is tinted blue (`#E6EBFF`).
2. `C-SKELETON/2` Lists show 3 skeleton rows. Cards show their own outline with bars inside.
3. `C-SKELETON/3` When content arrives it fades in over 440ms from 4px below with a 3px blur; the layout does not shift.
4. `C-SKELETON/4` Spinner: 12px ring, 1.5px `--edge` with a `--blue` top, 0.8s per turn. Used only inside buttons and inline status ("Checking for personal details"), never as a page loader.
5. `C-SKELETON/5` No full-screen loaders and no blocking overlays, anywhere.
6. `C-SKELETON/6` With reduced motion the shimmer stops; the bars stay.
7. `C-SKELETON/7` The loading region has `aria-busy="true"` and a polite status that says what is loading.

## `C-SKELETON.reference` Reference (generated)

- Source rules in the prototype: `reference/css/kit.css` (classes: `.sk`, `.spin`)
- Used on: `S-04`, `S-04B`, `S-05`, `S-06B`, `S-07`, `S-08`
