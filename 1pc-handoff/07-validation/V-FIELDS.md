---
id: V-FIELDS
title: Field rules and messages
rev: 1
status: baseline
source: reference/copy/
depends_on: [C-FIELD, C-FIELD-MSG, A-API]
last_delta: none
---

# Field rules and messages

Every rule is enforced on the server and mirrored in the front end. Messages appear under their field (`C-FIELD-MSG`). "Drawn" = the message is on the canvas, word for word. "Default" = not drawn; use this wording until a delta replaces it.

General:

1. `V-FIELDS/1` Trim leading and trailing spaces before counting characters. Count characters, not bytes.
2. `V-FIELDS/2` A disabled primary button that is clicked moves focus to the first field that blocks it and shows that field's message.
3. `V-FIELDS/3` The first invalid field receives focus on a failed submit and is scrolled clear of sticky bars.
4. `V-FIELDS/4` Messages clear as soon as the field is valid; they never time out.
5. `V-FIELDS/5` Every free-text field passes hidden-detail detection (`L-HIDE`) before anyone else can read it.

## `V-FIELDS.signin` Sign in (`S-02`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Work email | Required; a valid address on an allowed domain | "Use your KFintech email, like name@kfintech.com." | Default |
| 2 | Work email | "Send code" disabled until rule 1 passes | none | Drawn |
| 3 | Code | Exactly 6 digits; digits only; `maxlength` 6 across the boxes | "Sign in" disabled until 6 digits | Drawn |
| 4 | Code | Must match the latest code | "That code didn't match. Check the latest email from 1% Club. 2 tries left." (count from the server) | Drawn |
| 5 | Code | Expired or out of tries | "That code has run out. We've sent a new one." | Default |
| 6 | Resend | Not before the countdown ends | "You can ask for a new code in 0:45." | Drawn |
| 7 | Any | Rate limited | "Too many tries. Wait 10 minutes, or use single sign-on." | Default |

## `V-FIELDS.tellit` Tell it (`S-03` prompt, `S-04`, `S-04B`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Your words | At least 30 characters in total before "Move to Review" | "Your draft needs a little more first." (desktop, beside the button); "30 more characters" counting down, then "Enough to work with" (phone) | Drawn |
| 2 | Your words | No upper limit per message is drawn | Limit each message to 5,000 characters: "That's a lot for one go. Send this part, then carry on." | Default |
| 3 | Move to Review | All six parts in, and no detail being added | "Still working through your words." / "Finishing your last detail first." | Drawn |
| 4 | Move to Review | Nothing typed yet | "Start your draft first. It forms from your words." | Drawn |
| 5 | Voice | Up to 3 minutes per clip | "Listening. Up to 3 minutes." At the limit recording stops and the transcript stays | Drawn (limit); stop behaviour default |
| 6 | Microphone | Permission needed | Desktop: "Your browser has blocked the microphone. Allow it from the lock icon in the address bar, then try again. Or just type in the box above." Phone: "The microphone is off for this app. Turn it on in your phone's settings, or type above. Your words save as you go." | Drawn |
| 7 | A draft part, edited by hand | Title 1 to 70 characters; others not empty | "Give it a few words." | Default |
| 8 | Show a hidden detail | A reason must be chosen | "Show it" stays disabled until one is picked | Drawn |
| 9 | Attachment | Size and type (`A-API.files`) | "Too big. Files can be up to 15 MB." (the number from configuration) | Drawn |
| 10 | Link | Must be a URL | "That doesn't look like a link. A link looks like intranet.kfintech.com/page." With several pasted and one bad: ""<text>" doesn't look like a link. Fix it or delete it, then add again." | Drawn |

