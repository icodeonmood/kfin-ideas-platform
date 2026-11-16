---
id: V-ACC
title: Acceptance tests
rev: 1
status: baseline
source: reference/prototype/Handoff.dc.html
depends_on: [J-SHARE, J-RESUME, J-SIMILAR, J-TRACK, J-REVIEW, J-COMMITTEE, J-TEAMUP, J-RECOVER, J-BROWSE]
last_delta: none
---

# Acceptance tests

Each line is one test: given, when, then. Write them as end-to-end tests (the repo has a `.playwright-mcp` folder, so Playwright is probably in place) and keep the ID in the test name, for example `V-ACC.share/3`. A delta that changes behaviour names the tests it changes.

"AC n" in the last column is the original acceptance check from the design record that the test covers.

## `V-ACC.visual` Look and motion (every screen)

| # | Test | Covers |
|---|---|---|
| 1 | For every screen and every state listed in its module, a screenshot at 1440×(board height) and at 390×844 matches the reference in `reference/shots/` within a small tolerance (layout and colour; live text excluded). | |
| 2 | Every colour painted resolves to a token in `tokens.json` or a value listed in `F-COLOR.raw`. | |
| 3 | Only the radii in `F-SPACE.radius` are used. | |
| 4 | axe-core reports no violations on any screen in any listed state. | AC14 |
| 5 | Every interactive element is at least 44×44px or has a 44px hit area on touch. | AC14 |
| 6 | With `prefers-reduced-motion: reduce`, no element changes position or opacity over time after first paint, and no hand-over plays. | AC15 |
| 7 | Pressing any key or clicking during an arrival animation does not delay the action. | AC15 |
| 8 | No snackbar, toast or "Undo" message appears anywhere. | |
| 9 | Every message caused by a field appears directly under that field or group. | |
| 10 | The sidebar (desktop) and tab bar (phone) have the same items, order and current marker on every signed-in screen, and do not animate between screens. | AC13 |
| 11 | In every sheet and pop-up, focus moves inside on open, Escape closes it, and focus returns to the opener. | |
| 12 | The primary button of every view is at the bottom right (in the dock on phone); none is left-aligned or at the top. | |

## `V-ACC.share` Sharing (`J-SHARE`)

| # | Given | When | Then | Covers |
|---|---|---|---|---|
| 1 | A signed-out employee on Landing | They press "Share a problem" and single sign-on succeeds silently | They land on Tell it with focus in the box, without seeing the sign-in screen | AC1 |
| 2 | Same, single sign-on fails | They sign in with an email code | They land on Tell it, not on Home | AC1 |
| 3 | A signed-in employee on Home | They type a problem in the prompt and send | They land on the conversation with their words as the first message and the draft already building. The empty Tell it screen is never shown | |
| 4 | Words under 30 characters | They look at the draft panel | "Your draft needs a little more first." and "Move to Review" is disabled | |
| 5 | Words of 30 or more characters | The draft builds | The loader bar moves forward continuously, never pauses or moves back, stays under 97% until all six parts are in, then completes and folds away | |
| 6 | The similar-ideas part is three times slower than its mean | The draft builds | The loader line reads "still looking for similar ideas"; the other five parts are filled and editable meanwhile | AC3 |
| 7 | Words containing a folio number, a PAN and a phone number | The draft builds | The person's own text is unchanged; the draft, the receipt and everything another role can read show only "Folio ••••89", "PAN ••••4F", "Phone ••••10"; no service other than the detector received the raw values | AC5 |
| 8 | A hidden detail | They choose "Show it", pick a reason and confirm | It reads "Shown, because …"; the reason is logged; "Hide it" reverses it. Without a reason "Show it" stays disabled | AC5 |
| 9 | A suggested part | They change it by hand, then add another message | The changed part keeps their value and reads "Your call" | AC4 |
| 10 | A ready draft | They move to Check it, press "Looks right" on part 1 and "Confirm sorting" on part 2, and skip parts 4 to 6 | They reach Send without any extra click for the optional parts | AC2, AC7 |
| 11 | Sorting not confirmed | They press Submit | "Confirm the sorting first, or change any of it." appears with "Go to the sorting"; nothing is sent | AC8 |
| 12 | Sorting confirmed | They press Submit | An idea exists with a reference `IDEA-YYYY-NNNNNN`; they are on its page; the reference and "The review desk will look at it by <date 5 working days on>" are visible at once | AC10 |
| 13 | A just-shared idea | They press the browser's Back | They do not return to an editable form | |
| 14 | A problem-only share from a signed-in start | Counting screens | Two screens before the status: Tell it and Check it. Nothing was typed twice | AC2 |
| 15 | Flag S1 "Interview" on | They send the first message | Up to three skippable questions follow, then the draft builds once | |

## `V-ACC.resume` Resuming (`J-RESUME`)

