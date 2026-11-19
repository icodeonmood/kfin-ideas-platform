# New wording on the Inbox, messages and lane A's screens, for HR's sign-off (lane A)

Written Wednesday 18 Nov 2026 for HR's review of launch-facing copy (SHIP_PLAN §8), to be signed off before Thursday's 17:00 go/no-go. Lane A builds the Landing page, sign-in, "Share another way", "How it works", the Inbox, the two office screens (launch and office display) and the admin page, and the messages the platform sends (the Inbox items and their emails). Everything else on these screens is the design pack's own copy (`1pc-handoff/reference/copy/` and the boards), used as it stands. These are the lines lane A changed for the product lead's decision of 18 Nov, the message templates still waiting for HR, and the places where no line is drawn. In the templates, words in braces change with each case: `{left}` is "1 day" or "2 hours", `{title}` the idea's title, `{First}` a first name.

## 1. Lines changed by the product lead's decision (DEC-111, 18 Nov): the review desk, never a reviewer's name

The product lead decided on 18 Nov that a sharer, a crew member or anyone outside the review desk and the Ones Committee never sees the name of the person at the review desk. Wherever a reviewer was named, the line now says "the review desk", with the 1% mark in place of the person's initials. The boards' "Meera from the review desk" is the demo reviewer. HR is asked to sign off each new line.

