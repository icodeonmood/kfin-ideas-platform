---
id: S-R3
title: Answer the review desk
rev: 1
status: baseline
source: reference/prototype/Answer.dc.html
depends_on: [C-TASKBAR, C-FIELD, C-FILE, C-PROMPT, C-FIELD-MSG, L-QUESTIONS, L-HIDE]
last_delta: none
---

# S-R3: Answer the review desk

**Route (proposed):** `/ideas/:id/answer`. **Boards:** `Answer`, `PhoneAnswer`

## `S-R3.purpose` Purpose

The only place questions from the review desk are answered: one question at a time, typed or spoken, each answer going to its part of the idea.

## `S-R3.layout` Layout

1. **Review bar** at the top: "Answer the review desk"; "Meera from the review desk has 3 questions about "{idea title}". Answer them one at a time. Skip any you can't answer yet and come back before you send."; the countdown ("3 days left to answer", or "07:38 left to answer") and deadline ("Answer by Thursday 19 November, 6 pm" / "Answer by 7 pm today").
2. **Steps**: "Question 1", "Question 2", "Question 3", "Check and send", with a progress line "1 of 3 answered". Answered steps show a tick; any step can be opened.
3. **One question in a glass sheet**: who asked and when; "Added to" and the part name; the question as the heading; the answer box ("Your answer to question 2") with speak and attach; the hint "Press Enter to go on. Shift + Enter adds a new line."; at the bottom right "Back" and "Skip for now" (which becomes "Next" once there is text).

## `S-R3.states` States (board tweak `state`)

| State | Shows |
|---|---|
| Answering | As above |
| Checking | "Check your answers": each question with its part, the answer or "Not answered. It stays open until the deadline.", and "Change". Bottom right: "Send 1 answer to Meera" (the count follows) |
| Sent | "Sent. 3 of 3 answered. Sent to Meera, 4:32 pm." "Answered with 3 days to spare." "Your answers are with the review desk. Each answer is added to its part of your idea and posted in your conversation with the review desk. Meera decides by Friday 20 November, and her decision comes to your Inbox." The answers listed, read-only. A link back to the idea |

## `S-R3.rules` Rules

1. Rules: `L-QUESTIONS.answer`. Answers autosave as typed.
2. Moving between questions slides forward and back; Enter advances.
3. Files attached to an answer follow `C-FILE.row`; a file with personal data blocks sending until hidden or removed.
4. Sending with nothing answered is not possible: the button is disabled and reads "Answer at least one question".  `NOT DRAWN:` wording.
5. Phone: the compact bar ("Home" back, "Answer"), the same steps as a progress row, the question sheet filling the screen, and the forward button in the dock.

## `S-R3.reference` Reference (generated)

### Board `Answer` (1440×1100)

- Canvas caption: R3 · Kavya answers one question at a time, sees which part of her idea each answer goes to, checks her answers, then sends (tweaks: state, time to answer)
- Prototype: `reference/prototype/Answer.dc.html`
- Exact copy and controls in every state: `reference/copy/Answer.md`
- Board-specific CSS: `reference/css/boards/Answer.css`
- Default screenshot: `reference/shots/Answer.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `state` | Answering; Checking; Sent | `Answer__state-*.jpg` (2) |
| `timeToAnswer` | 3 days left; Under a day | `Answer__timetoanswer-*.jpg` (1) |

Links out, as wired on the board: S-08 (See the conversation); S-06 (See your idea)

### Board `PhoneAnswer` (390×844)

- Canvas caption: Answer: one question at a time, typed or spoken; each answer names the part of your idea it goes to (tweaks: state, time to answer)
- Prototype: `reference/prototype/PhoneAnswer.dc.html`
- Exact copy and controls in every state: `reference/copy/PhoneAnswer.md`
- Board-specific CSS: `reference/css/boards/PhoneAnswer.css`
- Default screenshot: `reference/shots/PhoneAnswer.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `state` | Answering; Checking; Sent | `PhoneAnswer__state-*.jpg` (2) |
| `timeToAnswer` | 3 days left; Under a day | `PhoneAnswer__timetoanswer-*.jpg` (1) |

Links out, as wired on the board: S-08 (See the conversation); S-06 (See your idea)
