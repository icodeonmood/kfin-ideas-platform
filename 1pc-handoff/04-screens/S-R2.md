---
id: S-R2
title: The idea, for the reviewer
rev: 1
status: baseline
source: reference/prototype/DeskIdea.dc.html
depends_on: [C-SIDEBAR, C-LISTEN, C-WORTH, C-FILE, C-SIMGRID, C-PREVIEW, C-SHEET-MERGE, C-FIELD, C-FIELD-MSG, C-PILL, L-REVIEW, L-QUESTIONS, L-DECIDE, L-MERGE, L-WORTH, L-LISTEN, L-COMMITTEE]
last_delta: none
---

# S-R2: The idea, for the reviewer

**Route (proposed):** `/desk/ideas/:id`. **Boards:** `DeskIdea`

## `S-R2.purpose` Purpose

Everything a reviewer needs to decide on one idea, on one page. The main path is to decide. Asking the sharer first is optional.

## `S-R2.layout` Layout

1. "Review desk" back link.
2. **Heading block**, above both columns and as wide as the left column: status pill and reference; the title (`h1`, max 24ch); "Shared Saturday 14 November by Kavya Menon, Investor service, Hyderabad. Sorting confirmed by her: a problem to fix, Investor service, saves time and cost."
3. Two columns, 32px apart, starting on the same line: the idea (flexible) and the panel (440px). **The panel's top edge is level with the top of "Listen to the whole idea".**

## `S-R2.left` Left column, top to bottom

1. **Listen to the whole idea** (`C-LISTEN`).
2. **Attachments and artefacts** ("Everything that came with the idea"): rows with an icon, a title, a line and one action at the right: each file ("branch-call-log-nov.pdf. Attached by Kavya. 140 KB, 3 pages. A phone number on page 2 is hidden." → "Open"); "Her own words. As she wrote them on Saturday, before the draft. Folio hidden." → "Read"; "Similar ideas. 2 found while she wrote. She kept hers separate." → "Compare"; "Draft history. 3 versions. Title changed once, sorting confirmed." → "See changes". Files added with answers appear here too ("Added with her answers today. Folio hidden on both.").
3. **The idea, part by part**, one card with a section per part: The problem, How often, Who it affects, What it's worth, Attached, Fix. Each section has its text and, at its right, "Ask about this" (a small outline button; reads "Asking" in the warn style once a question is pinned to it). Under the text, by state: a draft question ("You'll ask" + the question, warn outline), an asked question ("You asked, today 11:20 am" + "Not answered yet" / "Answered"), and the answer ("Kavya answered, today 4:32 pm" + text + files).
4. **What it's worth** carries "Revise and recategorise" (`C-WORTH.edit`).
5. **Similar ideas** card: "The same problem, raised by others. Merge them so one team builds one fix." A list: title (opens the preview), "IDEA-2026-001412, Ravi Nair, Investor service, Hyderabad. 4 on its crew", the match line; at the right "Preview" (text) and "Merge" (line, small). After a merge: the green banner and a "Merged" pill (`C-SHEET-MERGE.after`).

## `S-R2.panel` The panel (right)

Sticky 96px from the top; max height = window height less 120px, capped at 820px; it scrolls on its own when taller; its bottom bar with the main button stays pinned at its bottom while the content scrolls; when the panel reaches its end the page scrolls on. It stays in view in every state.