| Where | Was | Now | Why |
|---|---|---|---|
| The Inbox, the sender of the review desk's questions (row, reader and the email's first line) | Meera from the review desk asked you 3 questions | The review desk asked you 3 questions | DEC-111. The same sender for every desk item below (BLD-A221; changed by both lanes, lane B's BLD-B257 with the same words) |
| The Inbox, the sender of a decision | Meera from the review desk picked your idea / didn’t pick your idea, with a reason / said Not now to your idea, with a date it comes back | The review desk picked your idea / didn’t pick your idea, with a reason / said Not now to your idea, with a date it comes back | DEC-111 (BLD-A221; changed by both lanes, lane B's BLD-B257 with the same words) |
| The Inbox, the sender when the desk merges two ideas | Meera from the review desk merged your idea with Ravi’s | The review desk merged your idea with Ravi’s | DEC-111. "Ravi’s" is the other sharer, not a reviewer, and stays (BLD-A221; changed by both lanes, lane B's BLD-B257 with the same words) |
| The Inbox, the sender when the desk revises what an idea is worth | Meera from the review desk revised what your idea is worth | The review desk revised what your idea is worth | DEC-111 (BLD-A221; changed by both lanes, lane B's BLD-B257 with the same words) |
| The emails for the four items above, their subject line | Meera from the review desk asked you 3 questions / Meera from the review desk merged your idea / Meera from the review desk revised what your idea is worth | The review desk asked you 3 questions / The review desk merged your idea / The review desk revised what your idea is worth | DEC-111. The decision email's subject, "A decision on your idea", names no one and is unchanged (BLD-A221; changed by both lanes, lane B's BLD-B257 with the same words) |
| The Inbox, the answer reminder (row, title, email subject and the email's first line; template 1.1) | 1 day left to answer Meera’s questions | 1 day left to answer the review desk’s questions | DEC-111. The board's line (NOT DRAWN default) names the reviewer (BLD-A222; changed by both lanes, lane B's BLD-B257 with the same words) |
| The Inbox, the sender of an answer reminder, timed or sent by a reviewer by hand ("Send a reminder") | Meera Iyer 1 day left to answer … (by hand: the reviewer's full name) / 1% Club 1 day left to answer … (timed) | The review desk 1 day left to answer the review desk’s questions | DEC-111. Lane B's final wording (BLD-B257): every reminder comes from the review desk as a whole. Lane A's branch had "1% Club" for both; lane B's choice stands once both land (BLD-A221) |
| The Inbox and its email, a comment or a mention a reviewer writes in the conversation as the desk (not on the build team) | Meera Iyer commented on your idea / Meera Iyer mentioned you | The review desk commented on your idea / The review desk mentioned you | DEC-111. A crew member, or a reviewer on the build team, is still named (BLD-A221, with lane F; lane A only) |
| The email when the review desk asks a question (template `question` 1.2), the sign-off | {Reviewer's full name}, review desk, 1% Club | The review desk, 1% Club | DEC-111 (BLD-A222; changed by both lanes, lane B's BLD-B257 with the same words) |
| The same email, its opening | I'm reviewing your idea "{title}" and have one question: | We're reviewing your idea "{title}" and have one question: | The desk now writes as a whole, so "I" becomes "we", as the rest of the email already says ("If we don't hear back") (BLD-A222; lane A only) |
| The email when an idea is pointed to another team (template `redirected` 1.3), the sign-off | {Reviewer's full name}, review desk, 1% Club | The review desk, 1% Club | DEC-111 (BLD-A222; changed by both lanes, lane B's BLD-B257 with the same words) |
| The email when an idea has been reviewed (template `reviewed` 1.4), the sign-off | {Reviewer's full name}, review desk, 1% Club | The review desk, 1% Club | DEC-111. "Note from the reviewer:" names no one and stays (BLD-A222; changed by both lanes, lane B's BLD-B257 with the same words) |

HR may also want one sign-off for the desk everywhere: the committee-era email `gate-outcome` signs "The 1% Club review desk", and the three emails above now sign "The review desk, 1% Club". Lane A has left `gate-outcome` as it is.

## 2. Lane A's other message templates still waiting for HR

Each is in `comms/templates/` with `hr_signed_off: false`. The Inbox shows each item as "{sender} {line}"; the reader adds the heading and the note; the email opens with the same sentence. Senders: the review desk as a whole (section 1), a person by full name, a Ones Committee member as "{Full name} from the Ones Committee", or "1% Club".

| Template (version) | Heading / line / note | Email subject | Why HR is asked |
|---|---|---|---|
| `inbox/questions` (1.0) | Questions from the review desk / asked you 3 questions / Answer by Thursday 19 November, 6 pm. | The review desk asked you 3 questions | Row text is the pack's; the email wording is a draft (BLD-A200, BLD-A201) |
| `inbox/decision` (1.1) | Decision / picked your idea, didn’t pick your idea, with a reason, said Not now to your idea, with a date it comes back / The reason is on your idea’s page. | A decision on your idea | The Not now line and the email are drafts; 1.1 uses ’ throughout (BLD-A195) |
| `inbox/decision_reversed` (1.1) | Decision reversed / reversed a decision on your idea (to the reviewer who decided: reversed your decision on this idea) / The Ones Committee’s note and the new decision are on the idea’s page. This is final. | The Ones Committee reversed a decision | The reviewer's line and the email are drafts (BLD-A195) |
| `inbox/desk_merge` (1.1) | Ideas merged by the desk / merged your idea with Ravi’s / Both of you are credited, and you’re on one crew now. | The review desk merged your idea | Row text is a NOT DRAWN default; email draft (BLD-A195) |
| `inbox/worth_revised` (1.1) | Worth revised / revised what your idea is worth / The new figure and the review desk’s note are on your idea’s page. | The review desk revised what your idea is worth | Row text is a NOT DRAWN default; email draft (BLD-A195) |
| `inbox/answer_reminder` (1.1) | Answer reminder / 1 day left to answer the review desk’s questions / Answer by Thursday 19 November, 6 pm. | 1 day left to answer the review desk’s questions | Changed in section 1; the email is a draft (BLD-A222, BLD-A199) |
| `inbox/sent_to_desk` (1.0) | Sent to the review desk / sent your idea to the review desk / The review desk will look at it by Monday 23 November. | Your idea is with the review desk | Email draft (BLD-A200) |
| `inbox/detail_hidden_by_desk` (1.0) | A detail was hidden / hid a customer’s detail in your idea / Only you can still see it. | A detail was hidden in your idea | Lane A's draft, agreed with lane C; sent by the review desk as a whole (BLD-A205) |
| `inbox/teamup_request` (1.1) | Merge request, or Team-up request / asks to team up and merge their idea into yours (their ideas, for two or more), or asks to team up | {Full name} asks to team up on your idea | "their" for the board's "her" (BLD-E008); "asks to team up" for a team-up only request; the email (BLD-A195, BLD-A207) |
| `inbox/teamup_answer` (1.2) | Request answered / approved your team-up request, declined your team-up request, with a reason, or declined your team-up request / You’re on {First}’s crew now., or The reason is in the app, with your request. A lead who hid their name or has left shows as "The lead" | {Full name} answered your team-up request | The declined lines and "The lead" are NOT DRAWN (lane F's words, BLD-F029); the email (BLD-A196) |
| `inbox/crew_joined` (1.0) | Joined your crew / joined your crew | {Full name} joined your crew | Email draft (BLD-A200) |
| `inbox/build_ask` (1.0) | A build team asks / asked you to check new messages / Please look by Thursday 19 November, 6 pm. | {Full name} asked you to check new messages | Email draft (BLD-A200) |
| `inbox/mention` (1.0) | Mention / mentioned you | {Full name} mentioned you | Email draft (BLD-A200) |
| `inbox/comment` (1.0) | Comment on your idea / commented on your idea | {Full name} commented on your idea | Email draft (BLD-A200) |
| `inbox/stage_moved` (1.0) | Stage moved / moved your idea to Being built | Your idea moved to Being built | Email draft (BLD-A200) |
| `inbox/draft_kept` (1.1) | Draft kept / kept your draft from your phone (from email, from Teams; with no place, kept your draft) / Pick up where you left off. | Your draft is saved | The plain line with no place is ours; the email (BLD-A188) |
| `desk/decide-by-digest` (1.0) | (an email only, to the review desk) | Past the decide-by date: 3 ideas still with the review desk | NOT DRAWN default (L-REVIEW.clock/3); switched off at launch (BLD-A203) |

## 3. Lines lane A's screens show that the boards do not draw

| Where | Wording | Why |
|---|---|---|
| Share another way (S-H3), the "Arrived from elsewhere" part with nothing in it | Nothing waiting. Anything you forward or message shows up here. | The pack's written default (S-H3/3, NOT DRAWN). Email and Teams are off at launch, so the part is not shown yet (BLD-A192) |
| Sign-in by email code (S-02), a code that ran out before a new one could be sent | That code has run out. Ask for a new one when the countdown ends. | Not drawn. Sign-in by email code is off at launch; only InfoSec switches it on (BLD-A175) |
| Sign-in (S-02), "Sign in again to carry on", for a draft last saved on another device | Draft, saved 9:41 am on your phone (or: on your laptop) | Not drawn: the boards draw only "on this laptop" / "on this phone" for the same device. "On your phone" is the pack's own words on Home and Tell it (BLD-A227) |
| The Inbox (S-H5), when it cannot be loaded | We can't load your Inbox just now. Please try again in a minute. | Not drawn; shown instead of "Nothing here.", which would be wrong (BLD-A195) |
| The Inbox, the row text for a desk merge, a revised worth and an answer reminder | See section 2 | The pack marks these three rows NOT DRAWN and gives the defaults used there (L-INBOX.kinds) |
| The admin page (`/admin`), its headings, hints and messages | The page's own staff-facing lines | The pack leaves the admin screens undrawn (L-DECIDE.after, L-IMPACT/8). Only the programme team sees them, so they are listed for HR's read in BLD-A210, with no sign-off needed for launch |

The Landing page (S-01), "How it works" (S-H4), the launch screen (S-LAUNCH) and the office display (S-OFFICE) show only the boards' copy: no NOT DRAWN line is open on them.

## 4. DEC-113, the Ones Committee as one (19 Nov 2026)

The product lead extended DEC-111 on 19 Nov: a sharer never sees a committee member's name either. It reads "the Ones Committee", with no avatar or initials. The review desk and the committee still see each other's names. The boards' "Rohan Mehta from the Ones Committee" is the demo committee member. No template's text changed: the reversal's template (`inbox/decision_reversed` 1.1) already opens with the sender, which is now "The Ones Committee" for these readers. HR is asked to sign off each line below.

| Where | Was | Now | Why |
|---|---|---|---|
| The Inbox (S-H5), the row and the open item's header, the sender of a reversed decision, to the sharer and the crew | Rohan Mehta from the Ones Committee reversed a decision on your idea (with the initials RM) | The Ones Committee reversed a decision on your idea (no avatar or initials) | DEC-113 (BLD-A231). An item sent before the change reads the same way |
| The email for a reversed decision (template `inbox/decision_reversed` 1.1), its first line, to the sharer and the crew | Rohan Mehta from the Ones Committee reversed a decision on your idea: {title}. | The Ones Committee reversed a decision on your idea: {title}. | DEC-113. The subject, "The Ones Committee reversed a decision", names no one and is unchanged |
| The same item and email, to the reviewer whose decision was reversed, or anyone on the review desk or the committee | Rohan Mehta from the Ones Committee reversed your decision on this idea | Unchanged | DEC-113 keeps the names between the desk and the committee |
| The Inbox, a comment or a mention a committee member writes in the conversation, to someone outside the desk and the committee | Rohan Mehta commented on your idea / Rohan Mehta mentioned you (with the initials RM) | The Ones Committee commented on your idea / The Ones Committee mentioned you (no avatar or initials) | DEC-113, with lane F, who marks these items (BLD-A231) |
| The emails for that comment and mention (templates `inbox/comment` 1.0, `inbox/mention` 1.0), subject and first line | Rohan Mehta commented on your idea / Rohan Mehta commented on {title}. / Rohan Mehta mentioned you / Rohan Mehta mentioned you in the conversation about {title}. | The Ones Committee commented on your idea / The Ones Committee commented on {title}. / The Ones Committee mentioned you / The Ones Committee mentioned you in the conversation about {title}. | DEC-113. The template text is unchanged; only the sender is |
