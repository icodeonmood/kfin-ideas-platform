---
id: F-COLOR
title: Colour
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: []
last_delta: none
---

# Colour

Machine-readable values: `tokens.json` and `tokens.css` in this folder. Build every colour from a token. A raw hex in a component is a defect, with the exceptions listed under `F-COLOR.raw`.

## `F-COLOR.principles` How colour is used

1. The page is quiet: warm grey paper, near-black ink, white glass cards. Colour means something.
2. **Blue is the one interactive colour**: links on hover, focus rings, selected chips, current nav item, progress, primary status ("With the review desk", "Picked", "Being built").
3. **Spark orange belongs to the brand mark** (the slash and dot of the % glyph) and to nothing else in the interface chrome. It also tints one ambient glow on browsing screens.
4. **Warm colour means "needs you".** Amber is used for anything waiting on the signed-in person (pill "Needs you", countdowns, a question waiting). Because of that, avatar rings are neutral grey everywhere except where a tier is the subject (see `F-COLOR.tiers`).
5. **Status is never colour alone.** Every status has a dot plus words (see `C-PILL`). Errors have an icon plus words.
6. No colour at full saturation and full brightness. All accents were conditioned in OKLCH to 87% of their original chroma at the same lightness (round R34). Do not "brighten" them.
7. One ink primary button per view. Everything else is line, soft or text buttons (see `C-BUTTON`).

## `F-COLOR.core` Core tokens

| Token | Hex | Role |
|---|---|---|
| `--ink` | `#111111` | Text, primary button fill, strong rules |
| `--ink2` | `#2A2A2E` | Primary button hover, secondary strong text, nav text |
| `--mute2` | `#4A4A50` | Body text on paper, supporting text that must stay readable |
| `--mute` | `#5F5F64` | Meta text, hints, labels (4.5:1 on paper and on white) |
| `--faint` | `#6C6C70` | Neutral pill dot, chevrons. Not for text under 18px on paper |
| `--paper` | `#F3F3F1` | Page background |
| `--card` | `#FFFFFF` solid; `rgba(255,255,255,.78)` inside the signed-in shell | Card surface. In the shell, cards are glass (see `F-COLOR.glass`) |
| `--sunk` | `#E9E9E6` | Wells, soft buttons, neutral pill, skeleton base |
| `--rule` | `#DADAD6` | Dividers between rows |
| `--rule2` | `#E4E4E0` | Card borders, bar borders, disabled button fill |
| `--edge` | `#D0D0CB` | Control outlines (line button, chip) |
| `--blue` | `#395DED` | Interactive, focus ring, selection ring, progress |
| `--blueT` | `#2948C6` | Blue text on white or wash (passes 4.5:1) |
| `--wash` | `#EEF1FF` | Selected chip fill, blue pill fill, blue note fill |
| `--spark` | `#F46835` | Brand mark only |

Supporting neutrals that are fixed values in the kit (keep them as tokens in the build; suggested names in `tokens.json`):

| Hex | Use |
|---|---|
| `#8C8C91` | Field border at rest (3:1 against white) |
| `#6B6B70` | Placeholder text, disabled button text |
| `#A3A3A6` | Underline of text buttons and quiet links at rest |
| `#B9C3FF` | Underline of blue text buttons |
| `#1E2E99` | Text on a blue note (`.note.blue`) |
| `#E0E0DC` | Soft button hover |
| `#E2E2DE` | Avatar fill without a tier |
| `#ECECE8` | Avatar fill inside a ring |
| `#D9D9DE` | Neutral avatar ring |
| `#F1F1EE` | Skeleton highlight |
| `#18191D` | Dark slab background (The Ones on the Wall, One dashboard hero) |

## `F-COLOR.status` Status colours

Each status has three tokens: `D` dot, `T` text, `W` wash (background).

| Status | Dot | Text | Wash | Used for |
|---|---|---|---|---|
| Neutral | `--faint` `#6C6C70` | `--ink` | `--sunk` `#E9E9E6` | Draft, Not picked, Withdrawn, Closed |
| Blue | `--blue` `#395DED` | `--blueT` `#2948C6` | `--wash` `#EEF1FF` | Checking, With the review desk, Picked, Being built |
| OK | `--okD` `#12B76A` | `--okT` `#067647` | `--okW` `#ECFDF3` | Shipped, Checked (file), Answered, saved |
| Warn | `--warnD` `#EE953A` | `--warnT` `#B54708` | `--warnW` `#FFFAEB` | Needs you, Not now, time running out, warnings under fields |
| Bad | `--badD` `#E55446` | `--badT` `#B42318` | `--badW` `#FEF3F2` | Errors, failed upload, wrong code |

The full status-to-pill table for ideas is in `E-ENUMS.idea-status`.

## `F-COLOR.tiers` Tier colours (the Ones)

A One has a number and a tier. The tier colour appears as a conic ring around the avatar, a 24×4px bar on a One's card, and a glow behind the card.

| Tier | Name | Key colour | Ring (conic-gradient from 210deg) |
|---|---|---|---|
| 1 | Spark | `#F5863B` | `#F5863B, #FFC27A, #F69F54, #DE6D2D, #F5863B` |
| 2 | Glow | `#F35532` | `#F35532, #FF9A6B, #F4744C, #CE4327, #F35532` |
| 3 | Flame | `#F34770` | `#F34770, #FF8FB0, #F4678D, #CD3254, #F34770` |
| 4 | Blaze | `#F23729` | `#F23729, #F58267, #F34F41, #C80000, #F23729` |
| 5 | White heat | `#4DD187` | `#4DD187, #A6F2CC, #67DFA0, #12A862, #4DD187` |
| 6 | Blue flame | `#8841E1` | `#8841E1, #C99BFF, #9F65E8, #672BC0, #8841E1` |
| 7 | Star | `#264DC9` | `#264DC9, #8FA6FF, #5070E1, #1232A8, #264DC9` |

