---
id: L-REVIEW
title: The review desk's queue and working states
rev: 1
status: baseline
source: reference/copy/Desk.md
depends_on: [L-QUESTIONS, L-DECIDE, L-MERGE, E-ENUMS]
last_delta: none
---

# L-REVIEW: The review desk's queue and working states

## `L-REVIEW.queue` The queue (`S-R1`)

Four tabs, each a filter over ideas routed to the reviewer's queues:

| Tab | Holds | Row shows |
|---|---|---|
| To review | Shared, not yet opened or opened with nothing asked | "No questions asked", days left to decide ("6 days to decide"), decide-by date, "Open" |
| Waiting on the sharer | A question set is out | Answered count and seen time, time left to answer, decide-by date, "Open"; overdue rows offer "Remind {sharer}" |
| Answered, back to you | All or some answers arrived | "Both answered, 1 hour ago", days left to decide, "Read answers" |
| Decided this week | Decided in the last 7 days | The decision and date, the committee's window ("Ones Committee can review it until Wednesday 2 December"), or "Reversed: picked" with what the committee did |

The header line summarises what needs attention: "3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back with you."

Sort: Time left (default), Decide by, Area. Search works as `L-SEARCH` scoped to the desk.

## `L-REVIEW.open` Opening an idea

1. The first time any reviewer opens an idea, it is "opened": the sharer's edit window closes (`L-SUBMIT.edit/5`), the conversation records "Meera from the review desk opened it. Monday 16 November, 9:50 am", and the idea is assigned to that reviewer.
2. The reviewer sees: the summary and each part with answers under it; attachments and artefacts (files with what was hidden, "Her own words", "Similar ideas" with whether she kept hers separate, "Draft history"); the listen player (`L-LISTEN`); what it's worth with "Revise and recategorise" (`L-WORTH`); similar ideas with Preview and Merge (`L-MERGE.desk`).
3. Reviewers see the sharer's own words (masked). They never see unmasked hidden details.

## `L-REVIEW.panel` The reviewer's working states (`S-R2` panel)

| State | Meaning | Main action |
|---|---|---|
| Reviewing (default) | Nothing asked | "Decide on this idea". Optional: revise worth; open "Ask {sharer} first" |
| Asking | Questions queued, not sent | "Send N questions to {sharer}"; or "Decide without asking" |
| Sent, waiting | A set is out | "Give 2 more days", "Send a reminder" |
| Answered | Answers are in | "Decide on this idea"; or "Ask a follow-up" |
| Deciding | Choosing Pick / Not now / Not picked and writing the reason | "Send decision to {sharer}"; "Back" |
| Decided | Sent | Shows the decision, the reason as the sharer reads it, and the committee's window |
| Merging / Merged | The merge sheet is open / done | `C-SHEET-MERGE` |

Transitions: `reviewing → asking → sent → answered → deciding → decided`; `reviewing → deciding` directly; `asking → deciding` ("Decide without asking" discards nothing: queued questions are kept as unsent until the decision is sent, then dropped); `answered → asking` (follow-up); `deciding → back` returns to where the reviewer came from (`reviewing` or `answered`).

## `L-REVIEW.clock` The decision clock

1. Decide-by = 5 working days after sharing. Shown as a date and as days left.
2. Asking questions does not pause the clock. If the answer deadline is after decide-by, the reviewer is warned (`L-QUESTIONS.ask/4`) and may move the decide-by date, which tells the sharer the new date.
3. An idea past decide-by is flagged to the review desk lead. `NOT DRAWN:` default: a daily digest to the lead; no automatic decision.

## `L-REVIEW.touchpoints` Where the front end depends on this

`S-R1`, `S-R2`
