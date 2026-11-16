---
id: F-MOTION
title: Motion and transitions
rev: 1
status: baseline
source: reference/prototype/Motion.dc.html
depends_on: []
last_delta: none
---

# Motion and transitions

Live specimens of everything here: `reference/prototype/Motion.dc.html`. Exact keyframes: `reference/css/motion.css`. The prototype's engine, for reference only: `reference/css/motion-engine.js`.

## `F-MOTION.rules` Four rules

1. **Quick where people work.** Forms, lists and the review side move in under half a second. Nothing makes anyone wait.
2. **Cinematic where it matters.** Landing, Sign in, Home, the Wall, Find your crew, Profile, the One dashboard and "What happens after you share" get longer, layered arrivals.
3. **Every move says where.** Things grow out of what was tapped and go back where they came from.
4. **Reduced motion means still.** With `prefers-reduced-motion: reduce`, nothing travels, nothing loops, hand-overs are skipped, counted numbers show their final value, and every screen simply appears.

Hard limits:

5. Motion never blocks input. Any key, click or scroll finishes or cancels a running animation.
6. Animate only `transform` (or the individual `translate` / `scale` properties), `opacity` and a short `filter: blur` on arrival. No layout-affecting animation in loops.
7. A layout morph measures at most 180 elements per change, and only around what was touched.
8. What persists moves; it does not fade out and back in. The sidebar and the phone tab bar never animate between screens.

## `F-MOTION.tokens` Durations and curves

| Token | Value | Used for |
|---|---|---|
| `--mo-press` | 110ms | A button or chip going down under the finger |
| `--mo-quick` | 180ms | Hover, focus ring, small colour changes |
| `--mo-state` | 260ms | Selected, read, on or off |
| `--mo-move` | 460ms | Things changing place inside a screen; the next step sliding in |
| `--mo-scene` | 720ms | A working screen arriving, block by block |
| `--mo-hero` | 1000ms | Showcase screens arriving; hero lines word by word |
| spring | 520 to 560ms | Pop-ups, sheets, a selection landing, a press letting go |
| `--mo-gap` | 56ms (36ms for step slides, 80ms on cinematic screens) | Stagger between blocks |

| Curve | Value | Used for |
|---|---|---|
| `--mo-out` (expo out) | `cubic-bezier(.16,1,.3,1)` | Arrivals, reveals |
| `--mo-emph` (emphasised in) | `cubic-bezier(.05,.7,.1,1)` | Things entering the screen (phone sheets) |
| `--mo-acc` (accelerate out) | `cubic-bezier(.3,0,.8,.15)` | Things leaving |
| `--mo-snap` (standard) | `cubic-bezier(.2,0,0,1)` | State changes, presses |
| `--mo-spring` | `linear(...)` with a 16% overshoot; full value in `tokens.json` | Pop-ups, selection |
| `--mo-soft` | `linear(...)` with a 3% overshoot; full value in `tokens.json` | Gentle settles |

Leaving is always faster than arriving.

## `F-MOTION.arrive` A screen arriving

