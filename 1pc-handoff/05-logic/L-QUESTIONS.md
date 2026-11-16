---
id: L-QUESTIONS
title: Questions from the review desk, and answers
rev: 1
status: baseline
source: reference/copy/Answer.md
depends_on: [L-NOTIFY, E-ENTITIES]
last_delta: none
---

# L-QUESTIONS: Questions from the review desk, and answers

## `L-QUESTIONS.ask` Asking (reviewer)

1. Asking is optional. A reviewer may decide without asking anything (`L-DECIDE`).
2. A question is free text pinned to one part of the idea: The problem, How often, Who it affects, What it's worth, Attached, Fix. The part is guessed from the wording as the reviewer types and can be changed before adding.
3. The system suggests questions from the idea (gaps and ambiguities), each already pinned ("Suggested from this idea"). A suggestion is added with one click and can be removed.
4. Questions are queued, then sent together as one set with a time to answer: 1 day, 3 days (default) or 1 week. The deadline is shown before sending ("Kavya has until Thursday 19 November, 6 pm."). If the deadline falls after the reviewer's own decision date, say so: "That's after you decide, so you'd need to move your date."
5. Sending a set moves the idea to "Needs you" for the sharer and to "Waiting on the sharer" for the desk, and starts the answer clock.
6. One open set at a time per idea. After answers arrive the reviewer can "Ask a follow-up" (a new set).

## `L-QUESTIONS.answer` Answering (sharer)

1. Questions are answered only on the Answer screen (`S-R3`), one at a time, typed or spoken, with optional files per answer.
2. A question can be skipped and returned to. "Check and send" lists all answers; unanswered ones read "Not answered. It stays open until the deadline."
3. Sending is allowed with at least one answer: "Send 1 answer to Meera". Unanswered questions stay open until the deadline and can be answered later in the same way.
4. Answers are saved as drafts as they are typed (same autosave rules as `L-DRAFT.autosave/1`).
5. On send: each answer is added to its part of the idea (shown under that part on the sharer's page and the reviewer's page, with who and when); all answers post into the idea's conversation as one message; files go through `L-HIDE.files`; the idea returns to the reviewer's "Answered, back to you" tab; the sharer sees "Sent. Meera has your answers."
6. Hidden-detail detection runs on every answer.

## `L-QUESTIONS.clock` Clocks and reminders

1. The reviewer sees for each idea: how many answered ("0 of 3 answered"), whether the sharer has seen the questions and when ("seen 12:05 pm"), and time left ("3 days to answer"; under a day as hours and minutes "07:38 to answer"; then "Overdue by 5 hours").
2. The sharer is reminded 1 day before and 2 hours before the deadline (if they have reminders on, `S-H6`).
3. The reviewer can "Give 2 more days" (extends the deadline once per click) or "Send a reminder"; on an overdue idea the desk row offers "Remind {sharer}".
4. Overdue does not close anything. The reviewer may decide with what they have.
5. Deadlines are at 6 pm local office time on the due day; a 1-day deadline is 24 hours from sending.

## `L-QUESTIONS.states` Question-set states

`queued (reviewer only) → sent → seen → partly_answered → answered`, with `overdue` as a flag on any state before `answered`, and `closed` when the idea is decided.

Contract: `A-API.questions`.

## `L-QUESTIONS.touchpoints` Where the front end depends on this

`S-R2`, `S-R3`, `S-06`, `S-08`, `S-03`, `S-H5`, `C-QCARD`
