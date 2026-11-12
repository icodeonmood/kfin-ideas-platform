# 1% Club Design System

The working system for every screen of 1% Club, KFintech's ideas platform. The brand is already decided and does not change here (`docs/BRAND.md`: Zed, White, Electric, Spark, the seven tier colours, Geist, the Spark mark, "1% spark. 99% sweat."). Everything else was rebuilt on 11 Nov 2026: material, depth, motion, components and layout.

Status: **second proposal for review**, lane D, 11 Nov 2026. It replaces the first (flat) proposal. Revised the same day: the ground is matte, and the glass now bends light (refraction, colour split, a rim that follows the pointer) instead of only blurring it. Synthetic data only in every preview.

## The idea: molten glass

The club is named for a spark, and its tiers are named for heat: Spark, Glow, Flame, Blaze, White heat, Blue flame, Star. Glass is what heat makes. So every surface is glass, lit from behind, and the system gets hotter as a One rises.

| Ninety-nine | One |
|---|---|
| A matte ground with nothing on it: no lines, no pattern, no particles, only a fine grain. On it, glass: panels, cards, fields, buttons. This is the sweat. It is quiet, legible and the same on every screen, and because the ground is flat, the glass is the only thing with shine and depth | One hot thing per screen, in the heat colour: a lit slash tip, a commit button's rim, a One's number, the newest One in the hundred. Spark orange until someone is a One; then their tier's colour |

A designer never decides where to put orange. They decide what the one hot thing on the screen is, and the system lights it.

## Two surfaces

A surface is a theme. Components never ask where they are; the tokens change under them.

| Surface | `data-theme` | Where | The scene it is for |
|---|---|---|---|
| **White** | `white` | Canvas, My ideas, review desk, committee, console, admin, delivery | A client-service executive at a service centre under tube lights, on a 1366 px office PC between walk-ins, or on a budget Android on the bus home. Long forms, bright rooms: ink on white glass over a matte grey ground, big targets |
| **Zed** | `zed` | Home band, Wall hero, Ones dashboard and glow-up, office screen, launch, sign-in | The lobby screen read from five metres, and the inauguration hall the moment the lamp is lit. Matte charcoal, smoked glass, two soft lights, enormous type |

The header dock, the success pill, the recorder and the paused band are dark glass on both surfaces. DEC-031 holds: one theme per screen type, no dark-mode switch.

## The stage

The stage is a matte ground, and it is deliberately empty. Put `class="stage"` on the page body or a region. On White it is a neutral grey one step below white (`matte` running to `matte-deep`), so white glass visibly lifts off it. On Zed it is charcoal with two wide, soft lights: the heat colour from the top right and Electric from the bottom left, each capped at about 16% so text holds its contrast at every tier. Both carry a fine grain and nothing else: no lines, no pattern, no particles. On brand surfaces add `data-glow` and `bundle.js` lets those lights drift very slowly behind the glass (one to four of them, by tier), which is what makes the glass read as glass. Working screens get no moving light at all.

## Glass

Glass here bends light; it does not only blur it. That is the difference between this material and the frosted panels of the last ten years, and it is what Apple's Liquid Glass set as the standard: the edge of a piece of glass squeezes what is behind it, splits its colour a little, and catches the light.

### Two weights

| Weight | Class | What it is for | How it behaves |
|---|---|---|---|
| **Pane** | `glass`, and every card, panel, sheet and dialog | Holding content: text, forms, tables | Frosted enough (`blur-glass`) and filled enough that text on it passes 4.5:1 over anything. Stands on the matte ground; its rim is lit and it casts a shadow, but it rarely has anything to bend |
| **Lens** | `lens`, `round-btn`, `mic`, the nav thumb (`thumb-lens`), and the header bar (`hdr-dock`) | Floating over content: controls, navigation, a magnifier | Clear, almost no blur. What is behind stays visible and bends at the rim. Carries an icon or nothing; the header bar and text buttons are the exception and are smoked or filled enough for their words |

Three more materials complete the set: a **well** (`.input`, `.drop-zone`: anything you type or drop into sits below the surface, `shadow-well`, Steel border at 3:1), **frost** (`.paused` only: `blur-frost`, no colour, no motion: the one cold thing), and **liquid** (`btn-primary`, a selected choice, a filling vial: a fill that moves, always darker than what it replaces).

### The optics

