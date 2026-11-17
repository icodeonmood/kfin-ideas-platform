# New wording on team-up and merge requests, for HR's sign-off (lane F)

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
