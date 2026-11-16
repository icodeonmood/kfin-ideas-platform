---
id: C-SHEET-TEAMUP
title: Team up request sheet
rev: 1
status: baseline
source: reference/css/team-up-sheet.css
depends_on: [C-FIELD, C-DROPDOWN, C-BUTTON, C-PREVIEW]
last_delta: none
---

# C-SHEET-TEAMUP: Team up request sheet

One request sheet, the same on every screen that offers Team up: `S-03`, `S-05`, `S-06`, `S-09`, `S-H2` and their phone layouts.

## `C-SHEET-TEAMUP.compose` Step 1: write the request

Centred sheet (bottom sheet on phone), radius 28px.

1. Top row: the two avatars (you and the lead) overlapping; a close cross at the right ("Close without sending").
2. Title: "Team up with {lead}". Line: "{lead} leads "{their idea}" and decides who joins. Tell {lead} what you bring."
3. **"Your note to {lead}"**: a text area, 4 rows, pre-filled with a note drafted from the person's own idea. Under it a hint:
   - untouched: "We drafted this from your idea. Change anything you like."
   - under 30 characters: "Add a little more: at least 30 characters." (warning colour)
   - edited and long enough: "Looks good."
4. **"Bring your ideas along"** with "Optional": a dropdown, collapsed by default, nothing selected (`C-DROPDOWN`). The field reads "None picked". Opening it lists the person's own shared ideas as tick rows (title, then "IDEA-2026-001481, with the review desk"). Any number can be ticked. The field then reads the title, or "2 ideas picked".
5. A privacy line that follows the selection: "{lead} sees your name, your note." / "…and the idea you bring." / "…and the ideas you bring."
6. **One button**, bottom right: "Send to {lead}". Disabled while the note is under 30 characters; clicking it then focuses the note.

On Check it only, the sheet is opened from the person's unsent draft, so the choice is different and single: "Ask {lead} to merge mine in" ("{lead} decides. If {lead} accepts, yours joins that idea with credit to you. If not, you send yours on its own.") or "Keep mine separate" ("Team up, and send yours as its own idea") (`S-05.similar`, `L-MERGE.request`). Everything else is the same.

## `C-SHEET-TEAMUP.sent` Step 2: sent

The sheet changes in place: "Sent to {lead}". "{lead} reads your note, then approves or declines. You'll hear in your Inbox." The note is shown back under "Your note"; if ideas were brought: "Bringing "…" and "…"". Actions: "Withdraw request" (text) and one button to carry on ("Keep looking" on Find your crew, "Done" elsewhere). A spark burst marks the send.

## `C-SHEET-TEAMUP.after` After the sheet

| Outcome | What the opener shows |
|---|---|
| Waiting | "Waiting for {lead}" with "Withdraw" |
| Approved (team up only) | "You're on the crew. You'll get its updates." + "Say hello" (opens the conversation) |
| Approved (merged) | "Merged into IDEA-…, with credit to you." |
| Declined | The lead's reason if given; the person can send theirs on its own |
| Withdrawn | Back to "Team up" |

## `C-SHEET-TEAMUP.a11y` Accessibility

`role="dialog"`, `aria-modal`, labelled by the title and described by the line under it. Focus starts in the note with the cursor at the end. Escape and the backdrop close without sending; what was typed is kept if the sheet is reopened in the same session.

Rules and states: `L-TEAMUP`. Contract: `A-API.team-up`.

## `C-SHEET-TEAMUP.reference` Reference (generated)

- Source rules in the prototype: `reference/css/team-up-sheet.css` (classes: `.tusheet`, `.rq`)
- Resolved values as painted: `reference/computed/components.md`, section `C-SHEET-TEAMUP` (sheet, note field, dropdown)
- Used on: `S-03`, `S-05`, `S-06`, `S-09`, `S-H2`
