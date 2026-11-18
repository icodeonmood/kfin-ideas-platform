# New wording in lane F, for HR's sign-off

Written 17 Nov 2026 for HR's review of launch-facing copy (SHIP_PLAN §8). Four parts: team-up and merge requests, the conversation, Find your crew, and search.

## Team-up and merge requests (L-TEAMUP, L-MERGE.request, C-SHEET-TEAMUP)

Written 17 Nov 2026 for HR's review of launch-facing copy (SHIP_PLAN §8). Everything else in team-up is the design pack's own copy (`1pc-handoff/reference/copy/CrewRequest.md`, `Review.md`, and `C-SHEET-TEAMUP`), used as it stands. These are the lines lane F had to change or add, with the module each belongs to. "Kavya" stands for the person asking and "Ravi" for the idea's lead: at run time each is the real person's first name. The code is `services/worker/teamup/rules.py` (words) and `requests.py`, `drafts.py`, `crew.py` (messages under a field).

## 1. Lines changed so they never guess a person's gender (BLD-E008)

The board says "she" and "her" for the demo requester. With real people that would guess their gender, so the first name is used, or "they" and "their" where the name would repeat. BLD-E010 allows a pronoun the person chose in Profile; team-up does not read that choice yet, so it uses the neutral wording for everyone.