| Effect | What you see | How it is made | Dial |
|---|---|---|---|
| Refraction | At the rim, the backdrop is squeezed inward, hardest at the very edge; the middle is undisturbed | A displacement map cut to the element's exact rounded shape. For each distance from the edge one ray is traced through a convex squircle bezel with Snell's law (air 1.0 into glass 1.5) | `data-refract` (the largest shift in px; 20 to 30 for controls, 30 to 45 for sheets), `data-bezel` |
| Colour split | A faint prismatic fringe where high-contrast content meets the rim | Red, green and blue are bent by slightly different amounts and recombined | `data-dispersion` (0.1 by default; 0 turns it off) |
| Magnify | A round lens enlarges what is under its centre | A uniform pull toward the centre added to the map | `data-zoom` |
| Rim light | A thin bright line just inside the edge, strongest where the edge faces the light and again, fainter, opposite | A conic gradient on a 1.5 px ring; `bundle.js` turns it to face the pointer, wherever the pointer is on the page | `--rim-hi`, `--rim-mid`, `--rim-lo` |
| Pointer light | A soft highlight under the pointer on a pane; on a pressable card a coloured light also runs round the rim | `data-lit`, `data-edge` | `--lit-size`, `--edge-color` |
| Illumination | A press sends one ring of light out through the glass from the point of contact | A radial gradient driven by `--pulse` | On every `data-lit` surface |
| Thickness | Glass looks like a slab, not a sticker | A lit top edge, an inner glow, a faint Electric cast at the foot, a tight contact shadow and a wide soft one (`shadow-glass`, `shadow-float`) | Bigger pieces get thicker fills and deeper shadows |

Refraction and the colour split need a Chromium browser (only Chromium lets `backdrop-filter` take an SVG filter). Safari and Firefox show the same glass with blur, rim light, shadows and motion, and no bend. Nothing depends on the bend to be understood.

### How glass moves

| Move | Rule |
|---|---|
| **Materialise** | Glass does not fade in. It arrives by bending light: over-refracted at first, then it relaxes into place (`OnePercentClub.materialize(el)`; `dematerialize` reverses it) |
| **Morph** | One piece of glass becomes another: a button flows out into its confirm panel, "Menu" into the sheet (`OnePercentClub.morph(from, to)`). Glass is never cut to a new shape |
| **Lift** | A pressed lens lifts toward you (3 to 14% larger), bends light harder for a moment and settles with a spring. Only the liquid primary squeezes |
| **Flow** | The nav thumb is a bead under the labels and a lens over them, moving as one. In flight it lifts, stretches toward where it is going, and the labels bend as it passes |

### Rules

1. **Glass floats over content; content does not float over glass.** Lenses belong to the layer of controls and navigation. Do not stack a lens on a lens.
2. **Words need a pane.** Body text sits on a pane or the ground, never on a clear lens. A text button is filled or smoked enough for its label; over imagery or large type use a round icon lens or the primary.
3. **The header bar is thin dark glass** (`dock-thin`, 72%): the page shows and bends through it, and it carries White text only (7:1 over a white page; nav labels at 80% white, 5.2:1). Sheets, the toast and the recorder are thick dark glass (`dock`, 86%), where Ash is safe.
4. **A dialog dims the page to 72% and blurs it only 3 px**, so the page is still there and bends at the sheet's rim, and Ash inside the sheet still holds 5.3:1 over a white page.
5. **Glass is never square and never flat on its ground.**
6. **Two settings are honoured.** With *reduce transparency* glass becomes solid and nothing shows or bends through it. With *more contrast* every glass edge becomes a plain strong line. With *reduced motion* the rim stops turning and glass simply appears.

## Colour

| Role | Token | Rule |
|---|---|---|
| Ground | `matte`, `matte-deep`, `link-ground` | The matte stage. Links written straight on it use `link-ground` (the deeper Electric), which holds 5.8:1 where Electric would drop to 4.2:1 |
| Glass | `glass`, `glass-edge`, `glass-shine`, `dock`, `dock-thin` | The materials above |
| Text | `ink`, `ink-muted` | Zed and Slate on white glass (18:1 and 5.7:1 at worst) and on the matte ground (16:1 and 4.9:1 at worst); White and Ash on smoked glass (12:1 and 4.7:1 at worst). Ash never on white |
| Press | `press`, `press-hover`, `link`, `focus` | Electric is ONLY for things you can press and the focus ring. The nav thumb, progress and selected tabs are ink or white glass, never Electric |
| Heat | `heat`, `heat-core`, `spark`, `tier-1` to `tier-7` | The one hot thing. Light and fill, never small text: Tier 6 and Tier 7 are 3.6:1 and 2.8:1 on Zed. A One's number in a chip is `heat-core` with a glow in `heat` |
| States | `error`, `warn-ink`/`warn-wash`, `ok` | Functional only, always with a glyph and words. Error red is darker and cooler than Spark, so the two never read as the same thing |

## Type

Geist for everything. Geist Mono **only** for jersey numbers, never for labels, IDs or data: monospace as a "technical" costume is banned.

| Use | Style | Size / weight / tracking |
|---|---|---|
| Brand heroes | `display-160`, `display-96`, `display-64`, `display-44` | 800, tracking −0.035 to −0.05 em, leading 0.88 to 1.0 |
| Working screens | `h1` 36, `h2` 24, `h3` 19 | 800 / 600 / 600 |
| Big numerals | Score, clock, stats | 800 at 40 to 72 px, tabular: a count is a figure in the composition, not a label |
| Reading | `body-long` 17 / 1.55 | What people type and read at length |
| UI | `body` 16, `small` 14, `label` 16/600, `button` 16/600 | 14 px is the floor on employee screens |
| A One's number | `jersey-200` to `jersey-17` | Geist Mono 600, tight, `heat-core` running down to the tier colour |

No all-caps labels. No eyebrow labels above headings. No middle-dot meta strings: facts are a definition list.