Rules:

1. Tier rings show **only** on: your own account button (sidebar foot on desktop, top-right on phone), Profile, the Wall, the One dashboard, and the Ones cards on Home. Every other avatar uses the neutral ring `#D9D9DE`.
2. Ring build: 3px transparent border, `background: linear-gradient(#ECECE8,#ECECE8) padding-box, var(--ring) border-box`, plus `inset 0 0 0 2px #FFFFFF`.
3. Glow behind a One's card: radial gradient from the key colour at 32% alpha (`+ '52'`) to 0%.

`OPEN:` tier 6 is named "Blue flame" but its ring is violet, and tier 7 "Star" is blue. Confirm the name-to-colour pairing with the product owner before launch. Build what the table says.

## `F-COLOR.glass` Glass and ambient light (signed-in shell)

Signed-in screens sit on paper with soft blurred light behind glass cards.

| Surface | Fill | Blur | Border / shadow |
|---|---|---|---|
| Card, panel | `rgba(255,255,255,.78)` | `blur(18px) saturate(1.4)` | 1px `rgba(17,17,17,.07)`; `inset 0 1px 0 rgba(255,255,255,.9), 0 18px 40px -30px rgba(17,17,17,.28)` |
| `.glass` (review side, sheets) | `linear-gradient(180deg, rgba(255,255,255,.78), rgba(255,255,255,.52))` | `blur(26px) saturate(1.45)` | radius 20px; inset top highlight + 1px white inner ring + faint outer ring |
| Sidebar | `linear-gradient(180deg, rgba(255,255,255,.72), rgba(255,255,255,.45))` | `blur(22px) saturate(1.4)` | `1px 0 0 rgba(17,17,17,.08)` on the right edge |
| Task bar (Tell it, Check it) | `rgba(246,246,244,.55)` | `blur(10px)` | bottom border `--rule2` |
| Pop-up body (`C-PREVIEW`) | `linear-gradient(180deg, rgba(255,255,255,.94), rgba(255,255,255,.84))` | `blur(26px) saturate(1.5)` | radius 28px; `0 50px 100px -40px rgba(17,17,17,.5)` |
| Pop-up backdrop | `rgba(232,232,238,.42)` | `blur(14px) saturate(1.3)` | none |

Ambient light (`.amb`): six absolutely positioned circles, `filter: blur(48px)`, behind everything (`z-index:-1`), never interactive.

| Layer | Size | Position | Colour |
|---|---|---|---|
| a1 | 820×600 | left 40, top −140 | blue `rgba(57,93,237,.34)` |
| a2 | 740×560 | right −180, top 160 | spark `rgba(244,104,53,.24)` |
| a3 | 960×600 | left 30%, top 620 | violet `rgba(146,128,255,.30)` |
| a4 | 780×560 | right −120, top 1480 | blue `rgba(57,93,237,.28)` |
| a5 | 720×520 | left 140, top 2180 | spark `rgba(244,104,53,.22)` |
| a6 | 920×560 | right 12%, top 2920 | violet `rgba(146,128,255,.26)` |

1. **Full light** (all six layers): Landing, Sign in, Home, Tell it (`S-04`, `S-04B`), Find your crew, Wall, One dashboard, Profile, Share another way, What happens after you share.
2. **Quiet light** (only a1 and a4, at 50% opacity; no warm or violet light): Check it, Edit, Status, My ideas, Conversation, a colleague's idea, Inbox, Answer, and the whole review side (`S-R1` to `S-R4`, `S-H2B`). The reason: on these screens warm colour is reserved for "needs you".
3. A blurred element inside a glass surface must not be `position: fixed`: backdrop-filter makes the glass its containing block. Pop-ups and sheets are mounted at the page root.

## `F-COLOR.gradients` Gradients that are allowed

Gradients are used only as light, never as a decorative wash on a flat control.

| Where | Gradient |
|---|---|
| Preview pop-up band, hue 1 | `linear-gradient(165deg, #3455EC 0%, #6957EE 55%, #F58256 130%)` |
| Preview pop-up band, hue 2 | `linear-gradient(165deg, #7958EE 0%, #4261EC 60%, #1E2E99 120%)` |
| Primary button hover sheen | `linear-gradient(115deg, transparent 0 38%, rgba(255,255,255,.2) 50%, transparent 62% 100%)`, slides across once on hover |
| Idea card on Status, crew cards, phone crew cards | per-card hue pairs; exact stops are in `reference/computed/` for `S-06`, `S-H2` |
| Draft loader fill | blue to violet with a sweeping light; see `C-DRAFT-LOADER` |

## `F-COLOR.contrast` Contrast floor

1. Text: 4.5:1 minimum, measured on the surface it sits on, including glass over ambient light (measure against the lightest and darkest the glass can get).
2. Control outlines and field borders: 3:1 (`#8C8C91` on white).
3. Disabled buttons are exempt from 4.5:1 but must stay legible: `#6B6B70` on `--rule2`.
4. White text on the gradient bands and the ink button passes at all stops listed above. If a hue pair changes, re-measure.

## `F-COLOR.raw` Raw values that are allowed

- White `#FFFFFF` for text on ink and on gradient bands.
- The tier ring stops and status triplets above (they are tokens in `tokens.json`).
- Per-card hue pairs listed in the component that owns them.
- Black `#000` only inside shadow rgba values.
