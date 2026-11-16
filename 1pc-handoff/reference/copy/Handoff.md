# Handoff: copy and controls per state

Generated from the prototype board `reference/prototype/Handoff.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Handoff.jpg`

Headings: H1: Say it, check it, send it.; H2: Handoff; H2: Three choices left open to test; H3: How should the draft be built?; H3: When should similar ideas be decided?; H3: Should the phone start with typing or speaking?; H2: Motion and recovery rules; H3: Motion; H3: Recovery; H2: What we can see now, and what needs testing; H3: Observable in the design; H3: Needs user testing; H2: Conflicts we ruled on, and lines that need an owner; H3: Conflicts in the base, and the ruling

### Text, top to bottom

```
1% Club redesign, 14 November 2026. Built from the v38 boards, which stay unchanged in their own artefact.
Say it, check it, send it.
An employee who notices something broken says it in their own words, from wherever they are, sees it become a clear draft that hides customer details, confirms it in one check, and from then on always knows where it stands and what to do next.
Before
Home
Describe it
Wait for the analysis, about 4.5s
Check the draft
Add detail
Fix in a line
Fix details
Status, after a 3.5s cover
After
Tell it: the draft forms as you type
Check it and send it: evidence and fix are optional, on the same screen
Status: reference and next step at once
Handoff
Status shows how each row was checked in round 3. Verified: the independent critic walked it on the board in that state, and the fixes were re-checked. Inspected: read in the markup and script, because a static board can't fully show it (scroll restore, screen-reader behaviour).
Screen or part
Friction before
Behaviour now
Checks
Status
Sign in
Sign-in dropped people on Home, so they had to find Share a problem again.
Silent sign-in goes straight to the composer. The screen appears only when sign-in fails or a session expires, and both return to the draft.
AC1, AC17
Verified
Home
A question from the review desk sat behind a nav badge. A saved draft reopened at step 1.
Needs you comes first: the top two from the Inbox, with All 3 in Inbox. Carry on reopens the draft where it was left, on any device. C opens the composer from any screen.
AC9, AC11
Verified
Pick up where you left off
A saved draft reopened at step 1, with files unclear.
Opens the composer on that draft, its photo listed and where it was last saved.
AC9
Verified
Compose
A scripted analysis held the draft for about 4.5 seconds. The 50-character minimum was never stated.
The draft forms beside the text after each pause, into fixed slots. The minimum is stated up front. A receipt says what was hidden, sorted and matched.
AC2, AC3, AC15
Verified
Customer details
The folio showed in clear while typing and was reported after the fact, with no undo.
The detail is marked in your text and hidden in the draft and in everything shared. Not personal? Show it, with a reason logged.
AC5
Verified
Similar ideas
Shown only on the status page, after the duplicate was sent.
A quiet line while drafting. On Check it, your idea page and a colleague’s idea: one Team up, a request with a note the lead reads, bringing yours along if you like. Or keep yours separate.
AC6
Verified
Review
Optional evidence cost a screen. The fix was typed twice. The declaration sat below the buttons.
One screen: check-answers, one explicit sorting confirmation, evidence inline, fix in a sheet, declaration pinned beside Submit.
AC2, AC4, AC7, AC8
Verified
Status
A 3.5-second cover hid the reference. No edit or withdraw. No reason for a decision.
Reference and next step show at once. Edit or withdraw until the review desk opens it. Its questions show as a card with an Answer button, each answer sits on its part, and the decision shows with its reason and the Ones Committee’s window. No appeals.
AC10, AC11, AC15
Verified
Edit after sharing
No way to change an idea once sent.
Edit opens the same check screen in edit mode: the reference, the deadline, Save changes and Cancel. After the desk opens it, edits become notes.
AC10
Verified
Conversation
A list of every thread, and a free-text box that took answers away from their parts.
No list: each idea has one conversation, opened from the idea or the Inbox. Questions show as a card with an Answer button; the answers post back as one message; the box below is for messages only.
AC11
Inspected
Inbox
The same waiting items in four lists: Inbox, Conversations, Needs you and Home. The side bar still said 2 unread after one was read.
The Inbox is the only list, and Needs you is its tab. Home shows the top two. The Needs you board is retired, and the side bar’s count follows the Inbox.
R27
Inspected
Answer
Questions could be answered on Answer, in Conversations or in the phone thread, and only Answer kept an answer with its part.
Answered only on Answer, desktop and phone. Each question names the part its answer goes to, and the answers post back into the conversation.
R27
Inspected
Decisions
The reviewer could ask but not decide, and the committee’s view and veto had no screen.
Decide on the reviewer’s idea page: Pick, Not now or Not picked, each with a reason the sharer reads at once. The Ones Committee sees each decision for 30 days, extendable to 3 months, then it expires; a reversal needs a note to the sharer.
R27
Inspected
Names
Ones Committee, the review desk and Meera Iyer, for the same reviewer.
The review desk everywhere; Meera from the review desk where she speaks; the Ones Committee only for its own window and reversals.
R27
Inspected
My ideas
No filters, drafts missing, Back always went to the Wall, and an appeals link the story dropped.
Filters with counts, including Drafts and Needs you. The filter, sort and scroll come back on Back. Scroll position is restored in the build; a static board can only show the filter and the highlighted row.
AC12
Inspected
Shell
Two headers, Share an idea, a Sign out button, phone links into desktop pages.
One header and one tab bar on every signed-in screen, including a phone Wall and a phone idea page. Phone screens link to phone screens.
AC13
Verified
Fields and focus
Field borders at 1.6:1. Sticky bars could hide a focused field.
Borders and hint text pass contrast. Scroll margins keep focus clear of the bars. Errors sit by the field and take focus. The P shortcut (P for problem) is ignored while typing and can be turned off. Needs an audit on the built screens.
AC8, AC14
Inspected
Failures
Upload failure, offline and submit failure were not drawn.
Each is drawn with plain words and one action. A draft is never lost.
AC17
Verified
Three choices left open to test
Each is a switch on its board. The default is our pick; the other option is worth an A/B test because a metric, not taste, should settle it.
S1, on Compose
How should the draft be built?
Default
Live draft beside the text
Test against
A short interview: up to three skippable questions, then the draft
Decided by
Draft completeness against time to submit and drop-off
S2, on Review
When should similar ideas be decided?
Default
Quiet nudge, decided on Review
Test against
Check first: a comparison before Review on a strong match
Decided by
Duplicates reaching the review desk against completion rate
S3, on Phone compose
Should the phone start with typing or speaking?
Default
Type first, with a large mic
Test against
Voice first, listening at once
Decided by
Phone completion and how often people correct the transcript
Motion and recovery rules
Motion
Nothing blocks input. Long moments play beside content, and any key, click or scroll finishes them.
What persists moves; it doesn't fade out and back. Shared names: composer, draft-card, submit-card, idea-id.
One timing scale: 120ms press, 160 to 220ms state change, 280 to 360ms entrance, 600ms or less for drawing.
Focus lands on the next action: the page heading after navigation, the trigger after a sheet closes.
A changed value gets one soft blue wash and one polite announcement.
Reduced motion swaps movement for a 120ms crossfade; the mark appears already drawn.
Recovery
Drafts save as you go, on the device and the account. Offline says so and keeps working.
A failed upload keeps its row with Retry and Remove. A file with customer details offers Hide it for me.
A failed submit returns to Review with the draft intact and Try again.
Withdraw confirms in place, offers Undo, and the idea can be restored later from My ideas.
After the review desk opens an idea, edits become notes, so nothing the desk read is overwritten.
Back after submitting goes to the idea's page, never to an editable form.
What we can see now, and what needs testing
Observable in the design
A problem-only share takes two screens after sign-in, down from four plus Home.
No wait before the draft can be checked; the 4.5-second analysis and the 3.5-second cover are gone.
Nothing is typed twice: the fix is entered once, in one place.
Similar ideas are offered before sending, not after.
Every signed-in screen uses the same header or tab bar.
Edit, withdraw, reply and the reason for a decision all have a home.
Needs user testing
Faster completion and fewer abandoned drafts.
Fewer duplicates reaching the review desk.
Better drafts: more with frequency, who it affects and rough size.
Trust in the pre-filled sorting, measured by how often people change it.
Whether voice first lifts completion on phone.
Whether people use email, Teams or, once it ships, the app to start drafts.
Conflicts we ruled on, and lines that need an owner
Conflicts in the base, and the ruling
Two headers in the base (journey screens against My ideas, Wall and the idea page). Ruled by the newer journey boards: one shell, and the action is Share a problem.
My ideas linked to appeals, which the story dropped. Ruled by the story: no appeals; the decision and its reason are shown instead.
Main.dc.html documents small-caps labels and arrow links; the latest boards removed both on the owner's direction. Ruled by the latest boards.
A separate 1% Club Design System proposal (molten glass, Geist) exists in your artefacts. The brief named the current artefact as the base, so its OFFER look was kept; its copy rules were checked (no 'duplicate', 'rejected' or 'already solved' in the product's own voice).
The tier colours on the Ones were kept: the base keeps them as part of the brand, so the critic's note to draw them in ink was declined.
Your 13 November decision has the review desk decide on the committee’s behalf, while the review asked for a committee veto. Ruled by both: the desk’s decision reaches the sharer at once, and the committee can reverse it within its window, with a note.
Promises that need sign-off before launch
Drafts are kept for 30 days, then archived, never deleted silently.
The review desk usually replies within a working day.
A withdrawn idea can be restored at any time.
The legal policy wording on idea ownership: KFintech owns what employees share, and the sharer keeps the credit. It is not shown in the flow.
The 1% Club email address and Teams bot (shown as placeholders), and the app’s launch date.
The Ones Committee’s window: 30 days, extendable 30 days at a time up to 3 months, then expired. Confirmed on 15 November; the sharer sees an extended date on the idea.
How this was made
Run as a team of agents in three rounds. The Product Lead set the arc and 17 checks. Three specialist pairs audited v38 in parallel. Four builders made the screens in parallel. An independent critic, who hadn't seen the work being made, walked the journeys; the builders then fixed its eight major findings.
Before: 2 checks passed, 10 partly, 5 failed. After round 3: no failures; two checks rest on inspection rather than a walk-through.
The app repo on your computer couldn't be opened from this session, so the story was taken from the artefact and recorded decisions.
Engineering capacity was treated as unlimited. Everyone shown is a synthetic demo person.
```

### Controls

| Element | Label | Attributes |
|---|---|---|
