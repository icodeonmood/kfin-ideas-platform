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

**Superseded for the app by the design pack (DEC-102).** The interface colours, tier colours, type, radii and motion now come from `1pc-handoff/01-foundations/` (`tokens.json`, `F-COLOR`), imported as `apps/web/src/app/tokens.css`. The table below is kept as the brand's history; where it differs, the pack wins. The spark is `#F46835`.

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--zed` | `#0A0A0C` | Brand surfaces: header, wall hero, club pages, launch page. Text on white | White on it 19.7:1 |
| `--white` | `#FFFFFF` | Working screens (canvas, My ideas, review desk, admin). Text on Zed | |
| `--electric` | `#2B5BFF` | Only things you can press: buttons, links, focus rings | White on it 5.2:1; on white 5.2:1; on Zed only at 24 px and up (3.8:1) |
| `--spark` | `#FF5B14` | The outlier. Once per screen, only on "the one": the mark's spark. A One's number and badge take their tier colour (§4a, DEC-098) | On Zed 6.4:1; Zed text on it 6.4:1. Never text on white |
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

Only Ones have a tier. The colours are the design pack's (`F-COLOR.tiers`, DEC-102, conditioned to 87% chroma), and the names and order are unchanged. Each tier also has a conic ring (`--tier-N-ring` in `tokens.css`) drawn round the avatar. `services/worker/ones/tiers.py` and `tokens.css` hold the same values and change together.

| Tier | Name | Colour |
|---|---|---|
| 1 | Spark | `#F5863B` |
| 2 | Glow | `#F35532` |
| 3 | Flame | `#F34770` |
| 4 | Blaze | `#F23729` |
| 5 | White heat | `#4DD187` |
| 6 | Blue flame | `#8841E1` |
| 7 | Star | `#264DC9` |

A tier colour is light and fill only, never small text: the One's spark, badge, swatch and dashboard accent. A One's number is drawn from a pale core (`heat-core`) to the tier colour, because Tiers 6 and 7 fail as text on Zed (Star is about 2.8:1). In email the number stays white and the tier shows as a filled swatch beside its name. On white screens, a tier colour never sits beside an error, a success mark or a control, so Blaze is not read as an error, White heat as success or Star as something to press. The Spark mark (logo) keeps `#F46835` whatever anyone's tier.

A tier change sends the One an email from the 1% Club sender, on behalf of the committee and the CEO. The first time they sign in afterwards, the glow-up plays once (DEC-084): the spark heats from the old colour to the new one, then their story and messages appear. With reduced motion, the end state shows at once.

## 4b. Email (DEC-061, BLD-125; OFFER look DEC-101, BLD-A170)

Every email has a plain-text part and a branded HTML part. HTML: 600 px wide, built from tables, light colours inline (what Outlook desktop shows) and a dark version for mail apps set to dark. The values come from lane D's OFFER boards.

| Part | Light | Dark mode |
|---|---|---|
| Page | Paper `#F3F3F1` | `#111111` |
| Header | The Spark mark (hosted PNG, `/brand/email-mark-ink@2x.png`, shown at 22 x 26; never SVG in email), then "1% Club" in ink, weight 600, letter-spacing -0.03em. No band | The white mark (`email-mark-white@2x.png`), white name. Outlook desktop never gets the white copy |
| Card | White, 1px `#E4E4E0` border, radius 16, padding 32. The subject is the headline | `#1A1A1E`, border `#2C2C30` |
| Text | Ink `#111111`, 16 px, line height 1.6; muted `#5F5F64` | White; muted `#A3A3A6` |
| Button | One per email, the first link the template puts on its own line: black `#111111`, white words, radius 10, padding 14 x 22 | White, ink words |
| Links | Inline links ink and underlined. Further links on their own line: ink, weight 600, no underline, ending in an arrow. Blue `#3355FF` is never a link colour in email | White |
| The One's number | A dark panel (`#111111`, radius 16, padding 24) in both themes: the tier as a 24 x 4 dash in its colour (DEC-098, fill only), the tier in small capitals in `#A3A3A6`, the number in white at 64 px, then "Your number" | Same |
| Footer | A `#E9E9E6` band with a `#DADAD6` top rule: "1% Club" in ink, "1% spark. 99% sweat." and "A KFintech programme", 13 px muted | `#161619`, rule `#2C2C30` |

Type: Inter where the mail app has it, else Arial (`Inter, Arial, Helvetica, sans-serif`); headlines and the wordmark use `'Inter Tight', Inter, Arial, sans-serif` at 600. No web fonts are loaded and there are no tracking pixels. Every text pair passes AA, and the email tests compute each one. Wording comes from the templates and HR reviews it; the renderer never changes words.

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
