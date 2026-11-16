---
id: S-LAUNCH
title: Launch screen (inauguration)
rev: 1
status: baseline
source: reference/prototype/Launch.dc.html
depends_on: [L-DISPLAY]
last_delta: none
---

# S-LAUNCH: Launch screen (inauguration)

**Route (proposed):** `/display/launch`. **Boards:** `Launch`

1. `S-LAUNCH/1` 1920×1080. Sequence and timing: `L-DISPLAY.launch`.
2. `S-LAUNCH/2` Frame "Before Start (operator)": "1% CLUB · INAUGURATION, FRIDAY 20 NOVEMBER", "Launch screen", instructions ("For the lamp lighting on Friday 20 November. Put this page on the big screen, choose Full screen, then press Start the moment the lamp is lit." "It runs for about thirty seconds, with a bell and a spark sound at the start, and then stays on the invitation and its QR code."), buttons "Start" and "Full screen", and the timeline of the six beats.
3. `S-LAUNCH/3` Frame "Reveal": plays 0:00 to 0:30.
4. `S-LAUNCH/4` Frame "Final frame (invitation)": the mark, "1% spark. 99% sweat.", "You bring the spark.", "Scan the code to share your idea.", the QR code and the address under it.
5. `S-LAUNCH/5` Same style exemption as `S-OFFICE/4`. Values from `reference/css/boards/Launch.css`.
6. `S-LAUNCH/6` Escape leaves full screen but does not stop the sequence; reloading returns to the operator frame.

## `S-LAUNCH.reference` Reference (generated)

### Board `Launch` (1920×1080)

- Canvas caption: Launch screen (unchanged)
- Prototype: `reference/prototype/Launch.dc.html`
- Exact copy and controls in every state: `reference/copy/Launch.md`
- Board-specific CSS: `reference/css/boards/Launch.css`
- Default screenshot: `reference/shots/Launch.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `frame` | Before Start (operator); Reveal (plays the 30 seconds); Final frame (invitation) | `Launch__frame-*.jpg` (2) |