| # | Given | When | Then | Covers |
|---|---|---|---|---|
| 1 | A draft started on a phone | They open the app on a laptop | The draft is listed under Drafts with "on your phone" and its time | AC9 |
| 2 | That draft | They open it | Messages, files, parts, pinned values, sorting and the step are as they were; "Picked up where you left off." | AC9 |
| 3 | A recent draft exists | They start "Share a problem" | They are offered "Continue that draft" or "Start a new one" | AC9 |
| 4 | Typing with the network off | They keep typing, then reconnect | The status reads "Unsaved, you're offline", then "Saved at …"; no text is lost | AC17 |
| 5 | The session expires while on Check it | They sign in again | They return to the same part of Check it with sorting and hidden details intact | AC9, AC17 |
| 6 | An email forwarded to the 1% Club address | They open the app | A draft exists marked "From your email …", with personal details already hidden; nothing was shared | |

## `V-ACC.similar` Similar ideas and merge requests (`J-SIMILAR`)

| # | Given | When | Then | Covers |
|---|---|---|---|---|
| 1 | A draft that closely matches a shared idea | They reach Check it part 3 | A grid three across shows their idea first ("Yours, not sent yet"), then the matches, closest first | AC6 |
| 2 | A match | They press "Preview" | A pop-up shows the other idea with one button, "Team up"; Escape closes it | AC6 |
| 3 | The team-up sheet from Check it | They choose "Ask Ravi to merge mine in" with a 30+ character note and send | The part reads "Waiting on Ravi to merge"; Submit is unavailable; "Withdraw the request" is offered | |
| 4 | A waiting merge request | Ravi chooses "Merge it" | Kavya sees "Merged into IDEA-…, with credit to you. Nothing else to send."; she is on Ravi's crew; her draft is closed | |
| 5 | A waiting merge request | Ravi declines with a reason | Kavya sees the reason and "Send mine on its own", which submits her idea normally | |
| 6 | A waiting merge request | Ravi chooses "Team up only" | Kavya is on Ravi's crew and can still send hers | |
| 7 | Any match | They choose "Keep mine separate" and submit | The reviewer's page says she kept hers separate | |
| 8 | A sharer | They try to merge without the lead's acceptance by any route (including the API) | It is refused | |

## `V-ACC.track` Tracking and answering (`J-TRACK`)

| # | Given | When | Then | Covers |
|---|---|---|---|---|
| 1 | A shared idea not yet opened by the desk, within 3 days | The sharer opens its page | Edit and Withdraw are offered with the closing date | AC10 |
| 2 | The desk opens the idea | The sharer's page updates | Edit and Withdraw are gone; the page says to write in the conversation | AC10 |
| 3 | The desk sends 3 questions with 3 days to answer | The sharer looks at Home, the Inbox, the idea and its conversation | Each shows the questions card with the same countdown and an "Answer the questions" button; none has a free-text answer box | AC11 |
| 4 | On Answer | They answer 1 of 3, skip 2, and send | "Send 1 answer to Meera" is the button; after sending, that answer shows under its part on the idea and as one message in the conversation; the other two stay open until the deadline | AC11 |
| 5 | An open question set | 24 hours and 2 hours before the deadline | A reminder is sent on the channels the person has on | |
| 6 | A decision of each kind | The sharer opens the idea | The pill, sentence, reason (word for word), dates and the committee line match `S-06.states` | AC11 |
| 7 | A withdrawn idea | They press "Restore it" | It is shared again with the same reference; the review clock restarts | |
| 8 | Any signed-in screen | Counting unread | The sidebar count, the tab-bar badge and the Inbox's unread number are equal, and drop together when an item is opened | |

## `V-ACC.review` Reviewing (`J-REVIEW`)