1. **Reviewing** (default). Title "Review this idea". Line: "Clear enough? Decide now. If it's worth more than Kavya could put into numbers, revise what it's worth first. She sees your figures next to hers." A text link with a pencil, "Revise what it's worth", which opens the editor in the left column and scrolls to it; after a revision the line reads "You've revised what it's worth. Kavya sees your figures next to hers when you decide." and the link "Change what it's worth". Then a collapsed section "Ask Kavya first" marked "Optional". Bottom bar: one full-width primary, "Decide on this idea".
2. `S-R2.panel.ask` **Ask {sharer} first** (collapsed by default; opens on click, or when "Ask about this" is used on the left). Inside: "Only if something is unclear. Ask in your own words; each question is pinned to its part of the idea, so Kavya answers it right there." A question box ("What would you like to ask Kavya?") with a "Pinned to The problem" selector (guessed from the wording; a menu lists the six parts) and a round add button; Enter adds. "Your questions" with a count: each with its part tag and a remove cross. "Suggested from this idea": each with a plus and its part. "Time to answer": 1 day, 3 days, 1 week (single choice) and the deadline line. When at least one question is queued the section header shows "2 questions ready", and the bottom bar becomes: "Decide without asking" (text, left) and "Send 2 questions to Kavya" (primary, right).
3. **Sent, waiting.** Title "Waiting on Kavya". A countdown ("3 days to answer") and "Sent today, 11:20 am. Seen 12:05 pm." The questions, each "Not answered yet". Actions at the bottom right: "Give 2 more days" (text) and "Send a reminder" (line, small).
4. **Answered.** Title "All 3 answered". "Answered with 3 days to spare" and the time. The questions, each "Answered". Bottom bar: "Decide on this idea" (primary, full width); under it "Decide by Friday 20 November." and "Ask a follow-up" (line, small, right).
5. **Deciding.** Title "Decide on this idea". "Kavya reads your decision and your reason as soon as you send it." Three options as radio rows with a line each (`L-DECIDE.options`). Pick adds a toggle chip to join it with the similar idea; Not now adds "Look at it again in" 1 month / 3 months / 6 months and the return-date line. Then the reason field (label follows the choice), the counter, any error under it; a shield note about the Ones Committee's review; bottom bar "Back" (line, left) and "Send decision to Kavya" (primary, right).
6. **Decided.** Title "Decision sent to Kavya". The decision pill and "Today, 4:58 pm. She has it now."; for Not now, the return line; "Your reason, as Kavya reads it" quoted; "Ones Committee review": "Open, 30 days left", a progress bar, and "Open until Wednesday 16 December. The committee can extend it, up to 3 months in all, to Tuesday 16 February 2027. If they reverse it, Kavya gets their note and you see it here. When the window closes, the decision stands."

## `S-R2.states` States (board tweak `state`)

Reviewing (default); Asking Kavya (the Ask section open with 3 questions queued); Sent, waiting; Answered; Deciding; Decided; Merging (`C-SHEET-MERGE` open); Merged.

## `S-R2.rules` Rules

1. Working states and transitions: `L-REVIEW.panel`. "Decide without asking" goes to Deciding; "Back" from there returns to Reviewing (not to Answered) when nothing was asked.
2. Using "Ask about this" on a part queues that part's first suggested question and opens the Ask section.
3. Sending questions, a decision or a merge fires the spark burst once.
4. Focus moves to the panel's title on every state change.
5. Preview and merge pop-ups are mounted at the page root.
6. Field rules: `V-FIELDS.review`.
7. No phone board; on phone the panel follows the idea as a bottom sheet with the main button always visible. `NOT DRAWN:` default.

## `S-R2.reference` Reference (generated)

### Board `DeskIdea` (1440×2080)

- Canvas caption: R2 · The idea, for the reviewer: listen on the go, revise what it’s worth, then decide: Pick, Not now or Not picked, each with a reason. Asking the sharer first is optional and folded away. Or merge it with a similar idea and team the sharers up (tweak: state)
- Prototype: `reference/prototype/DeskIdea.dc.html`
- Exact copy and controls in every state: `reference/copy/DeskIdea.md`
- Board-specific CSS: `reference/css/boards/DeskIdea.css`
- Default screenshot: `reference/shots/DeskIdea.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `state` | Reviewing; Asking Kavya; Sent, waiting; Answered; Deciding; Decided; Merging; Merged | `DeskIdea__state-*.jpg` (7) |

Links out, as wired on the board: S-H5 (Inbox, 1 unread); S-R1 (Review desk, Search the desk, View all); S-H6 (Your profile and settings, Meera Iyer,)
