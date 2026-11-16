---
id: P-GAPS
title: Everything the canvas leaves open or does not draw
rev: 1
status: baseline
source: none
depends_on: []
last_delta: none
---

# Gaps: open questions and undrawn behaviour

Generated from every `OPEN:` and `NOT DRAWN:` line in the pack. Build the default each line gives. A later delta that settles one removes its marker.

## `P-GAPS.open` Open questions (22)

For the product owner. The numbered list with owners is `P-DECISIONS.open`.

| Module | Line |
|---|---|
| `P-PRODUCT` | A reviewer never reviews their own idea.  conflict-of-interest routing (who reviews a reviewer's idea) is not drawn; default: any other reviewer. |
| `P-ROUTES` | Screens without a phone board (`S-ONE`, `S-R1`, `S-R2`, `S-R4`, `S-H3`, `S-H4`, `S-H6`) must still work on a phone using `F-SPACE.breakpoints`. They were not drawn because their users work at a desk.  confirm whether the review side needs a designed phone layo… |
| `F-COLOR` | tier 6 is named "Blue flame" but its ring is violet, and tier 7 "Star" is blue. Confirm the name-to-colour pairing with the product owner before launch. Build what the table says. |
| `F-MOTION` | GSAP's standard licence is free for commercial use but is not open source. Legal to confirm before launch (owner: product). If not cleared, use the Web Animations API and a FLIP helper. |
| `F-SPACE` | the 641 to 1100px range is not drawn. The rules above are the default; each screen module lists its own stacking order under `layout` where it matters. |
| `C-CREW-DECK` | Phone: the card fills the screen; swipe left for the next, swipe up for the detail; "Team up" is a glass button at the bottom right that shrinks to an icon after first use.  `P-DECISIONS.open/8`. |
| `C-FILE` | Drop area. In the Home and Tell it prompt box: "Drop files or a folder here, or browse" with "PDF, Word, PowerPoint, Excel, Markdown, HTML, ZIP, images or a whole folder, up to 15 MB each." On Check it (Proof) and Edit: "Drop files here, or browse" with "Scree… |
| `C-TASKBAR` | the two screens show the same three steps in two styles. Default: build both as drawn; the product owner to choose one. |
| `S-05` | Buttons at the bottom right: "Cancel" and "Add my fix". Sending the sheet without answer 1: "Say how you'd solve it, or close this to send without a fix." After adding, the part shows "Included, 5 of 5 ready", the one-line fix and a size line ("70 to 150 hours… |
| `L-AUTH` | A first-time person gets an employee record created from the directory: name, initials, department ("area"), city, manager.  the directory source and field mapping are for IT (`P-DECISIONS.signoff/5`). |
| `L-DECIDE` | the admin screens for choosing a team and marking shipped are not drawn. Default: an admin API plus a minimal admin page. |
| `L-DRAFT` | **Language.** The draft is written in English whatever language the person used; their own words are kept as given, with the detected language recorded.  `P-DECISIONS.open/10`. |
| `L-DRAFT` | App / coming soon |
| `L-HIDE` | Customer name next to any of the above / "Name" / names are hard to detect reliably; default: hide a name only when it sits in the same sentence as another detected detail |
| `L-IMPACT` | the screen where a team enters a measurement and Finance confirms it is not drawn. Default: an admin form and API. |
| `L-LISTEN` | `L-LISTEN/6` Voice: one clear Indian English voice.  voice choice and provider. |
| `L-MERGE` | The Ones Committee sees the merge for 30 days and can reverse it (`L-COMMITTEE`, same window rules).  `P-DECISIONS.open/7`. |
| `L-ONES` | (`P-DECISIONS.open/9`) what earns points, the thresholds between tiers, and whether the leaderboard ranks by tier, impact or number are not specified by the design. Build tiers and points as values set by a rules table the programme team can edit, with an audi… |
| `L-SORT` | Routing: the area maps to a review queue.  the area-to-reviewer mapping is configuration owned by the review desk lead. |
| `L-WALL` | Sort (one at a time): **Popular** (most colleagues who opened the idea in the last 7 days), **Newest** (default; most recently shared), **Crew size** (largest crew), **Ones** (most Ones on the crew). Ties go to the newest.  `P-DECISIONS.open/5–6`. |
| `L-WALL` | The latest issue (issue number, month, headline, three numbered items, "Read this issue"), the next issue as "Coming soon", and a note that every issue is also emailed. Content is editorial.  authoring is outside draft 0; default: a simple content record per i… |
| `E-ENUMS` | Check it offers two kinds; the Wall shows three. Default: an idea shared as "A problem to fix" shows on the Wall as "Fix" once it includes a fix, else "Problem". Confirm with the product owner. |

## `P-GAPS.notdrawn` Behaviour the canvas does not draw (45)

Failure cases, busy states, limits and widths the build needs. Each line is the default.

| Module | Line |
|---|---|
| `C-BUTTON` | Busy:  label swaps to the action in progress ("Sending…") with a 12px spinner before it; the button keeps its width and ignores further clicks. |
| `C-CHIP` | Disabled / 50% opacity, not focusable |
| `C-DRAFT-LOADER` | the canvas shows a slow part but not a failed one. Defaults: |
| `C-FILE` | Uploading / a thin progress line in the row / Remove |
| `C-FILE` | "View" opens the checked file in a viewer pop-up (images inline, PDFs paged), built like `C-PREVIEW`. Hidden regions are blacked out in the stored copy of the file, not overlaid in the viewer. |
| `C-LISTEN` | the audio reads the summary and facts as the reviewer sees them, including answers once given; hidden details are spoken as "hidden". The sharer's raw words are not read. |
| `C-QCARD` | Partly answered / answered questions show a tick; the button reads "Carry on answering" |
| `S-04` | in the current structure. The phone board shows an earlier single-field layout: a compact bar ("Save and close", save status, "Step 1 of 3 Tell it", "Next: check it"), the question, a help line ("What happens, who it affects, how often. Any language. At least … |
| `S-05` | **Similar ideas** (`S-05.similar`). Heading "Has someone raised this already?" Line: "Two colleagues shared something close while you were writing. Team up with them, and bring yours along if you like, or keep yours separate." The grid (`C-SIMGRID.grid`): your… |
| `S-06B` | If the desk opens the idea while this screen is open, Save is refused: "The review desk has just opened it, so it can't be changed now. Your changes are kept below. Send them as a message instead." with "Open the conversation" (the unsaved text is carried into… |
| `S-07` | With the review desk / in this list; by the pattern of the other rows: "The review desk looks at it by Friday 20 November." / "See where it is" → `S-06` |
| `S-07` | Shipped / what was measured / "See what it changed" |
| `S-07` | Not now / the return date / "Read the decision" |
| `S-07` | Withdrawn / "Withdrawn on 12 November. It's back in your drafts." / "Restore it" |
| `S-09` | **Head**: status pill, title, reference, "Shared Monday 9 November by Ravi Nair, Investor service, Hyderabad" ( if the sharer hides their name on the Wall, the name is omitted: "Shared Monday 9 November, Investor service, Hyderabad"). |
| `S-H2B` | "Decline" opens an optional reason field in place before confirming ("Tell Kavya why, if you like") with "Decline the request" at the bottom right.  the field; the outcome text is drawn. |
| `S-H3` | With nothing arrived, the section reads "Nothing waiting. Anything you forward or message shows up here."  wording. |
| `S-H6` | Every switch saves at once and shows its new state; no Save button, no toast.  a failed save flips the switch back with a message under it: "Couldn't save that. Try again." |
| `S-H6` | The account menu (from the sidebar's account row) also holds: turn the `P` shortcut on or off, and "Sign out".  the menu itself; default: a small menu above the account row. |
| `S-ONE` | Number field: whole numbers 1 to 999. Taken: "No. 7 is taken. Free numbers near it: 6, 8, 11." Window closed: the field is replaced by "No. 1 is yours for good." (`V-FIELDS.one`; both  defaults.) |
| `S-R1` | A row opens `S-R2` with the grow-from-row hand-over. "Remind Divya" sends the reminder in place;  the button then reads "Reminded, just now" for that session. |
| `S-R2` | No phone board; on phone the panel follows the idea as a bottom sheet with the main button always visible.  default. |
| `S-R3` | Sending with nothing answered is not possible: the button is disabled and reads "Answer at least one question".   wording. |
| `S-R4` | Extend acts in place: the row updates to the new date with the "Extended" pill; the button then offers the next 30 days;  it is replaced by "At the 3-month limit" when no extension remains. |
| `S-WALL` | Title "Wall" and one line. **Kindling** as groups down the page (Just in, Picked, Being built, Shipped), each with a count and rows (title; "Problem, Investor service. <fact>"; chevron), under a sideways chip row for kind. The **Just in** group adds a sort cyc… |
| `L-AUTH` | Out of tries / expired / 3 wrong, or 10 minutes passed / "That code has run out. We've sent a new one." and a fresh code is sent automatically, once |
| `L-AUTH` | these three cases; the wording is the default. |
| `L-COMMITTEE` | A member cannot reverse a decision on their own idea.  default: the action is hidden for that member. |
| `L-CONVO` | `L-CONVO/10` Messages are not editable after sending.  default: a sender can delete their own message within 5 minutes; a deleted message leaves "Message removed". |
| `L-DECIDE` | Wording check: the product never tells a sharer their idea was a "duplicate", "rejected" or "already solved".  default: warn the reviewer if the reason contains those words and suggest plain alternatives; do not block. |
| `L-DRAFT` | One active editor at a time: opening a draft on a second device takes over; the first shows "This draft is open on your phone. Carry on here?"  wording is the default. |
| `L-DRAFT` | All parts fail / the words are saved. The panel says "We couldn't build the draft just now. Your words are saved. Try again." with a retry; the person can still fill parts by hand and move on |
| `L-DRAFT` | Save fails / status "Couldn't save. Trying again." with automatic retry and back-off; words stay on the device |
| `L-HIDE` | A reviewer who spots a missed detail can hide it from `S-R2` ( a "Hide this" action on any selected text; default: reviewers can flag text, which masks it at once and notifies the sharer). |
| `L-HIDE` | File limits: one configurable size limit per file and one configurable type list (`P-DECISIONS.open/12`: the boards state 15 MB in the prompt box and 25 MB on Check it). Types drawn: PDF, Word, PowerPoint, Excel, Markdown, HTML, ZIP, images; a folder uploads a… |
| `L-INBOX` | Ideas merged by the desk ( row text) / Both sharers / "merged your idea with Ravi's" / No / Open the idea |
| `L-INBOX` | Worth revised ( row text) / Sharer / "revised what your idea is worth" / No / Open the idea |
| `L-INBOX` | Answer reminder ( row text) / Sharer / "1 day left to answer Meera's questions" / Yes / "Answer the questions" |
| `L-LISTEN` | `L-LISTEN/7` If generation fails the player shows "Couldn't prepare the audio. Try again." and the rest of the page is unaffected ( default). |
| `L-MERGE` | a request unanswered after 3 working days: the sharer is offered "Send mine on its own" without waiting; the request stays open for the lead. |
| `L-NOTIFY` | `L-NOTIFY/3` Messages contain the idea title, what happened, any date, and a link into the app. They never contain hidden details, the person's raw words, or a decision's full reason: the reason is read in the app.  default. |
| `L-NOTIFY` | `L-NOTIFY/5` Reminders: for an open question set, 24 hours and 2 hours before the deadline, skipped if already answered. For a lead with a waiting request: once after 2 working days ( default). |
| `L-ONES` | Each One has an **impact brief**: one sentence shown on the Wall and the office screen. They can "Propose a new brief"; it goes live after the programme team approves it ( default). |
| `L-REVIEW` | An idea past decide-by is flagged to the review desk lead.  default: a daily digest to the lead; no automatic decision. |
| `L-TEAMUP` | Leaving a crew:  default: a member can leave from the idea's page; the lead can remove a member; both are logged and announced in the conversation. |
