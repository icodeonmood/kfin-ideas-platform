---
id: C-TRACK
title: Stage track
rev: 1
status: baseline
source: reference/css/boards/Status.css
depends_on: [F-MOTION, F-COLOR]
last_delta: none
---

# C-TRACK: Stage track

## `C-TRACK.anatomy` Anatomy

The five stages in order (Shared, Checked and matched, Reviewed, Built, Shipped) as nodes on a line. Under each: one line of detail.

| Node state | Look | Screen-reader suffix |
|---|---|---|
| Done | Filled ink node with a tick; line to the next is solid | ", done" |
| Now | 24px node with a `--blue` inner ring and a soft blue halo; a "Now" tag | ", now" |
| To come | Hollow node, `--edge` outline; line dashed | ", to come" |
| Not going ahead | Hollow node, `--mute` label | ", not going ahead" |

Desktop: horizontal, full width of the content. Phone and narrow cards: vertical (`.vtrk`), nodes on the left, text right.

## `C-TRACK.detail` Detail line per stage

| Stage | Done | Now | To come |
|---|---|---|---|
| Shared | "Today, 10:05 am" (date and time shared) | | |
| Checked and matched | "Personal details hidden, 2 similar ideas found" | "Checking…" | |
| Reviewed | "Picked, Monday 16 November" (the decision and date) | "By Friday 20 November" | |
| Built | date built | "Team chosen by Friday 27 November" | "If it's picked" |
| Shipped | date shipped | | "Then we measure what changed" |

## `C-TRACK.motion` Motion

On arrival the line draws itself (1.2s) and each node pops in turn (700ms spring, 120ms apart); the current node breathes twice, then rests. With reduced motion the track appears complete.

The track is an ordered list; each item's text includes its state suffix. It is not interactive.

## `C-TRACK.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Status.css` (classes: `.trk`, `.vtrk`)
- Resolved values as painted: `reference/computed/components.md`, section `C-TRACK` (track, node now)
- Used on: `S-01`, `S-06`, `S-09`
