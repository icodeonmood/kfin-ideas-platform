---
id: C-LISTEN
title: Listen to the whole idea (player)
rev: 1
status: baseline
source: reference/css/boards/DeskIdea.css
depends_on: [F-MOTION]
last_delta: none
---

# C-LISTEN: Listen to the whole idea (player)

For a reviewer on the move: the idea read aloud, part by part.

## `C-LISTEN.anatomy` Anatomy

A glass strip at the top of the reviewer's idea: the title "Listen to the whole idea", the time "0:00 / 2:10", and at the right a parts menu button, a "Save for offline" button and a round ink play button. Under them one continuous line with a blue bead as the playhead and small ticks where each part starts.

## `C-LISTEN.behaviour` Behaviour

1. Six parts, in the idea's order: The problem, How often, Who it affects, What it's worth, Attached, Fix. The line carries no labels; the menu names the parts with their start times and jumps to one.
2. Play / Pause. While playing: a small equaliser beside the time, the current part named ("Now: How often"), and a speed button under the play button cycling 1×, 1.25×, 1.5×, 2×.
3. Dragging the bead or clicking the line seeks. The played length fills blue.
4. "Save for offline" keeps the audio on the device; the button then reads "Saved for offline".
5. At the end the playhead returns to 0:00 and stops.
6. `NOT DRAWN:` the audio reads the summary and facts as the reviewer sees them, including answers once given; hidden details are spoken as "hidden". The sharer's raw words are not read.
7. Play has an accessible label with the full length ("Play the whole idea, 2 minutes 10 seconds"); the line exposes "Played 0:42 of 2:10"; the menu is a list of buttons ("Jump to How often, 0:38").

Back end: `L-LISTEN`.

## `C-LISTEN.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/DeskIdea.css` (classes: `.listen`)
- Resolved values as painted: `reference/computed/components.md`, section `C-LISTEN` (player, play)
- Used on: `S-R2`
