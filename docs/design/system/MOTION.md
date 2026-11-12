# Motion

The first proposal allowed one moment per screen and banned bounce. This edition reverses that on purpose: glass and liquid only read as glass and liquid when they respond. The discipline moves from "almost nothing moves" to "nothing moves unless a person, or real progress, made it move".

## Three kinds of motion

| Kind | What starts it | Examples | Budget |
|---|---|---|---|
| **Answer** | A person's pointer or press | The flood in a button, the ring from a press, a tile lifting, the light crossing glass, a jersey tilting, beads parting | As often as the person acts. Each ends within `t-spring` of them stopping |
| **Progress** | Something real finishing | A check igniting its node, a vial filling, a file's tick drawing, a stage slash springing up, the heat in a glow-up | Once per event. Never on a timer, never looped to look busy |
| **Ambient** | Nothing: it is the room | One to four wide, soft lights drifting very slowly behind the glass; the sheen on "coming soon" | Brand surfaces only, behind content, never particles or lines, and paced by the tier's `--energy` (a full drift takes about a minute). Working screens get none |

Entrance animations on sections, cards that fade up as you scroll, and hover effects that only decorate are still out.

## Timings and curves

| Token | Value | For |
|---|---|---|
| `t-press` | 100 ms | A press going down |
| `t-state` | 200 ms | Colour and light. Also the cap for every reduced-motion fade |
| `t-reveal` | 320 ms | Light and text arriving; the pointer light fading |
| `t-spring` | 520 ms | Anything with mass settling: a press releasing, a tile lifting, the nav thumb |
| `t-scene` | 600 ms | One choreographed step: a vial filling, a node igniting, a choice filling |
| `t-glow` | 2400 ms | The glow-up heat only (DEC-084) |
| `ease-spring` | cubic-bezier(0.34, 1.56, 0.64, 1) | Overshoot and settle. For things with mass: buttons, tiles, nodes, the thumb. Never for text |
| `ease-out` | cubic-bezier(0.16, 1, 0.3, 1) | Arrivals with no mass: light, colour, text |
| `ease-move` | cubic-bezier(0.42, 0, 0.58, 1) | Cross-fades, colour heat, and every reduced-motion replacement |
| `ease-in` | cubic-bezier(0.7, 0, 0.84, 0) | Exits, at 75% of the entrance time |

In timelines the same curves are GSAP's `back.out`, `elastic.out(1, 0.4 to 0.75)`, `expo.out`, `sine.inOut` and `power3.in`. Only transform, opacity, colour, filter values and SVG attributes animate. Never width, height, top, left or margins (the one exception: a removed file row closing its gap).

## The signature moves

| Move | Where | How it goes |
|---|---|---|
| **Materialise** | Dialogs, the toast, the menu sheet, any glass arriving | Glass does not fade in. It arrives over-refracted (about 2.6 times its resting bend) and slightly small, then relaxes: the bend settles on an elastic curve over 1 s while the shape lands in 600 ms. Leaving reverses it in 240 ms |
| **Morph** | Button into confirm panel; "Menu" into the sheet | The new piece starts as the shape and place of the old one and flows out to its own (620 ms, expo out); its contents rise in 50 ms apart; its bend surges and settles |
| **Lens thumb** | Header nav, section nav | A bead under the labels and a lens over them move as one. The leading edge arrives in about 360 ms, the trailing edge follows with a spring over 660 ms; in flight it lifts 16% and bends harder, and the labels bend as it passes |
| **Lift** | Round buttons, the mic, glass buttons | A pressed lens grows 3 to 14%, brightens, and its bend jumps to about 1.9 times and settles with a spring over 1 s |
| **Illumination** | Any `data-lit` pane | A press sends one ring of light out through the glass from the point of contact (900 ms) |
| **Rim** | Every glass edge | The rim highlight turns to face the pointer wherever it is, easing a sixth of the way each frame, so a moving pointer reads as a moving lamp |
| **Flood** | Primary and commit buttons | A darker fill grows from where the pointer entered and follows it; its edge is displaced by noise that gets rougher with pointer speed; leaving drains it |
| **Shockwave** | Any liquid button, on press | The pill squeezes to 96%, one ring leaves the press point, the edge shudders and settles with an elastic curve |
| **Pointer light** | Anything with `data-lit` / `data-edge` | A soft highlight, and on cards a coloured light round the rim, sit under the pointer and fade when it leaves |
| **Ignite** | Checks, stages, files, the meter | A node or slash pops with an elastic curve, its tick draws in 350 to 400 ms, 8 to 16 sparks leave it |
| **Fill** | Choice tiles, vials, the count line | Liquid rises from the bottom (or along the line) in `t-scene` |
| **Tilt and foil** | Jerseys | Up to 9° toward the pointer; the foil's light follows it; a spring brings it back |
| **Heat** | The glow-up, the tier dial | The old tier's number fades out as the new one's fades in over `t-glow`; sparks at the end |

