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