| # | Given | When | Then |
|---|---|---|---|
| 1 | A reviewer opens an idea for the first time | The page loads | The panel reads "Review this idea" with one button, "Decide on this idea"; "Ask Kavya first" is collapsed and marked Optional; no questions are queued |
| 2 | That page at 1440×900 | Measuring | The panel's top edge is level with the top of "Listen to the whole idea"; after scrolling, the panel sticks 96px from the top and its button stays visible |
| 3 | A panel taller than the window | Wheel over the panel | The panel scrolls; the page does not, until the panel reaches its end |
| 4 | Reviewing | They press "Decide on this idea", choose Pick, write a 30+ character reason and send | The sharer's page shows "Picked" and the reason at once; a 30-day committee window is open; the idea is under "Decided this week" |
| 5 | Deciding with nothing asked | They press "Back" | The panel returns to "Review this idea" |
| 6 | Reviewing | They press "Ask about this" on a part | The Ask section opens with that part's suggestion queued; the bar shows "Decide without asking" and "Send 1 question to Kavya" |
| 7 | Questions queued | They send with "3 days" | The idea is under "Waiting on the sharer" with "0 of 3 answered" and a countdown; the sharer is notified |
| 8 | Answers in | They open the idea | Each answer is under its part with who and when; the panel reads "All 3 answered" |
| 9 | A decision with no choice, or a reason under 30 characters | They press send | "Choose Pick, Not now or Not picked first." / "Give Kavya a reason of at least a line, 30 characters or more."; nothing is sent |
| 10 | "Revise what it's worth" | They change the hours and save with a note | The reviewer's tile shows the new figure and "was …"; the sharer's page shows both figures and the note; the sharer gets an Inbox item |
| 11 | A similar idea | They press "Preview" | The pop-up shows a comparison with the idea under review and one button, "Merge" |
| 12 | The merge sheet | They send with a note under 20 characters | "Tell both why, in a line or two."; nothing is merged |
| 13 | The merge sheet, defaults | They press "Merge and tell both" | The earlier idea leads; the other is marked merged and points to it; both sharers are credited and told; the other sharer is on the lead's crew; the card shows the green banner |
| 14 | A reviewer who is also the sharer | They open their own idea on the desk | They cannot ask, revise, decide or merge |
| 15 | The listen player | They press play, change speed, jump to a part, and save for offline | Audio plays from the chosen part at the chosen speed; the time and the current part update; the button reads "Saved for offline" |

## `V-ACC.committee` Ones Committee (`J-COMMITTEE`)

| # | Given | When | Then |
|---|---|---|---|
| 1 | A decision 5 days old | A member opens "In the window" | It is listed with the reviewer's reason and "25 days left" |
| 2 | An open window | They extend | The end date moves 30 days; "Extended once"; the sharer's page shows the new date |
| 3 | A window extended to 3 months | They look at the row | No further extension is offered |
| 4 | An open window | They reverse with a 30+ character note | The idea takes the new decision; the sharer's page shows the committee's card and "This is final."; the row is under "Reversed"; no further reversal or extension is possible |
| 5 | An open window with nothing done | The end date passes | The row is under "Expired" and the decision stands |
| 6 | Reversing | No choice, or a short note | "Choose what to change it to." / "Write a note of at least a line, 30 characters or more." |

## `V-ACC.teamup` Team up (`J-TEAMUP`)

| # | Given | When | Then |
|---|---|---|---|
| 1 | The team-up sheet | It opens | The note is pre-filled; "Bring your ideas along" is collapsed and reads "None picked"; there is one button, "Send to Ravi", and a close cross; no "Cancel" |
| 2 | The note under 30 characters | They look at the sheet | The hint is the warning; the button is disabled; clicking it focuses the note |
| 3 | The dropdown open | They tick two ideas | The field reads "2 ideas picked"; the privacy line ends "and the ideas you bring." |
| 4 | A sent request | They look at the card | "Waiting for Ravi" with Withdraw; the same on every screen that shows that idea |
| 5 | Ravi's Inbox | He opens the request | Her note, any idea brought, and three answers in the order Decline, Team up only, Merge it |
| 6 | Each of Ravi's answers | He chooses it | The result text matches `S-H2B.states`; Kavya's Inbox gets the matching item; no Undo is offered |
| 7 | Find your crew, desktop | They press Next | The front card lifts out to the right and tucks behind the pile; it does not slide sideways |
| 8 | Find your crew | They pass every card | "That's everyone for now" with counts, "See them again" and "Undo last pass" |
| 9 | Home's Ones, pointer over the cards | Wheel down, then up | One card forward, then one back, per wheel step; at the last card the page scrolls on |

## `V-ACC.recover` Failures (`J-RECOVER`)

One test per row of `J-RECOVER`: reproduce the failure and check the exact message, the offered action and that nothing typed or attached is lost. Covers AC17.

## `V-ACC.browse` Lists and return (`J-BROWSE`)

| # | Given | When | Then | Covers |
|---|---|---|---|---|
| 1 | My ideas with a tab, filter, sort and search set, scrolled | They open a row and press Back | The same tab, filter, sort, search and scroll position; the opened row is highlighted and focused | AC12 |
| 2 | A sort change on My ideas, the Review desk or Just in | They choose another sort | Rows glide to their new order; the choice is in the URL | |
| 3 | The Wall's Just in with 12 ideas | They load the Wall | 5 rows and "Show 5 more"; then 10 and "Show 2 more"; then 12 and "Show fewer" | |
| 4 | Just in | They choose each sort | Popular orders by "Opened this week", Newest by "Shared", Crew size by "Crew", Ones by "Ones"; ties go to the newest; the sorted column is emphasised | |
| 5 | The Wall's impact tiles at 1440, 1100 and 390 wide | Measuring | All four tiles have the same height; no number wraps; the unit is in the label under the number | |
| 6 | A kind chip on the Wall | They choose "Problems" | Kindling and Just in both show only problems; the counts follow | |