1. Content blocks of the main region rise in one after another: from `opacity 0, translateY 22px, scale .985, blur 6px`, over `--mo-scene` with `--mo-out`, staggered by `--mo-gap` for the first six blocks (the seventh onward share the sixth's delay).
2. The page heading settles a beat later (90ms): up from 0.45em below, blur 8px, tracking tightening from +0.02em, over scene + 200ms.
3. Cinematic screens (rule 2 list) use the deeper arrival: from `translateY 48px, scale .96, blur 14px`, scene 1000ms, gap 80ms. Hero headlines reveal word by word (each word up from 115% with a 2.5° tilt, 1.15s, 55ms stagger).
4. Ambient light, the sidebar, the tab bar and sticky bars do not take part.
5. On scroll, sections marked for reveal on cinematic screens (cards, list rows, section heads on Landing and the Wall) rise in once as they enter the viewport. Big figures count up once (impact tiles on the Wall, a One's figures, points on Profile).

## `F-MOTION.handover` From one screen to the next

Five hand-overs. The screen being left records what was tapped; the next screen grows out of it. Total hand-over is under 0.5s before content starts arriving.

| Hand-over | What happens | Used for |
|---|---|---|
| **Grow from the card** | The tapped row or card opens into the next screen; its title flies up to become the page heading. New content starts 380ms later. | Rows and cards to their detail: My ideas → Status, Review desk → the idea, Inbox → Answer, Wall → an idea |
| **Flood from the button** | Ink spreads out of the pressed button, then lifts like a curtain off the new screen. New content starts 420ms later. | "Share a problem" anywhere, the phone Share tab, every primary button that starts a flow |
| **Fade through** | The page changes in place with a small zoom (old: fade to 0 and scale .985 in 220ms; new: from scale 1.01 in 420ms). Sidebar and tab bar do not move. | Sidebar and tab-bar navigation, any other link |
| **Slide forward** | The next step comes in from 48px to the right, `--mo-move`, 36ms stagger. | Next, Continue, the steps of Check it, sign-in steps, answering questions |
| **Slide back** | The previous step comes back from 48px to the left. | Back links, breadcrumbs |

Implementation note: the prototype uses cross-document view transitions plus a session record. In a single-page app, use the router's transition hooks or the View Transitions API; the result must match the table.

## `F-MOTION.inside` Inside a screen

| Pattern | Behaviour | Used on |
|---|---|---|
| **Tabs slide** | The underline travels from the old tab to the new one and stretches to fit. | Review desk, My ideas, Inbox, Profile, Committee |
| **Choices land** | A ring slides from the last choice to the new one, which pops into place on the spring (520ms). | Sorting chips, filters, sort options, answers, the kind chips on the Wall |
| **Lists re-sort** | Rows glide to their new order (560ms, `--mo-snap`) instead of jumping. Rows are matched by content, so a row must keep the same text when the sort changes. | Review desk, My ideas, Wall "Just in" |
| **Layout morph** | Whatever moved glides to its new place; whatever is new fades in. | Check it parts, Status card, Home cards, Inbox reader, Tell it when the draft panel appears |
| **Things open** | Menus open from their button (260ms, from scale .95, 6px above, blur 4px) and close back into it. Pop-ups and sheets arrive on the spring (520ms, from 18px below, scale .94, blur 6px). Phone sheets slide up from the bottom (560ms, `--mo-emph`). Backdrops fade in `--mo-state`. | All menus, pop-ups, sheets |
| **Notes unfold** | Inline confirmations, banners and notes unfold downward (420ms; clip from the top, 6px rise). `details` content animates its height (380ms). | Confirm rows, "Merged" banner, folded sections |
| **Field messages** | Drop in from 4px above in 280ms (`cubic-bezier(.2,.7,.2,1)`). An error also nudges sideways once (480ms). A wrong sign-in code shakes the code boxes (420ms). | `C-FIELD-MSG` |
| **Progress draws** | The stage track draws its line (1.2s) and each node pops in turn (700ms spring, 120ms apart); the current node breathes twice. | `C-TRACK` on Status, a colleague's idea, How |
| **The 1% spark** | A burst of small slashes from the button (5×14px, rounded 3px). It marks a commitment only: sending an idea, sending a team-up request, sending answers, sending a decision. Never on an ordinary click. | Those four moments |
| **Press** | Buttons and chips scale to .97 on press (110ms) and release on the spring. | All buttons and chips |
| **Primary hover** | A light sheen crosses the ink button once (900ms) and a soft drop shadow appears. | `C-BUTTON` primary |
| **Tilt** | Showcase cards tilt a few degrees toward the pointer. | Landing figure, Ones cards and crew cards on Home, crew cards, Profile card |

Component-specific motion is specified in the component: the draft loader (`C-DRAFT-LOADER`), the pack-of-cards deck (`C-CREW-DECK`), the Ones fan and its wheel scrolling (`C-ONES-FAN`), the folding sidebar (`C-SIDEBAR`), the listen player (`C-LISTEN`).

## `F-MOTION.focus` Focus and announcements

1. After navigation, focus lands on the page heading. After a sheet or pop-up closes, focus returns to the control that opened it.
2. When a pop-up or sheet opens, focus moves inside it so Escape and Tab work at once.
3. A value that changed without the person acting (a draft field filling in, a count updating) gets one polite announcement (`aria-live="polite"`), never more than one per change.
4. The focus ring is 2px `--blue` with a 3px offset, and its offset eases in over `--mo-quick`.

## `F-MOTION.reduced` Reduced motion

1. All animations and transitions collapse to effectively instant (0.01ms), one iteration.
2. Hand-overs are skipped: the next screen appears.
3. The effects layer (sparks, rings, ghosts) is not rendered.
4. Loops stop: skeleton shimmer, the loader's sweeping light, the breathing node, the listening indicator.
5. Wheel-driven and swipe-driven moves still work; they jump instead of gliding.

## `F-MOTION.build` Build notes

1. The prototype loads GSAP 3.13 (Flip, SplitText, ScrollTrigger, CustomEase) from a CDN for layout morphs, word reveals and scroll scenes, and uses the browser's own animation engine for first frames, hand-overs, presses and sparks. The build may use any library that reaches the same result; whatever is chosen must be bundled, not loaded from a public CDN.
2. `OPEN:` GSAP's standard licence is free for commercial use but is not open source. Legal to confirm before launch (owner: product). If not cleared, use the Web Animations API and a FLIP helper.
3. If the animation library fails to load, screens must still arrive, buttons must still press and hand-overs must still play.
