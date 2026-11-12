# Spark tiers

A draft of how the system changes as a One's spark rises. It answers one question: when someone moves from "not yet a One" to Tier 7, what do they see change, and what must never change?

## The rule

One attribute does it. `data-tier="0"` to `"7"` on any element turns five dials for everything inside it. Nothing else in the markup or the CSS knows about tiers.

| | Tier 0 | 1 Spark | 2 Glow | 3 Flame | 4 Blaze | 5 White heat | 6 Blue flame | 7 Star |
|---|---|---|---|---|---|---|---|---|
| Who | Not yet a One | A One | | | | | | |
| Heat colour (`--heat`) | `spark` | `tier-1` | `tier-2` | `tier-3` | `tier-4` | `tier-5` | `tier-6` | `tier-7` |
| Core (`--heat-core`) | #ffe2c4 | #ffe2c4 | #ffd2c2 | #ffd0de | #ffc9c9 | #dcffec | #e8d6ff | #d6deff |
| Energy (`--energy`) | 0.25 | 0.35 | 0.45 | 0.55 | 0.70 | 0.80 | 0.90 | 1.00 |
| Soft lights behind the glass (`--lights`), plus one Electric | 1 | 1 | 2 | 2 | 3 | 3 | 4 | 4 |
| Glow radius (`--bloom`) | 12 px | 18 px | 26 px | 34 px | 44 px | 54 px | 64 px | 78 px |
| Foil (`--foil`) | none | 12% | 24% | 38% | 52% | 66% | 82% | 100% |
| What it feels like | One warm light in the room; calm glass | A number on a jersey, and it glows | A steady halo behind the number; a second light | The foil starts to catch the light | A third light; the glow reaches the glass around it | The glow lights the whole card | A fourth light; foil across the whole jersey | The widest glow, the fullest foil, the room at its warmest |

## What changes, component by component

| Component | What the tier changes | What it does not |
|---|---|---|
| Stage | On Zed, the colour of the warm light, and on `data-glow` stages how many lights drift and how fast. More lights spread wider; they never get brighter | The matte ground, the Electric light, the layout. The White stage is neutral at every tier |
| Header | A One gets a chip in the dock: a lit slash, "Tier 2" and their number in `heat-core` with a glow in the tier colour | The dock, the menu, the nav thumb (always white glass) |
| Button | The rim and glow of the **commit** button; the tip of the busy slashes | Primary and secondary stay Electric at every tier. A press never changes colour with status |
| Slashes (meter, stages, table, checks) | The lit tip of a filled slash and the glow of the current one | Filled is still ink at the base; empty is still a Steel outline |
| Field | The far end of the count line under a well | Borders, focus (always the focus colour), errors |
| Status, PausedBanner | Only the lit ring in an empty state and the tick's glow in the success pill | Error, amber and frost never take a tier colour |
| OneJersey | Everything: the number's colour, the glow from the collar and round the card, the bar, the swatch, and how much foil shows when it tilts | Name, brief and tier name stay White and Ash; the mesh |
| Hundred | The newest One's bead: colour and bloom | Every other bead is neutral at every tier |
| Dialog (the glow-up) | The number cross-fades from the old tier's colour to the new one's; the heat scale steps up; the light behind the sheet changes colour and spread | The story, the messages, the way out |
| OnesStrip | Each jersey carries its own tier; the band's light follows the tier of the One in front | The carousel, its buttons, its pace |

## Where a tier is allowed to show

| Surface | The viewer's own tier | Someone else's tier |
|---|---|---|
| Working screens (canvas, review desk, committee, console, admin, delivery) | The header chip, lit slash tips and the commit rim only. No moving light; the ground stays neutral grey. The work looks the same for everyone | Only as a jersey or the tier swatch beside a tier's name |
| Brand surfaces (home band, Wall, Ones pages, dashboard, office screen, launch) | Everything: the light in the room, glow, foil | Each jersey, bead and dialog sets its own `data-tier` |

This keeps the club's promise honest: a higher tier makes your own corner of the product warmer. It never makes anyone else's work harder to read, and it never moves a button.

## What never changes with tier

1. **Layout and words.** No component gains, loses or moves a part.
2. **Electric.** Pressable things are Electric at every tier. Heat is never a call to action.
3. **Contrast.** Glass on Zed is smoked so Ash and links hold 4.5:1 over the brightest tier's glow (Tier 5). The White stage carries no tier colour at all, so text on it is unaffected by tier.
4. **Small text.** A tier colour is light and fill, never words. A number in a chip is `heat-core`; a jersey number is large and runs from `heat-core` down to the tier colour.
5. **Reduced motion.** The light is drawn once and stands still; the tier is then colour and glow only.

## Open points for the product lead and brand

| # | Point | Why it matters | Proposal |
|---|---|---|---|
| 1 | **Tier 6 and Tier 7 fail as text.** `tier-6` is 3.6:1 and `tier-7` is 2.8:1 on Zed (the first proposal's token notes said 10.6:1 and 7.3:1, which was wrong; the notes are corrected) | BRAND.md shows a One's number in the tier colour. At the two highest tiers that number would be the hardest to read | Keep the brand colours exact; draw numbers as a gradient from a pale core to the tier colour (done here), and never set small text in a tier colour |
| 2 | **Tier 7 is the same blue as `electric-deep`** (#1e46d9) | On a white screen, Star-coloured light could be read as something to press | Heat never appears on or beside a control on white; the White stage carries no tier colour, so on working screens Star only ever appears inside the header chip and on lit slash tips |
| 3 | **Tier 5 is called White heat but is green** (#27d57f) | The name promises white; the screen shows green | Brand's call. If the green stays, nothing here needs to change |
| 4 | **How much should a tier show on working screens?** | This draft keeps it to the chip, slash tips and the commit rim | Confirm, or allow a faint tier-coloured light on a One's own My ideas page |
| 5 | **Does the tier change sound, haptics or the office screen?** | Not covered here | Out of scope for this draft |