## `V-FIELDS.checkit` Check it and Edit (`S-05`, `S-06B`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Title | 1 to 70 characters | "Give it a title of a few words." | Default |
| 2 | What happens | Not empty | "Say what happens, in a sentence or two." | Default |
| 3 | `V-FIELDS.sorting` Sorting | Who it affects: at least one. What kind: exactly one. Area: exactly one. What it would bring: at least one ("Not sure yet" counts and clears the others) | Under the sorting card: "Confirm these, or change any of them, before you send." | Drawn |
| 4 | Sorting, at Submit | Confirmed (`L-SORT.rules/2`) | On the Send part: "Confirm the sorting first, or change any of it." with "Go to the sorting"; the summary row reads "Not confirmed yet" | Drawn |
| 5 | Proof: file | Uploaded | "Didn't upload. Your other files are fine." + Try again | Drawn |
| 6 | Proof: file | No personal data | "Found a phone number on page 2. Nobody can open it until it's hidden." + Hide it for me / Remove file. Blocks Submit until resolved | Drawn |
| 7 | Proof: link | Reachable (warning only; does not block) | "We couldn't open this link. It may need a sign-in; the review desk can still try it." + Keep it | Drawn |
| 8 | Fix: "How would you solve it?" | Required to add a fix; at least 20 characters | "Say how you'd solve it, or close this to send without a fix." | Drawn (message); length default |
| 9 | Fix: amounts | A number or a range, in any Indian form (2 lakh, 2L, 2,00,000); units implied by the field | "Write a rough figure or a range, like 70 to 150." | Default |
| 10 | Who would help: own words | Up to 140 characters | counter only | Default |
| 11 | Merge request note | At least 30 characters | "Add a little more: at least 30 characters." (warning) | Drawn |
| 12 | Submit while a merge request waits | Not allowed | The bar: "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own." + "Withdraw the request" | Drawn |
| 13 | Submit | Server error | "Couldn't send. Your draft is safe. Check your connection, then try again." + Try again | Drawn |
| 14 | Submit | Offline | "You're offline. Your draft is saved on this device. Submit now and it sends when you're back online." | Drawn |
| 15 | Save changes (Edit) | Inside the edit window | "The review desk has just opened it, so it can't be changed now. Your changes are kept below. Send them as a message instead." | Default |
| 16 | Withdraw reason | Optional, up to 280 characters | none | Default |

## `V-FIELDS.teamup` Team up (`C-SHEET-TEAMUP`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Your note to {lead} | At least 30 characters; up to 600 | Under 30: "Add a little more: at least 30 characters." (warning; the button is disabled and clicking it focuses the note). Untouched draft: "We drafted this from your idea. Change anything you like." Edited and valid: "Looks good." | Drawn (600 limit default) |
| 2 | Bring your ideas along | Optional; any number; only the person's own shared ideas that are not closed | none | Drawn |
| 3 | Send | Not already on the crew or waiting | The entry point is not offered | Drawn |

## `V-FIELDS.answer` Answer (`S-R3`) and conversation (`S-08`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | An answer | Optional per question; up to 2,000 characters | counter near the limit | Default |
| 2 | Send answers | At least one answer | Button disabled, "Answer at least one question" | Default |
| 3 | Answer file | As `V-FIELDS.checkit/5–6` | same | Drawn |
| 4 | Message | Text or a file | "Write a message or attach a file first." | Drawn |
| 5 | Message | Up to 4,000 characters | counter near the limit | Default |

## `V-FIELDS.review` Reviewer (`S-R2`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Your question | Not empty to add; up to 300 characters; pinned to one part | The add button is disabled while empty | Drawn (limit default) |
| 2 | Send questions | At least one queued; a time to answer chosen (default 3 days) | The bar shows "Decide on this idea" instead until one is queued | Drawn |
| 3 | Time to answer after the decide-by date | Warning, does not block | "That's after you decide, so you'd need to move your date." | Drawn |
| 4 | `V-FIELDS.decision` Decision | One of three chosen | "Choose Pick, Not now or Not picked first." | Drawn |
| 5 | Reason | At least 30 characters; up to 1,000 | Counter "12 of at least 30 characters" → "Kavya reads this word for word."; on send: "Give Kavya a reason of at least a line, 30 characters or more." | Drawn (1,000 default) |
| 6 | Not now: look again in | One of 1, 3, 6 months (default 3) | none | Drawn |
| 7 | Worth: hours, cost, revenue | Numbers or ranges, any Indian form; all optional | "Write a figure or a range." | Default |
| 8 | Worth: note | Optional, up to 280 characters | none | Default |
| 9 | Merge: which idea leads | One chosen (a default is set) | none | Drawn |
| 10 | Merge: note to both | At least 20 characters; up to 600 | "Tell both why, in a line or two." | Drawn |

## `V-FIELDS.committee` Committee (`S-R4`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Change it to | One of the two other decisions | "Choose what to change it to." | Drawn |
| 2 | Your note to {sharer} | At least 30 characters; up to 1,000 | "Write a note of at least a line, 30 characters or more." | Drawn |
| 3 | Extend | Under the 3-month limit | Button replaced by "At the 3-month limit" | Default |

## `V-FIELDS.one` One dashboard and Profile (`S-ONE`, `S-H6`)

| # | Field | Rule | Message | Source |
|---|---|---|---|---|
| 1 | Number you'd like | Whole number 1 to 999 | "Pick a number from 1 to 999." | Default |
| 2 | Number | Free | "No. 7 is taken. Free numbers near it: 6, 8, 11." | Default |
| 3 | Number | Inside the 30-day window | Field replaced by "No. 1 is yours for good." | Default |
| 4 | Impact brief | 20 to 140 characters, one sentence | "Keep it to one sentence, up to 140 characters." | Default |
| 5 | A settings switch | Saves at once | On failure: "Couldn't save that. Try again." | Default |