## Moments by screen

| Screen | Moment | What starts it | Reduced motion |
|---|---|---|---|
| Sign-in | The spark rises into the %, once (600 ms) | The page opening | The finished mark |
| Home | The Ones carousel turns in depth; soft light drifts behind it | Previous, Next, a drag, or Play | A scrolling row; no Play; still light |
| Quick capture and canvas | Flood, then a slash crosses "Share your idea" and the label answers "Shared" | The press | The checks page opens |
| Checks running | Each check ignites its node and the lit line grows to the next | The worker's real progress | Filled or empty; no orbit |
| Find your crew | Match cards tip up into place, 140 ms apart | The result arriving | They are simply there |
| My ideas, as a One | The glow-up (about 3.5 s in all) | First sign-in after a tier change | The end state, announced |
| Wall | The hundred pops in from the One outward; beads part round the pointer | The page opening; the pointer | The filled hundred |
| Office screen | Ambient light at the tier of the One on screen | An admin switching ambient on | Still light; the rotation waits for a press |
| Launch | The 30-second reveal (exists, DEC-046) | The operator pressing Start | The final frame and the bell |

Working screens (review desk, committee, console, admin, delivery) get answers and progress only: liquid buttons, the confirm panel growing out of its button, the thumb, rows sliding when a table is sorted.

## Reduced motion

Under `prefers-reduced-motion: reduce` (or `<html data-reduce-motion>`, which the Motion preview's tick box sets) nothing travels. Liquid, rings, lean, tilt, foil, orbit and sparks are off; the rim stops turning; glass that would materialise or morph simply appears. Loops stop. The ambient light is drawn once and stands still. Anything that would have moved appears in its end state, with a fade of at most 200 ms (`t-state`, `ease-move`). Nothing advances on its own. Whatever the animated version announces is still announced. In code: wrap every timeline in `OnePercentClub.play(timeline)`, which jumps to the end state when the setting is on, and check `OnePercentClub.reduced()` before starting anything pointer-driven.

## GSAP

Sequenced moments and pointer-driven motion use GSAP 3.13 (core only, about 72 KB), carried inside `components/bundle.js` and exposed as `OnePercentClub.gsap`. The first proposal avoided GSAP because its licence is not MIT. Since its 2025 "standard no-charge" licence, commercial use is free, including for a product like this; what it prohibits is building a visual animation-builder tool that competes with Webflow, which this is not. It is still not an open-source licence, so it needs one look from Legal before the merge. If Legal says no, the fallback is the Web Animations API: the timelines here use nothing GSAP-specific beyond easing names, staggers and `fromTo`.

## Performance

Everything pointer-driven is one delegated listener that writes custom properties. The ambient light is drawn at a sixth of the stage's size and stretched, and stops when off screen. Refraction maps are built once per element size, never per frame; while a piece of glass is changing size its map is stretched, and redrawn once when it settles. The rim follows the pointer in one animation frame for all glass on screen. On the 1366 px office PC and the budget Android the test is simple: typing in the canvas must never drop a frame because of something decorative. If it does, the stage loses its drifting light before anything else changes.
