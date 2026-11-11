# 1% Club Design System

The working system for every screen of 1% Club, KFintech's ideas platform: tokens, type, space, components and motion, built on a brand that is already decided (`docs/BRAND.md`: Zed, White, Electric, Spark, Geist, the Spark mark, seven tiers, "1% spark. 99% sweat."). This system may change layout, components, density, motion and interaction. It never changes the palette, the type, the mark or the tagline.

Status: **proposal for review**, lane D, 11 Nov 2026. Synthetic data only in every preview.

## The idea: ninety-nine and one

The tagline is the layout rule. Every screen is ninety-nine parts sweat and one part spark.

| Ninety-nine | One |
|---|---|
| Quiet, gridded, black on white. Precise fields, square structure, plain words. It disappears into the work | Exactly one thing on the screen glows: the mark, a One's number, the moment that matters. Spark orange (or a One's tier colour) appears here and nowhere else |

This is the brand's own rule ("Spark: once per screen, only on the one", DEC-028) turned into a system. A designer never decides where to put orange; they decide what the one is.

## Two surfaces

A surface is a theme. Components never ask where they are; the semantic tokens change under them.

| Surface | `data-theme` | Where | The scene it is for |
|---|---|---|---|
| **White** | `white` | Canvas, My ideas, review desk, committee, console, admin, delivery | A client-service executive at a service centre under tube lights, on a 1366 px office PC between walk-ins, or on a budget Android on the bus home. Long forms, bright rooms: black on white, big targets |
| **Zed** | `zed` | Header, home band, Wall hero, Ones dashboard and glow-up, office screen, launch, sign-in | The lobby screen read from five metres, and the inauguration hall the moment the lamp is lit. Enormous type, one spark |

DEC-031 holds: one theme per screen type, no dark-mode switch.

## Colour

| Role | Token | Rule |
|---|---|---|
| Ground | `surface`, `surface-raised`, `surface-hover` | White / Paper / Mist on working screens; Zed / Graphite / Coal on brand ones. Raise with lightness, not shadow |
| Text | `ink`, `ink-muted` | Zed and Slate on white; White and Ash on Zed. Ash never on white |
| Press | `press`, `press-hover`, `link`, `focus` | Electric is ONLY for things you can press and the focus ring. The current nav item, progress bars and selected tabs are Zed or White, never Electric |
| The one | `spark`, `tier-1` to `tier-7` | Once per screen. Tier colours sit only on Zed or Graphite; on white, show a swatch ringed in Zed |
| States | `error`, `warn-ink`/`warn-wash`, `ok` | Functional only, always with a glyph and words. Error red is darker and cooler than Spark, so the two never read as the same thing |

Every text pairing in the tokens passes WCAG 2.1 AA (ratios are in each token's note). Control borders use Steel (4.6:1) so inputs pass 3:1 on white and Paper.

## Type

Geist for everything. Geist Mono **only** for jersey numbers (and the compounding line), never for labels, IDs or data: monospace as a "technical" costume is banned.

| Use | Style | Size / weight / tracking |
|---|---|---|
| Brand heroes | `display-160`, `display-96`, `display-64`, `display-44` | 800, tracking −0.035 to −0.05 em, leading 0.88 to 1.0 |
| Working screens | `h1` 36, `h2` 24, `h3` 19 | 800 / 600 / 600 |
| Reading | `body-long` 17 / 1.55 | What people type and read at length |
| UI | `body` 16, `small` 14, `label` 16/600, `button` 16/600 | 14 px is the floor on employee screens |
| A One's number | `jersey-200` to `jersey-17` | Geist Mono 600, tight |

No all-caps labels. No eyebrow labels above headings. No middle-dot meta strings: facts are a definition list.

## Space, shape, elevation

Space is a 4 px base stepping 4, 8, 12, 16, 24, 32, 48, 64, 96, 128 (`space-1` to `space-10`). The page gutter is 32 px at 1440 and 16 px at 360. Working screens cap at 1200 px; reading text at 68 ch.

Shape follows the mark, which is two zeros and a wedge:

| Radius | Token | On |
|---|---|---|
| Round | `radius-pill` | Everything you press or that names a state: buttons, chips, the stage pills. The zeros |
| Precise | `radius-field` 6 px | Inputs, selects, checkboxes |
| Soft | `radius-panel` 14 px | Panels, idea and match cards, status boxes |
| Slab | `radius-slab` 24 px | One cards, Zed slabs, dialogs |
| Square | `radius-none` | Bands, the header, tables. Structure is square |

Elevation: cards and panels sit on the page (`shadow-none`). Only things that float over the page (a dialog, the stuck side panel, the mobile menu) take `shadow-float`. The success pill sits beside the action that caused it, so it has no shadow.

## Three signature devices

1. **The slash.** The %'s rising stroke, at its exact angle (58.45°, CSS `skewX(-31.55deg)`), is the system's progress mark: the strength meter is five slashes, the stage tracker is three (Picked, Being built, Shipped), the checks are a column of slashes, the spinner is three slashes breathing. Filled is Zed (or White on Zed); empty is a Steel outline. Never Electric, never Spark.
2. **The jersey.** A One always appears as the back of their jersey: name (only with consent; otherwise "One No. 3"), the number huge in Geist Mono in their tier colour, a short bar in the same colour, then the impact brief. It is the same object on the home strip, the Wall, the dashboard, the leaderboard, the office screen and the email number block, and it matches the real t-shirt (DEC-049).
3. **The hundred.** A ten-by-ten field of dots, used only on brand surfaces and only when it encodes real data: "of the last 100 ideas, this many were picked, built, shipped", with the newest One as the single Spark dot. It is "Every hundred has a one" made literal.

## Components

| Group | Components |
|---|---|
| Actions | Button, ConfirmInPlace |
| Forms | Field, ChoiceCard, PersonalData, ResearchFiles, VoiceNote |
| Progress | StrengthMeter, StageTracker, ChecksRunning |
| Feedback | Status (error, check first, coming soon, success, empty), PausedBanner, Dialog |
| Navigation | Header, SectionNav, Table |
| Content | IdeaCard, MatchCard, OneJersey, Hundred, OnesStrip |
| Motion | Motion (the tokens and each P0 screen's one moment) |

## Iconography

Glyphs are drawn the way the mark is drawn: circles and straight strokes, 20 px, 1.75 px stroke, round caps, `currentColor`. No icon fonts, no emoji, no filled pictograms. A glyph never stands alone: it sits beside words or carries an `aria-label`.

## Words

Plain Indian business English, short sentences, sentence case. The platform's words are fixed: **canvas**, **Already running**, **Find your crew**, **review desk**, **1% Club core committee**, **Ones**, "No. 17", and the stages **Picked**, **Being built**, **Shipped**. Never on screen: Garage, duplicate, rejected, already solved. A button says exactly what happens ("Share your idea", "Carry out and send"), and its success message uses the same verb. Wording in previews is today's wording from the app; new or changed copy is marked and goes to HR (DEC-091).

## Accessibility floor

WCAG 2.1 AA on every screen: 4.5:1 text, 3:1 for controls and focus, a visible 3 px focus ring, 48 px targets, 360 px with no sideways scroll, 200% zoom, and `prefers-reduced-motion` honoured (see Motion). Colour is never the only signal: every state has a glyph shape and words.

## Using it in the app

`components/bundle.css` is plain CSS over the tokens: no Tailwind, no component library, no new dependency. At hand-off it replaces the ad-hoc parts of `apps/web/src/app/globals.css` class by class, keeping every accessible name, id, role, live region and on-screen word the e2e tests rely on. See the Hand-off section.
