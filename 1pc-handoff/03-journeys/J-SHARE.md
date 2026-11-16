---
id: J-SHARE
title: Share a problem for the first time
rev: 1
status: baseline
source: reference/prototype/Landing.dc.html
depends_on: [S-01, S-02, S-04, S-04B, S-05, S-06, L-AUTH, L-DRAFT, L-HIDE, L-SORT, L-SIMILAR, L-SUBMIT]
last_delta: none
---

# J-SHARE: Share a problem for the first time

**Who:** any employee. **Starts:** "Share a problem" on Landing, Home, the sidebar, the phone Share tab, or the `P` key. **Ends:** the idea has a reference and the person is on its page knowing the next step and its date. **Target:** about two minutes; two screens after sign-in.

## `J-SHARE.steps` Steps

| # | Screen | The person | The system | Rules |
|---|---|---|---|---|
| 1 | `S-01` | Presses "Share a problem" | Remembers the intent; tries silent single sign-on | `L-AUTH.rules/1,4` |
| 2 | `S-02` (only if needed) | Signs in by single sign-on or email code | Returns them to the composer | `L-AUTH.states` |
| 3 | `S-04` | Lands with the cursor in the box. Types or speaks the problem in their own words | Saves as they go. From about 25 characters, starts the six parts; hides personal details before anything else sees the text | `L-DRAFT.parts`, `L-HIDE.rules` |
| 4 | `S-04` → `S-04B` | Sends the first message | The screen becomes the conversation; the loader runs; parts land one by one with their reasons; a receipt is posted | `C-DRAFT-LOADER`, `C-DRAFT-PANEL` |
| 5 | `S-04B` | Optionally adds details, changes a part, or shows a hidden detail with a reason | Re-runs only what changed; pins what the person changed | `L-DRAFT.pins`, `L-HIDE.rules/6` |
| 6 | `S-04B` | Presses "Move to Review" (enabled when the draft is ready and all six parts are in) | Slides forward | `L-DRAFT.parts/7` |
| 7 | `S-05` part 1 | Reads "Is this how you'd put it?"; fixes anything; "Looks right" | | |
| 8 | `S-05` part 2 | Confirms or changes the sorting | Records each field as confirmed or changed | `L-SORT.rules/2–3` |
| 9 | `S-05` part 3 | Looks at similar ideas; previews; keeps theirs separate or asks to merge | See `J-SIMILAR` | `L-SIMILAR`, `L-MERGE.request` |
| 10 | `S-05` parts 4 to 6 | Skips, or adds proof, a fix, who would help | Checks each file for personal details | `L-HIDE.files` |
| 11 | `S-05` part 7 | Reads the summary and the declaration; presses "Submit" | Creates the idea with its reference; starts "Checked and matched" and the 5-working-day clock | `L-SUBMIT.pre`, `L-SUBMIT.send` |
| 12 | `S-06` | Sees the reference, the stage track, "The review desk will look at it by …", and that they can edit or withdraw until a date | Draws the mark once in the header; notifies on Teams and email | `S-06.states` "Just shared" |

## `J-SHARE.variants` Variations

| Variation | Difference |
|---|---|
| From Home's prompt | Steps 3 and 4 merge: the words typed on Home arrive on `S-04B` as the first message |
| Already signed in | Steps 1 and 2 are skipped |
| By voice | Step 3 by speaking; the transcript is editable before sending (`L-DRAFT.voice`) |
| Interview (flag S1) | After the first message, up to three skippable questions, then the draft |
| Check first (flag S2) | With a close match, step 9 comes before step 7 |
| Phone | Same steps in the phone layouts (`S-04.phone`, `S-05.phone`) |

## `J-SHARE.accept` Acceptance

`V-ACC.share`.

## `J-SHARE.boards` Boards to walk on the canvas

`Landing`, `SignIn`, `Compose`, `ComposeResume`, `Review`, `Status`
