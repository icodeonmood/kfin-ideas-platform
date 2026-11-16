---
id: F-TYPE
title: Type
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: []
last_delta: none
---

# Type

## `F-TYPE.faces` Typefaces

| Role | Family | Weights | Token |
|---|---|---|---|
| Display (headings, numbers, idea titles) | Inter Tight | 400, 500, 600 | `--fd` |
| Text (everything else) | Inter | 400, 450, 500, 600 | `--ft` |

1. Load both from Google Fonts with `display=swap`. Fallback stack: `'Inter Fallback', system-ui, sans-serif`, where Inter Fallback is local Arial with `size-adjust:107%; ascent-override:90%; descent-override:22.5%; line-gap-override:0%` so text does not jump when the web font arrives.
2. Global settings on the app root: `font-feature-settings: 'cv11' 1` (single-storey a), `-webkit-font-smoothing: antialiased`, `font-kerning: normal`, `text-rendering: optimizeLegibility`, `letter-spacing: -0.006em`.
3. Headings and legends use `text-wrap: balance`; paragraphs, list items and captions use `text-wrap: pretty`.
4. Any number that changes or lines up in a column uses tabular figures (`font-variant-numeric: tabular-nums`): counts, times, references, countdowns, money.
5. Headings are weight 500, never bold. 600 is used only for the brand word, badges, avatar initials and the current phone tab.

## `F-TYPE.scale` Scale

Desktop (1440 design width):

| Style | Size / line | Weight | Tracking | Face | Use |
|---|---|---|---|---|---|
| `d1` | clamp(44px, 4.6vw, 64px) / 1.02 | 500 | −0.035em | Display | Landing and showcase headlines |
| `d2` | clamp(35px, 4vw, 58px) / 1.06 | 500 | −0.028em | Display | Section heads on the Wall |
| `h1` | 40px / 1.08 | 500 | −0.03em | Display | Page title (one per screen) |
| `h2` | 28px / 1.12 | 500 | −0.024em | Display | Section title, sheet title (24px in sheets) |
| `h3` | 19px / 1.3 | 500 | −0.014em | Display | Card title, panel title (20px in the reviewer panel) |
| `lead` | 18px / 1.55 | 400 | base | Text | Intro under a page title, max 62ch |
| `body` | 15.5px / 1.6 | 400 | base | Text | Running text, max 65ch |
| `label` | 15px / 1.4 | 500 | base | Text | Field labels, button text (15px / 1) |
| `meta` | 13.5px / 1.45 | 400 | +0.004em | Text | Supporting lines, timestamps, references |
| `pill` | 13px / 1.4 | 500 | base | Text | Status pills |
| `micro` | 12px to 12.5px | 500 to 600 | base | Text | Badges, sidebar section heads, phone tab labels (11.5px) |

Phone (390 design width) overrides:

| Style | Size / line | Tracking |
|---|---|---|
| base | 15px | base |
| `d1` | 32px / 1.08 | −0.03em |
| `h1` | 28px / 1.12 | −0.026em |
| `h2` | 21px / 1.2 | −0.018em |
| `h3` | 17px / 1.3 | −0.01em |
| `lead` | 16px / 1.5 | base |
| `meta` | 13px | +0.004em |
| tab label | 11.5px / 1, weight 500 (600 when current) | +0.01em |

Big figures (impact tiles, a One's number, counts) use the display face, weight 500, tracking −0.04em, line-height 0.95, tabular figures. Sizes: Wall impact tiles `clamp(48px, 4.6vw, 72px)`; a One's number 80px; phone impact tiles 32px.

## `F-TYPE.rules` Rules

1. Sentence case everywhere. No all-caps labels, no letter-spaced eyebrows. (`S-OFFICE` and `S-LAUNCH` are the exception: they are wall displays carried over from an earlier design and keep their caps line.)
2. Do not put a small label above a heading unless the label tells the reader something the heading does not.
3. No arrows in buttons or links. No middle dots between meta items: use commas ("Problem, Investor service").
4. Do not accent one word of a heading with colour, italics or weight.
5. Minimum text size 12px; anything a person must read to act is 13.5px or larger.
6. Line length: body text is capped at 65 characters; titles are capped where a module says so (for example `S-R2` caps its title at 24ch).
7. Titles that must stay on one line say so in their module (`S-H2.title` is one). Otherwise titles wrap, balanced.
8. Truncate with an ellipsis only in the sidebar, phone nav title and list rows where the module says so; never truncate an idea title on its own page.

Resolved values for each style as painted are in `reference/computed/components.md` under `F-TYPE`.
