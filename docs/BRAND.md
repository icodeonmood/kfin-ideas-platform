# 1% Club brand rules

For: engineers and designers building anything employees see. The full brand book (thinking, identity, examples) is the design canvas at claude.ai/artifact/VzS7DU6PoJPJo8zazkA5yv. Decisions behind each rule are DEC-027 to DEC-052 in `docs/DECISIONS.md`. When this file and the canvas disagree, this file wins for the app.

## 1. Name and words

| Rule | Detail |
|---|---|
| Name | **1% Club** on every screen, email, page title and poster (DEC-030). Written with the numeral and the % sign, never "One Percent Club" |
| Internal only | "The Garage" is the project's internal name. It never appears to employees (DEC-035). Code, repo and internal docs keep their names |
| Endorsement | "A KFintech programme" in the footer, emails and certificates. No KFintech logo (DEC-036) |
| The inducted | **Ones**. "New Ones", "You're No. 17." (DEC-034). Everyone else is "you" |
| Numbers | Jersey numbers 1 to 999, shown as "No. 17", no leading zeros (DEC-039) |
| Stages | **Picked**, **Being built**, **Shipped**. A match to a solution that already runs: **Already running** (DEC-038) |
| Other platform words | canvas, Find your crew, review desk, 1% Club core committee |
| Never on screen | Garage, duplicate, rejected, already solved |
| Language | English only at launch (DEC-048) |

### Lines (DEC-027)

| Line | Use it for |
|---|---|
| 1% spark. 99% sweat. | The tagline. Wordmark lockups, launch screen, certificate |
| Every hundred has a one. | The idea behind the mark. Manifesto, induction call |
| You don't apply. You build your way in. | When someone asks how to join |
| You bring the spark. | Launch posters and the first email |
| Ideas compound. | Results and numbers |

Voice: like a colleague who has seen everything and still believes in you. Short, specific, a little wry, never grand. "You're No. 17." not "Congratulations on your selection into the prestigious 1% Club!" All message wording still goes to HR for sign-off.

## 2. Colour (DEC-028)

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--zed` | `#0A0A0C` | Brand surfaces: header, wall hero, club pages, launch page. Text on white | White on it 19.7:1 |
| `--white` | `#FFFFFF` | Working screens (canvas, My ideas, review desk, admin). Text on Zed | |
| `--electric` | `#2B5BFF` | Only things you can press: buttons, links, focus rings | White on it 5.2:1; on white 5.2:1; on Zed only at 24 px and up (3.8:1) |
| `--spark` | `#FF5B14` | The outlier. Once per screen, only on "the one": the mark's spark, a One's number or badge | On Zed 6.4:1; Zed text on it 6.4:1. Never text on white |
| `--graphite` | `#17181C` | Raised surfaces on Zed | |
| `--ash` | `#9EA3AD` | Secondary text on Zed | 7.8:1 on Zed. Not on white |
| `--slate` | `#5C6270` | Secondary text on white | 6.1:1 on white |
| `--line-dark` | `#2A2C33` | Borders on Zed | Decorative only |
| `--line-light` | `#DCDFE5` | Borders on white | Decorative only |

Theme (DEC-031): one theme. Working screens are white with Zed text; the header, the wall, club pages and the launch page are Zed with white text. No dark-mode switch on day one.

## 3. Type

Geist for everything, self-hosted (SIL Open Font License); Geist Mono only for jersey numbers and the compounding line. Headlines ExtraBold (800) with tight tracking (−0.03 to −0.05 em); section headings SemiBold (600); body Regular 16–17 px, line height 1.5. No all-caps labels, except the name on the back of a jersey t-shirt.

## 4. The mark: Spark (DEC-029, DEC-052)

The % sign with its slash drawn as a rising spark and an ember: a one between two zeros. It is the final logo for now.

**Master geometry** (viewBox `0 0 200 240`; files in `apps/web/public/brand/`):

| Part | Geometry | Colour |
|---|---|---|
| Upper zero | circle cx 52, cy 58, r 34, stroke 12, no fill | White on Zed, Zed on white |
| Lower zero | circle cx 148, cy 184, r 34, stroke 12, no fill | Same as upper zero |
| Spark | polygon 34,236 146.9,27.2 169.1,40.8 | Spark |
| Ember | circle cx 171.6, cy 11.8, r 7 | Spark |

**Small sizes (below 32 px tall):** use `spark-mark-small-*.svg`. The zeros are r 32 with stroke 24, the spark is polygon `34,236 141,23.5 175,44.5`, and there is no ember. Smallest use: 14 px tall.