## Space, shape, depth

Space is a 4 px base stepping 4, 8, 12, 16, 24, 32, 48, 64, 96, 128 (`space-1` to `space-10`). The page gutter is 32 px at 1440 and 16 px at 360. Working screens cap at 1200 px; reading text at 68 ch.

| Radius | Token | On |
|---|---|---|
| Round | `radius-pill` | Everything you press or that names a state: buttons, chips, the dock, the section nav. The zeros |
| Well | `radius-field` 16 px | Inputs, selects, file rows (checkboxes 8 px) |
| Card | `radius-panel` 22 px | Idea and match cards, status glass, choice tiles, the table |
| Sheet | `radius-slab` 32 px | Dialogs, jerseys, the meter, confirm panels, Zed slabs |
| Square | `radius-none` | Full-bleed brand bands only |

Depth has three levels: wells sit below the surface (`shadow-well`), glass sits a little above it (`shadow-glass`), and the dock, dialogs, confirm panels and toasts float (`shadow-float`).

## Signature devices

1. **The slash.** The %'s rising stroke, at its exact angle (58.45°, CSS `skewX(-31.55deg)`), is the system's progress mark and nothing else (it is never a background pattern): the strength meter is five slanted vials, the stage tracker is three slashes, a table's strength is five small ones, the spinner is three breathing. A filled slash is ink at the base and lit in the heat colour at the tip. Never Electric.
2. **The ember.** The one hot thing, always part of a component, never of the backdrop: the newest One in the hundred, a lit slash tip, the ring in an empty state, the dot on a live recorder, a commit button's rim.
3. **The jersey.** A One always appears as the back of their jersey, on mesh, tilting toward the pointer, with foil that grows with the tier. It matches the real t-shirt (DEC-049).
4. **The hundred.** A ten-by-ten field of beads, used only on brand surfaces and only when it encodes real data: "of the last 100 ideas, this many were picked, built, shipped", with the newest One as the single ember.
5. **Liquid.** What answers a press: the flood in a primary button, the fill rising in a selected tile, a vial filling, the nav thumb stretching to where it is going.

## Spark tiers

`data-tier="0"` to `"7"` on any element re-lights everything inside it: heat colour, how much soft light is in the room and how fast it drifts, glow radius, jersey foil. Layout, words, Electric and every contrast ratio stay put. See the Spark tiers section and the SparkTiers component.

## Components

| Group | Components |
|---|---|
| Material | LiquidGlass (the glass itself, on a page you can drag it across) |
| Actions | Button, ConfirmInPlace |
| Forms | Field, ChoiceCard, PersonalData, ResearchFiles, VoiceNote |
| Progress | StrengthMeter, StageTracker, ChecksRunning |
| Feedback | Status (error, check first, coming soon, success, empty), PausedBanner, Dialog |
| Navigation | Header, SectionNav, Table |
| Content | IdeaCard, MatchCard, OneJersey, Hundred, OnesStrip |
| Motion | Motion (the tokens and the signature moves, playable) |
| Tiers | SparkTiers (the whole system on one dial) |

## Iconography

Glyphs are drawn the way the mark is drawn: circles and straight strokes, 20 px, 1.75 px stroke, round caps, `currentColor`. No icon fonts, no emoji, no filled pictograms. A glyph never stands alone: it sits beside words or carries an `aria-label`. Choice tiles carry larger 44 px drawings in the same hand, with at most one stroke in the heat colour.

## Words

Plain Indian business English, short sentences, sentence case. The platform's words are fixed: **canvas**, **Already running**, **Find your crew**, **review desk**, **1% Club core committee**, **Ones**, "No. 17", and the stages **Picked**, **Being built**, **Shipped**. Never on screen: Garage, duplicate, rejected, already solved. A button says exactly what happens ("Share your idea", "Carry out and send"), and its success message uses the same verb. Wording in previews is today's wording from the app; new or changed copy is named in each component's guidelines and goes to HR (DEC-091).

## Accessibility floor

WCAG 2.1 AA on every screen: 4.5:1 text, 3:1 for controls and focus, a visible 3 px focus ring, 48 px targets, 360 px with no sideways scroll, 200% zoom, and `prefers-reduced-motion` honoured (see Motion). Colour is never the only signal: every state has a shape and words. Glass never lowers this floor: fills are opaque enough, and smoked enough on Zed, that every text pair above holds over the brightest tier's glow; the liquid in a button is always darker than its fill; canvases are `aria-hidden` and everything they show is also in words.

## Using it in the app

Two files and no build step. `components/bundle.css` is plain CSS over the tokens. `components/bundle.js` is one classic script (`window.OnePercentClub`) that carries GSAP and wires the behaviour from class names and a few attributes: `data-lit`, `data-edge`, `data-tilt`, `data-glow`, `data-refract`, plus `data-thumb` on navs and `data-tier` anywhere. It keeps every accessible name, id, role, live region and on-screen word the e2e tests rely on. Without the script the system still works: buttons, fields and states are complete in CSS; only the liquid, the bend, the lights and the timelines are missing. See the Hand-off section.
