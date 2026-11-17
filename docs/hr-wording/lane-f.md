# New wording in lane F, for HR's sign-off

Written 17 Nov 2026 for HR's review of launch-facing copy (SHIP_PLAN §8). Lane F's team-up and merge-request wording is listed in this same file on the team-up branch (`f/teamup-3`); when both are on `main`, both sections sit here.

## Conversation (L-CONVO, S-08)

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