**Clear space:** the height of one zero (80 units at master size, a third of the mark's height) on every side.

**Wordmark:** "1% Club" in Geist ExtraBold, tracking −0.04 em. Lockup: mark to the left, its height equal to 1.4× the wordmark's cap height, with a gap of half the mark's width.

**Don't:** recolour the zeros orange or the spark blue; rotate or flip the mark; add shadows, glows or gradients; place it on photos without a Zed panel; put the Spark colour on Electric; redraw the spark at a different angle (members' own sparks are the only variation, below).

**Member sparks:** each One gets a spark of their own, generated from their permanent induction record, never from personal data. Used on the pin, certificate and constellation wall. Their angle varies from 38° to 71°, along with their length and where the ember sits.

## 4a. Spark tiers (DEC-075, DEC-080 to DEC-083)

Only Ones have a tier. The spark is lit at Tier 1 on induction, and the committee moves it up or down through the console (propose, approve, carry out). The colours are DEC-098's; the names and order are unchanged.

| Tier | Name | Colour |
|---|---|---|
| 1 | Spark | `#FF7F14` |
| 2 | Glow | `#FF4313` |
| 3 | Flame | `#FF2E6B` |
| 4 | Blaze | `#FF0000` |
| 5 | White heat | `#27D57F` |
| 6 | Blue flame | `#8C2FF1` |
| 7 | Star | `#1E46D9` |

A tier colour is light and fill only, never small text: the One's spark, badge, swatch and dashboard accent. A One's number is drawn from a pale core (`heat-core`) to the tier colour, because Tiers 6 and 7 fail as text on Zed (Star is about 2.8:1). In email the number stays white and the tier shows as a filled swatch beside its name. On white screens, a tier colour never sits beside an error, a success mark or a control, so Blaze is not read as an error, White heat as success or Star as something to press. The Spark mark (logo) keeps `#FF5B14` whatever anyone's tier.

A tier change sends the One an email from the 1% Club sender, on behalf of the committee and the CEO. The first time they sign in afterwards, the glow-up plays once (DEC-084): the spark heats from the old colour to the new one, then their story and messages appear. With reduced motion, the end state shows at once.

## 4b. Email (DEC-061, BLD-125)

Every email has a plain-text part and a branded HTML part. HTML: 600 px wide, built from tables, Arial, light colours inline (what Outlook desktop shows) and a dark version for mail apps set to dark. A Zed header band carries the Spark mark as a hosted PNG (`/brand/email-mark-white@2x.png`, shown at 20 x 24; never SVG in email) and "1% Club". One Electric button per email, the first link the template puts on its own line. The One's number sits in a Zed block with its tier swatch. The footer always reads "1% spark. 99% sweat." and "A KFintech programme". No tracking pixels, no web fonts. Links on dark use #7C9BFF, since Electric is too dark to read on Graphite. Wording comes from the templates and HR reviews it; the renderer never changes words.

## 5. Motion and sound

One orchestrated moment: the **logo introduction** on the launch screen (DEC-046). It plays like this:

| Time | What happens |
|---|---|
| 0:00 | Black screen |
| 0:04 | The spark rises from bottom left to top right |
| 0:08 | The two zeros arrive |
| 0:14 | "1% Club", then the tagline |
| 0:30 | QR code and "You bring the spark." |

Everywhere else, motion only answers what a person does. `prefers-reduced-motion` gets the final frame with no animation.

**Sound (DEC-050):** the logo introduction has a sound signature. It is a single bell tone, then a soft spark crackle as the spark rises, synthesised in the browser (no audio files). It plays only after the operator presses Start. Every other screen is silent.

## 6. Objects (DEC-047, DEC-049)

| Object | Spec |
|---|---|
| Orange lanyard | Spark colour, "1% Club" and the number in Zed |
| Pin | Steel, with the One's own spark in orange enamel and the number on the back |
| Jersey t-shirt | Zed. The back has the name or nickname the One chooses (HR checks it), then the number in white with a short orange bar under it. The chest has the mark |
| Laptop skin | Zed, with the % at full size cropped by the edge |
| Laptop bag | Zed, with the mark embossed black on black and an orange zip pull |
| Constellation wall | A Zed wall in the new office. Each One's spark is added on induction |

## 7. Accessibility

WCAG 2.1 AA everywhere (non-negotiable 10). Use only the colour pairings with contrast listed in section 2. Spark and Electric are never the only signal: a stage, state or selection always has words too.