| Module | Pack line | Our line |
|---|---|---|
| `S-H2B.reader` (the lead's Inbox reader, the request line) | Kavya Menon asks to team up and merge her idea into yours | Kavya Menon asks to team up and merge their idea into yours |
| `S-H2B.reader`, the note's heading | Her note | Kavya’s note |
| `S-H2B.reader`, the heading over the idea brought | The idea she asks you to merge into yours | The idea Kavya asks you to merge into yours |
| `S-H2B.reader`, the link on the idea brought | Open her idea | Open Kavya’s idea |
| `S-H2B.reader`, the line over the three answers | Merge it, and her idea joins yours: she is on your crew and credited on it. Team up only puts her on your crew and keeps her idea separate. Decline, and she sends hers on its own, with your reason if you give one. | Merge it, and Kavya’s idea joins yours: they are on your crew and credited on it. Team up only puts Kavya on your crew and keeps their idea separate. Decline, and they send theirs on its own, with your reason if you give one. |
| `S-H2B.states`, Merged | Merged. Kavya’s idea is now part of yours, and she is on your crew, credited. We’ve told her. | Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them. |
| `S-H2B.states`, Teamed up only | Teamed up. Kavya is on your crew. Her idea stays separate, and she sends it on its own. We’ve told her. | Teamed up. Kavya is on your crew. Their idea stays separate, and they send it on its own. We’ve told them. |
| `S-H2B.states`, Declined | Declined. Kavya sees your reason: “The crew is full for now”. She can send hers on its own. | Declined. Kavya sees your reason: “The crew is full for now”. They can send theirs on its own. |

## 2. Lines the pack does not draw

| Module | Pack line | Our line |
|---|---|---|
| `S-H2B.reader`, a request with no idea brought (`S-H2B.rules/3` names only the buttons) | Not drawn | Team-up request (the label, where the board says Merge request) / Kavya Menon asks to team up / Approve, and Kavya joins your crew. Decline, and they see your reason if you give one. |
| `S-H2B.reader`, two or more ideas brought | Not drawn | Kavya Menon asks to team up and merge their ideas into yours / The ideas Kavya asks you to merge into yours / Merge it, and Kavya’s ideas join yours: … keeps their ideas separate. … |
| `S-H2B.states`, Approve with nothing brought | Not drawn | Teamed up. Kavya is on your crew. We’ve told them. |
| `S-H2B.states`, Merged or Teamed up only with two or more ideas | Not drawn | Merged. Kavya’s ideas are now part of yours, … / Their ideas stay separate, and they send them on their own. |
| `S-H2B.states`, Declined without a reason (the reason is optional, `S-H2B.rules/1`) | Not drawn | Declined. We’ve told Kavya. They can send theirs on its own. (the last sentence only when an idea was brought) |
| `S-H2B.reader/3`, when the idea brought was shared | Shared Saturday. | Shared today. / Shared yesterday. / Shared 2 Nov. (more than a week ago) |
| `C-SHEET-TEAMUP.after`, Declined ("The lead's reason if given; the person can send theirs on its own") | Not drawn | Ravi declined: “The crew is full for now”. Send yours on its own. / Ravi declined. |
| `C-SHEET-TEAMUP.after`, Approved (merged) | Merged into IDEA-…, with credit to you. | The same line, with "Say hello" beside it, as for Team up only (`J-TEAMUP/5`) |
| `L-MERGE.request/6`, Check it after Team up only | Not drawn | You’re on the crew / You’re on the crew. You’ll get its updates. Send yours on its own. |
| `L-MERGE.request/7`, Check it after a decline without a reason | Not drawn | Ravi kept that idea separate. Send yours on its own. |
| `L-TEAMUP.rules/2`, the pre-filled note (BLD-F011: a fixed template, no assistant) | "a first draft is generated from the requester's own closest idea and their role" | I’m in Investor service (Senior executive). I shared “{their closest idea}”, which is close to yours, and I can bring what I learned from it. / without an idea of their own: … This touches my work, and I can help shape and test the fix. |
| `V-FIELDS.teamup/1`, a note over 600 characters | Not drawn | Keep your note to 600 characters. |
| `S-H2B.rules/1`, a decline reason over 280 characters | Not drawn | Keep the reason to 280 characters. |
| `A-API.team-up` errors, shown under the field or on the sheet | Only `note_too_short` is worded ("Add a little more: at least 30 characters.") | `idea_closed`: This idea is no longer open to team up. · `already_on_crew`: You’re on the crew. · `already_requested`: Waiting for Ravi (a draft: Waiting on Ravi to merge) · `brought_invalid`: Choose from your own shared ideas. · `not_lead`: Only the lead of this idea can answer. · `nothing_brought`: Nothing was brought to merge. Approve puts Kavya on your crew. · `brought_not_open`: That idea is no longer open to merge. · `answer_required`: Choose an answer. · `not_waiting`: Kavya withdrew this request. / You’ve answered this request already. / This request has already been answered. · `forbidden`: Sign in again to team up. |
| `A-API.drafts` merge-request errors | Only `note_too_short` | `draft_closed`: This draft has already been sent. · `idea_closed`: This idea is no longer open to merge. · `already_on_crew`: You lead this idea. |
| `L-TEAMUP.rules/11`, leaving and removal (NOT DRAWN default) | Not drawn | `not_on_crew`: You’re not on this crew. / That person is not on this crew. · `lead_stays`: You lead this idea, so you stay on its crew. · `not_lead`: Only the lead of this idea can remove someone. |

## 3. Lines added after the 17 Nov review

| Module | Where it shows | Our line |
|---|---|---|
| `A-API.team-up`, `A-API.drafts`: any 404 `not_found` (BLD-F025) | The sheet, Check it or the Inbox reader, when the idea, draft or request is not there or is not the person's to see | We couldn’t find that. |
| `A-API.team-up`: `DELETE /team-up/:id` on a request that closed with its idea (BLD-F025) | The requester's "Waiting for Ravi" card, if the idea closed first | This idea is no longer open to team up. (the existing `idea_closed` line, instead of "This request has already been answered.") |
| `A-API.conventions/3`: 409 `key_reused` (BLD-F026) | Any team-up or merge-request send, when the screen resends a key with other details | Something changed since you last sent this. Refresh the page and try again. |
| `S-H2B.reader`: answering a draft merge request whose draft was sent or archived while it waited (BLD-F024) | The lead's Inbox reader | Kavya withdrew this request. (the existing `not_waiting` line) |
| `S-H2B.reader/3`: an idea brought whose short summary fails the checks (BLD-F022, BLD-C090) | The lead's Inbox reader | A short summary is on its way. (lane C's existing placeholder, BLD-C022) |


## 4. The team-up sheet (`C-SHEET-TEAMUP`, added 17 Nov)

The sheet's own words are the pack's (`C-SHEET-TEAMUP` and `reference/copy/Crew.md`, view=Request and view=Request sent), used as they stand: they name the lead, so no line needed the BLD-E008 change. The code is `apps/web/src/components/teamup/teamup-sheet.tsx` (`TEAMUP_COPY`). These are the lines the pack does not draw.

