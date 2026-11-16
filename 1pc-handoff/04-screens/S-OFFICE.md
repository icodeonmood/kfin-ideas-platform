---
id: S-OFFICE
title: Office screen (wall display)
rev: 1
status: baseline
source: reference/prototype/Office.dc.html
depends_on: [L-DISPLAY, L-ONES]
last_delta: none
---

# S-OFFICE: Office screen (wall display)

**Route (proposed):** `/display/office`. **Boards:** `Office`

1. `S-OFFICE/1` 1920×1080, no chrome, no interaction. Content and rotation: `L-DISPLAY.office`.
2. `S-OFFICE/2` Left: a field of lights, one per One, labelled "No. 1 · Rohit"; the current One's is brightest. Right: "1% CLUB · KFINTECH", "The Ones", "7 Ones so far. Each one shipped something that changed how we work.", then the current One: "TIER 4 · BLAZE", "Number 1" (the digits roll like a counter), name, "Founding One", the brief with its headline figure, and "1 of 7". Footer: "1% spark. 99% sweat."
3. `S-OFFICE/3` Tweaks: `stars` (One's own spark, the default; Glowing dots) and `secondsPerOne`.
4. `S-OFFICE/4` This screen keeps its earlier visual style (caps lines, middle dots, its own brighter palette). It is exempt from `F-TYPE.rules/1` and `/3` and from the conditioned palette. Take all values from `reference/css/boards/Office.css`.
5. `S-OFFICE/5` With reduced motion the rotation still advances; the roll and the light changes cut.

## `S-OFFICE.reference` Reference (generated)

### Board `Office` (1920×1080)

- Canvas caption: Office screen (content aligned)
- Prototype: `reference/prototype/Office.dc.html`
- Exact copy and controls in every state: `reference/copy/Office.md`
- Board-specific CSS: `reference/css/boards/Office.css`
- Default screenshot: `reference/shots/Office.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `stars` | One's own spark (current design); Glowing dots | `Office__stars-*.jpg` (1) |
| `secondsPerOne` | int (default 8) | |