| Module | Where it shows | Our line |
|---|---|---|
| `C-SHEET-TEAMUP.compose/5`, the privacy line in full | Under the choice, once one or more ideas are picked (the pack writes "…and the idea you bring.") | Ravi sees your name, your note and the idea you bring. / Ravi sees your name, your note and the ideas you bring. |
| `C-SHEET-TEAMUP.compose/4`, the open list with nothing to pick | "Bring your ideas along", for a person with no shared idea of their own | You have no shared ideas to bring yet. |
| `C-SHEET-TEAMUP.compose`, Check it: the name of the single choice (BLD-F071) | Above "Ask Ravi to merge mine in" and "Keep mine separate" | Your draft |
| `C-SHEET-TEAMUP.compose/3`, a note over 600 characters | Under the note (the line in section 2, now also shown before sending) | Keep your note to 600 characters. |
| `C-SHEET-TEAMUP.sent`, the withdraw in progress | On "Withdraw request" while it goes | Withdrawing… |
| `C-SHEET-TEAMUP`, while the note loads | Read by a screen reader only | Loading your note |
| `C-SHEET-TEAMUP`, when neither the idea nor the note loads | The sheet's title, with the reason under it and "Try again" | Team up |
| `C-SHEET-TEAMUP`, opened on an idea the person cannot ask about (BLD-F072) | In place of the note, with only "Done" | You lead this idea. / You’re on the crew. / This idea is no longer open to team up. (the API's existing lines) |
| `A-API.conventions/2`, a 401 (the session ended) as well as a 403 | Above "Send to Ravi" | Sign in again to team up. (the existing `forbidden` line) |
| No answer from the server | Above "Send to Ravi", or where the note would be | Check your connection, then try again. (lane C's line on the preview, BLD-C100) |
| An answer the sheet cannot read | Above "Send to Ravi" | Something went wrong. Please try again. (the existing `worker_error` line) |
| `C-SHEET-TEAMUP`, when the note did not load | The button under the reason | Try again (C-PREVIEW's existing button, BLD-C100) |
| `C-SHEET-TEAMUP`, opened while a request still waits but the request did not come back (BLD-F074) | In place of the note, with only "Done" | Waiting for Ravi (the opener's own line, `C-SHEET-TEAMUP.after`) |

Not the sheet's: `Crew.md` view=Request sent also adds "Ravi Nair, Investor service", "Waiting for Ravi" and the link "Rejection SMS codes confuse investors, waiting for Ravi. Open the idea." These are a row in S-H2's "Your crews" list behind the sheet (they replace "Ideas you team up on show here."), so they belong to the crew page, which lane F builds next, and are used there word for word (BLD-F074).

## 5. A lead who is not named (BLD-F029, added 18 Nov)

DEC-104: a lead who hid their name from the Wall in Profile, or has left, is not named to a person asking to join until that person is on the crew (the review desk and the Ones Committee always see the name). Each line below is the pack's line with the lead's name replaced by "the lead" ("The lead" at the start of a sentence); nothing else changes. The code is `services/worker/teamup/rules.py` (`lead_word`) and `apps/web/src/components/teamup/teamup-sheet.tsx` (`leadWord`).

| Module | Where it shows | Pack line (lead named) | Our line (lead not named) |
|---|---|---|---|
| `C-SHEET-TEAMUP.compose/2` | The sheet's title | Team up with Ravi | Team up with the lead |
| `C-SHEET-TEAMUP.compose/2` | The line under the title | Ravi leads “Rejection SMS codes confuse investors” and decides who joins. Tell Ravi what you bring. | The lead of “Rejection SMS codes confuse investors” decides who joins. Tell them what you bring. |
| `C-SHEET-TEAMUP.compose/3` | The note's label | Your note to Ravi | Your note to the lead |
| `C-SHEET-TEAMUP.compose/5` | The privacy line | Ravi sees your name, your note. (…and the idea you bring. / …and the ideas you bring.) | The lead sees your name, your note. (…and the idea you bring. / …and the ideas you bring.) |
| `C-SHEET-TEAMUP.compose/6` | The button | Send to Ravi | Send to the lead |
| `C-SHEET-TEAMUP.compose`, Check it | The choice to merge | Ask Ravi to merge mine in / Ravi decides. If Ravi accepts, yours joins that idea with credit to you. If not, you send yours on its own. | Ask the lead to merge mine in / The lead decides. If the lead accepts, yours joins that idea with credit to you. If not, you send yours on its own. |
| `C-SHEET-TEAMUP.sent` | The sent step | Sent to Ravi / Ravi reads your note, then approves or declines. You’ll hear in your Inbox. | Sent to the lead / The lead reads your note, then approves or declines. You’ll hear in your Inbox. |
| `C-SHEET-TEAMUP.after`, waiting; the 409 `already_requested` | The opener (Find your crew, the idea page, Status) and the sheet | Waiting for Ravi | Waiting for the lead |
| `C-SHEET-TEAMUP.after`, declined (section 2's line) | The opener | Ravi declined: “The crew is full for now”. Send yours on its own. / Ravi declined. | The lead declined: “The crew is full for now”. Send yours on its own. / The lead declined. |
| `L-MERGE.request/4` (Review.md, merge=Waiting for Ravi); the 409 `already_requested` on a draft | Check it's Similar ideas part and the bar under the steps | Waiting on Ravi to merge / Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own. | Waiting on the lead to merge / Waiting for the lead to accept the merge. If the lead declines, you can send yours on its own. |
| `L-MERGE.request/7` | Check it after a decline | Ravi kept it separate / Ravi kept that idea separate: “Better as two”. Send yours on its own. | The lead kept it separate / The lead kept that idea separate: “Better as two”. Send yours on its own. |
| `L-MERGE.request/5`, accepted, only when the person has left the crew since | Check it | Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send. | The lead accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send. |

The person asking is still named to the lead they ask, even if they hid their name from the Wall (BLD-F075): the sheet tells them so before they send ("Ravi sees your name, your note." / "The lead sees your name, your note."), so the lead's Inbox reader keeps the lines in sections 1 and 2.

## Conversation (L-CONVO, S-08)

The lines below that name a reviewer ("Meera from the review desk", "Meera has 3 questions …") are as the review desk and the Ones Committee read them. Since DEC-111 everyone else reads the review desk in their place: see section 6.

Everything else on S-08 is the design pack's own copy (`1pc-handoff/reference/copy/Messages.md`), used as it stands: "You shared it.", "Checked and matched. 1 folio number hidden, 2 similar ideas found.", "Meera from the review desk opened it.", "Meera from the review desk picked it.", "Arjun Rao’s team started building it.", "Ravi Nair approved your team-up request.", the four placeholders, the visibility lines the board draws, "No messages yet", the line above the box while questions are open, "Your answers to Meera’s 3 questions", "Each answer was added to its part of your idea. Meera decides by Friday 20 November.", "Write a message or attach a file first." and "Message removed" (`L-CONVO/10`). "Meera", "Ravi", "Kavya" and "Sanjay" stand for real people: at run time each is the person's name, and "You" for the reader. The code is `services/worker/convo/render.py` (event lines), `reads.py` (header, side panel, box) and `messages.py` (messages under the box).

### 1. Lines changed so they never guess a person's gender (BLD-E008)

The conversation board draws no "he" or "she". The one line lane F wrote about a person who is not the reader, where the name would repeat, uses "them".

| Module | Pack line | Our line |
|---|---|---|
| `L-MERGE.effects`, a draft merged into the lead's idea (J-SIMILAR/6a) | Not drawn | Kavya Menon’s idea is now part of it, with credit to them. (for Kavya: Your idea is now part of it, with credit to you.) |

### 2. Event lines the pack does not draw

| Module | Pack line | Our line |
|---|---|---|
| `L-CONVO/3`, the desk decides | Meera from the review desk picked it. | Meera from the review desk chose Not now. / Meera from the review desk didn’t pick it. |
| `L-WORTH`, the desk revises what it is worth | Not drawn | Meera from the review desk revised what it’s worth. |
| `L-REVIEW`, the date to decide moves | Not drawn | Meera from the review desk moved the date to decide. |
| `L-DECIDE`, a Not now idea comes back | Not drawn | It’s back with the review desk. |
| `L-MERGE.effects/6`, the desk merges (on the idea that joins) | "a closing line with a link" | Meera from the review desk joined it with IDEA-2026-001412. The conversation carries on there. (the reference is the link) |
| `L-MERGE.desk`, the desk merges (on the lead idea) | Not drawn | Meera from the review desk joined it with IDEA-2026-001481. |
| `L-COMMITTEE`, a decision reversed | Not drawn | Rohan Mehta from the Ones Committee reversed the decision. It’s now Not now. |
| `L-COMMITTEE`, a desk merge undone | Not drawn | Rohan Mehta from the Ones Committee undid the merge. Each idea is on its own again. |
| `L-TEAMUP.rules/7`, as the lead and others read it | Ravi Nair approved your team-up request. | You approved Kavya Menon’s team-up request. / Ravi Nair approved Kavya Menon’s team-up request. |
| `L-TEAMUP.rules/8`, someone joins the crew | Not drawn | Kavya Menon joined the crew. / You joined the crew. |
| `L-TEAMUP.rules/11`, leaving and removal | "announced in the conversation" | Kavya Menon left the crew. / Ravi Nair took Kavya Menon off the crew. / You took Kavya Menon off the crew. |
| `L-MERGE.effects/6`, the lead accepted a merge (on the idea that joins) | "a closing line with a link" | It’s now part of IDEA-2026-001412. The conversation carries on there. |
| `L-MERGE.effects`, the lead accepted a merge (on the lead idea) | Not drawn | IDEA-2026-001481 is now part of it, with credit to Kavya Menon. |
| `L-CONVO/3`, the build team starts, as its lead reads it, or with no lead named (BLD-F061) | Arjun Rao’s team started building it. | Your team started building it. / The build team started building it. |
| `L-CONVO/3`, the desk decides with a choice the line does not know | Meera from the review desk picked it. | Meera from the review desk decided. |
| `L-COMMITTEE`, a decision reversed with no outcome named | Not drawn | Rohan Mehta from the Ones Committee reversed the decision. |
| `L-TEAMUP.rules/7`, the person who asked is no longer there | Ravi Nair approved your team-up request. | Ravi Nair approved a team-up request. |
| `L-CONVO/3`, Checked and matched with nothing hidden or found | Checked and matched. 1 folio number hidden, 2 similar ideas found. | Checked and matched. Nothing to hide, no similar ideas found. (and "2 folio numbers and 1 PAN hidden" for more than one kind) |
| A line whose person or idea is no longer there | Not drawn | A colleague (for a person erased from the records) / It’s now part of another idea. / Another idea is now part of it. / Meera from the review desk joined it with another idea. |

### 3. The header, the side panel and the box

| Module | Pack line | Our line |
|---|---|---|
| `S-08.layout/1`, a build team's idea read by someone other than the sharer | Your idea, being built by Arjun Rao’s team | Kavya Menon’s idea, being built by Arjun Rao’s team |
| `L-CONVO/8`, what each person is doing | Reviewing it / Shared the idea / On the crew / Joined today / Leads the build team / Picked it / Mentioned | Chose Not now / Didn’t pick it / On the build team / From the review desk / From the Ones Committee / In the conversation |
| `S-08.layout/3`, the visibility line as others read it | Only you and the review desk see this conversation. | Only Kavya and the review desk see this conversation. |
| `S-08.layout/3`, a build team's idea read by anyone but the sharer (the sharer reads the board's line, crew or not, BLD-F060) | You, the build team and the review desk see this conversation. | The crew, the build team and the review desk see this conversation. (with a crew) / Kavya, the build team and the review desk see this conversation. |
| `S-08.layout/3`, a mentioned person on an idea with no crew | The crew, the review desk and anyone they mention see this conversation. | Kavya, the review desk and anyone they mention see this conversation. |
| `L-MERGE.effects/6`, the box on a merged idea | Not drawn | This idea is now part of another one. Write in IDEA-2026-001412’s conversation. (when the idea it joined is no longer there: … Write in the idea it joined.) |
| `L-CONVO/5`, the box's placeholder for the review desk, the committee or the build team writing to a sharer with no crew | Reply to Sanjay (a mentioned person's box) | Reply to Kavya (the sharer's first name) |
| `L-CONVO/4`, the answers message as the reviewer reads it | Your answers to Meera’s 3 questions | Kavya’s answers to your 3 questions |

### 4. Messages under the box (A-API errors)

| Module | Pack line | Our line |
|---|---|---|
| `L-CONVO/5`, a message over 4,000 characters (BLD-F055) | Not drawn | Keep a message under 4,000 characters. |
| `L-CONVO/7`, a sixth file on one message (BLD-F055) | Not drawn | Attach up to 5 files to a message. |
| `L-CONVO/6`, an eleventh person mentioned in one message (BLD-F055) | Not drawn | Mention up to 10 people in a message. |
| `L-CONVO/7`, a file sent by someone who cannot add files (BLD-F063; S-08 shows them no attach control) | Not drawn | You can’t add files here. The person who shared this idea or the review desk can add them. |
| `L-CONVO/7`, the check for customers’ details could not run (BLD-F054) | Not drawn | We couldn’t check this message for customers’ details just now. Try again in a minute. |
| `L-CONVO/7`, a file that is not this person's, not on this idea, or already sent | Not drawn | This file can’t be added here. Add it again from this conversation. |
| `L-CONVO/7`, a file still being checked | Not drawn | This file is still being checked. Send it once it shows as checked. |
| `L-CONVO/7`, a file with a customer detail found (DEC-107) | Not drawn | This file has a customer detail in it. Hide the detail or remove the file first. |
| `L-CONVO/10`, removing someone else's message | Not drawn | You can remove only your own messages. |
| `L-CONVO/10`, removing after 5 minutes | Not drawn | A message can be removed only in the first 5 minutes after sending. |
| `A-API.conventions/3`, the same request sent again with other words | Not drawn | This request was already sent with different words. Refresh and try again. |

### 5. The conversation screen (S-08)

Everything else on S-08 is the pack's copy (Messages.md) or comes from the conversation's own lines above.

| Module | Pack line | Our line |
|---|---|---|
| `S-08`, a message that did not reach the server | Not drawn | Your message didn’t send. Try again. |
| `S-08`, the button on one's own message in its first 5 minutes (L-CONVO/10) | Not drawn | Remove (read out as "Remove your message from Today, 10:07 am") |
| `S-08`, a removal that did not go through | Not drawn | The message wasn’t removed. Try again. |
| `S-08`, the Send button while sending | Send | Sending |
| `S-08`, the @mention list, as read out (L-CONVO/6) | Not drawn | People to mention. "3 people to mention. Use the up and down arrows, then Enter." ("1 person to mention. …" for one) |
| `S-08.rules/4`, the phone's "i" button and the sheet's button | an "i" button | Who is in this conversation / Close |
| `S-08`, a file's button and the file lists, as read out | View | View plain-rejection-reasons.xlsx / Files in your message / Files in Ravi Nair’s message / Files with this answer |
| `S-08`, the questions for a reader who did not ask them (BLD-F065) | Meera has 3 questions about your idea | Meera from the review desk asked 3 questions. / You asked 3 questions. / See them on the idea |
| `S-08`, the sharer's questions once closed before every answer came (BLD-F065) | Meera’s 3 questions, answered | Meera’s 3 questions, now closed |

### 6. The review desk, not the person at it (DEC-111, added 18 Nov)

For HR's sign-off under DEC-111. The sharer, the crew, the build team and anyone mentioned never see the name of the person at the review desk. Each line below is the line they read before, with the reviewer's name replaced by "the review desk" ("The review desk" at the start of a line or as a byline), and no face or initials beside it. Nothing else in the line changes. The review desk and the Ones Committee still read the named lines in sections 2, 3 and 5. The Ones Committee's own lines ("Rohan Mehta from the Ones Committee reversed the decision.") are unchanged (BLD-F082). The code is `services/worker/convo/render.py` and `reads.py` (`Ctx.shown`), with the words from `onepc/words.py`; the screen is `apps/web/src/components/convo/conversation.tsx`.

| Module | Line before (as the sharer, crew or build team read it) | Line now, for HR's sign-off (DEC-111) |
|---|---|---|
| `L-CONVO/3`, the desk opens the idea | Meera from the review desk opened it. | The review desk opened it. |
| `L-CONVO/3`, the desk decides | Meera from the review desk picked it. / … chose Not now. / … didn’t pick it. / … decided. | The review desk picked it. / The review desk chose Not now. / The review desk didn’t pick it. / The review desk decided. |
| `L-WORTH`, the desk revises what it is worth | Meera from the review desk revised what it’s worth. | The review desk revised what it’s worth. |
| `L-REVIEW`, the date to decide moves | Meera from the review desk moved the date to decide. | The review desk moved the date to decide. |
| `L-MERGE.effects/6`, the desk merges (on the idea that joins) | Meera from the review desk joined it with IDEA-2026-001412. The conversation carries on there. | The review desk joined it with IDEA-2026-001412. The conversation carries on there. |
| `L-MERGE.desk`, the desk merges (on the lead idea), or the other idea is no longer there | Meera from the review desk joined it with IDEA-2026-001481. / … joined it with another idea. | The review desk joined it with IDEA-2026-001481. / The review desk joined it with another idea. |
| `L-CONVO/5`, a message from the desk: the name above it | Meera from the review desk (with her initials in a circle) | The review desk (no circle, no initials) |
| `S-08`, the files on the desk's message, as read out | Files in Meera from the review desk’s message | Files in the review desk’s message |
| `L-CONVO/4`, the sharer's open questions (Messages.md) | Meera has 3 questions about your idea | The review desk has 3 questions about your idea |
| `L-CONVO/4`, the sharer's questions once answered (Messages.md) | Meera’s 3 questions, answered | The review desk’s 3 questions, answered |
| `L-CONVO/4`, the sharer's questions closed before every answer came (BLD-F065) | Meera’s 3 questions, now closed | The review desk’s 3 questions, now closed |
| `L-CONVO/4`, the questions as the crew and the build team read them (BLD-F065) | Meera from the review desk asked 3 questions. | The review desk asked 3 questions. |
| `L-CONVO/4`, the line above the box while questions are open (Messages.md) | Answer Meera’s 3 questions with Answer the questions, so each answer lands on its part of your idea. Write here for anything else. | Answer the review desk’s 3 questions with Answer the questions, so each answer lands on its part of your idea. Write here for anything else. |
| `L-CONVO/4`, the answers message (Messages.md) | Your answers to Meera’s 3 questions / Kavya’s answers to Meera’s 3 questions | Your answers to the review desk’s 3 questions / Kavya’s answers to the review desk’s 3 questions |
| `S-08` "Answers sent", the sharer's line under the answers (Messages.md) | Each answer was added to its part of your idea. Meera decides by Friday 20 November. | Each answer was added to its part of your idea. The review desk decides by Friday 20 November. |
| `L-CONVO/8`, "In this conversation" | Meera from the review desk, Reviewing it (one row per reviewer, each with initials) | The review desk, Reviewing it (one row for the desk, no circle; also Picked it / Chose Not now / Didn’t pick it / From the review desk) |
| `L-CONVO/5`, the box of a person the desk mentioned | Reply to Meera | Reply to the review desk |
| `L-CONVO/6`, a person at the desk mentioned in the desk's message | @Harish Kulkarni (highlighted) | @the review desk (highlighted); the mention list does not offer the desk to the sharer, the crew or the build team (BLD-F083) |

### 7. Teams named only while Teams messages go out (DEC-105, BLD-F086, added 18 Nov)

For HR's sign-off. Teams messages are built and switched off at launch (DEC-105), so S-08 names Teams only while the `comms.teams` switch is on. While it is on, both lines read as the board draws them (the "before" column). While it is off, only the Teams clause is dropped (the "after" column); nothing else in the line changes. The code is `services/worker/convo/reads.py` (`empty_state`) and `apps/web/src/components/convo/compose.ts` (`sideNote`).

| Module | Before (Messages.md, and while Teams is on) | After, while Teams is off, for HR's sign-off |
|---|---|---|
| `S-08` "No messages yet", the card's line for the sharer (Messages.md:367) | If the review desk has a question, it shows here and in your Inbox, and we tell you on Teams. | If the review desk has a question, it shows here and in your Inbox. |
| `S-08` "In this conversation", the last line of the side panel (Messages.md:75) | This is the idea’s own conversation. It shows on the idea’s page too, and new messages reach you in your Inbox, on Teams and by email. | This is the idea’s own conversation. It shows on the idea’s page too, and new messages reach you in your Inbox and by email. |

## Find your crew (S-H2, L-CREW, added 18 Nov)

The page's own words are the pack's (`reference/copy/Crew.md`, every view, and `C-CREW-DECK.states`), used as they stand. "Ravi" stands for the idea's lead and "Saturday" for the day the person shared their own idea: at run time each is the real name or day. The code is `services/worker/crew/deck.py` (the card lines and "Your crews") and `apps/web/src/app/crew/` (the page). These are the lines the pack does not draw.

| Module | Where it shows | Our line |
|---|---|---|
| `L-CREW/2`, "touches their work" (BLD-F034) | The card's reason strip, when the sharer asked for help from the person's line of work | They need someone in Investor service |
| `L-CREW/2`, "close to an idea of theirs" when the match's reason was written for the other person, or there is none (BLD-F032) | The card's reason strip | Close to your idea from Saturday |
| `L-CREW/2`, a match reason that does not start "Same …" (BLD-F032) | The card's reason strip | The calls you describe, like your idea from Saturday |
| `L-CREW/2`, the day in those lines | The card's reason strip | today / yesterday / a weekday within the week / 12 November |
| `S-H2`, a lead who hid their name from the Wall or has left (BLD-F042) | The card's Team up button, read by a screen reader; "Your crews" | Team up on Rejection SMS codes confuse investors: send the lead a note / Waiting for the lead (and "A colleague" for the name, lane C's line) |
| `S-H2`, filters that match nothing (BLD-F037; the pack draws no state) | In place of the deck, with "Clear all" | No ideas match these filters / Try fewer filters, or clear them to see every idea close to yours. |
| `L-CREW/7`, the end of the deck when nothing was asked (the pack draws "You asked to team up on 1 idea.") | "That's everyone for now" | New ideas close to yours show up here. (the line without its first sentence) / You asked to team up on 2 ideas. (the plural) |
| `L-CREW/5`, the filter panel's count, read by a screen reader | As options are picked | 1 idea matches / 2 ideas match (the board's "2 ideas match") |
| `S-H2`, the card's title as a button (it opens the preview) | Read by a screen reader | Rejection SMS codes confuse investors. Preview the idea |
| `S-H2`, while the deck loads | Read by a screen reader only | Loading ideas close to yours |
| `S-H2`, when the deck does not load | In place of the deck, with "Try again" | These ideas did not load / Check your connection, then try again. (lane C's line on the preview, BLD-C100) |
| `S-H2`, when a pass, an undo or "See them again" does not go through | Under the deck | That did not go through. Check your connection, then try again. |

## Search on your own list (L-SEARCH, added 18 Nov)

The first sentence over a result set is lane E's My ideas line, used as it stands ("Found 3 ideas about “SMS”: 2 of yours and 1 you teamed up on. Closest: “…”." and "Nothing found for “SMS”."). The code is `services/worker/search/rules.py`. These are the lines the pack does not draw.

| Module | Where it shows | Our line |
|---|---|---|
| `L-SEARCH/3`, the second sentence (BLD-F041) | Under the first, naming only what matched | Matched on titles, short summaries and your own words. (any of: titles, references, short summaries, your own words, the review desk’s reasons) |
| `L-SEARCH/7`, filters that match nothing, with no words typed | In place of the list | No ideas match these filters. / Try fewer filters. |
| `L-SEARCH/7`, words that match nothing | In place of the list, with "Show all ideas" | Nothing found for “SMS”. / Try other words, or clear the search. (lane E's lines) |
| `L-SEARCH/5`, the filter names | The filter panel | List (Yours, Teamed up) / Status (lane E's filter names) / Category |

