---
id: S-H2B
title: A team-up or merge request, in the lead's Inbox
rev: 1
status: baseline
source: reference/prototype/CrewRequest.dc.html
depends_on: [C-SIDEBAR, C-INBOX-READER, C-BUTTON, L-TEAMUP, L-MERGE, L-INBOX]
last_delta: none
---

# S-H2B: A team-up or merge request, in the lead's Inbox

**Route (proposed):** `/inbox/:itemId`. **Boards:** `CrewRequest`

## `S-H2B.purpose` Purpose

What the lead of an idea sees when a colleague asks to team up, and their three answers. It is the Inbox (`S-H5`) with a request item open; the signed-in person here is the lead (Ravi).

## `S-H2B.reader` The reader for this item

1. Kind: "Merge request" (or "Team-up request" when no idea is brought). The lead's idea title. "Kavya Menon asks to team up and merge her idea into yours", "Just now".
2. **Her note**, in full.
3. **The idea she asks you to merge into yours**: its status pill; "Kavya Menon, Investor service, Hyderabad. Shared Saturday."; a one-paragraph summary; "Open her idea".
4. An explanation of the three answers: "Merge it, and her idea joins yours: she is on your crew and credited on it. Team up only puts her on your crew and keeps her idea separate. Decline, and she sends hers on its own, with your reason if you give one."
5. Three buttons in one row at the bottom right, in this order: "Decline" (text), "Team up only" (line), "Merge it" (primary).

## `S-H2B.states` States (board tweak `state`)

| State | Reader shows |
|---|---|
| Waiting | As above |
| Merged | "Merged. Kavya's idea is now part of yours, and she is on your crew, credited. We've told her." + "Say hello to Kavya" |
| Teamed up only | "Teamed up. Kavya is on your crew. Her idea stays separate, and she sends it on its own. We've told her." + "Say hello to Kavya" |
| Declined | "Declined. Kavya sees your reason: "The crew is full for now". She can send hers on its own." + "Next" (opens the next Inbox item) |

## `S-H2B.rules` Rules

1. "Decline" opens an optional reason field in place before confirming ("Tell Kavya why, if you like") with "Decline the request" at the bottom right. `NOT DRAWN:` the field; the outcome text is drawn.
2. No Undo. The result is shown in place and the item leaves "Needs you".
3. With no idea brought, the buttons are "Decline" and "Approve".
4. Rules: `L-TEAMUP.rules/5–9`, `L-MERGE.effects`.

## `S-H2B.reference` Reference (generated)

### Board `CrewRequest` (1440×1000)

- Canvas caption: H2b · Ravi gets Kavya’s request in his Inbox: her note and the idea she asks him to merge into his; Merge it, Team up only, or Decline with an optional reason (tweak: state)
- Prototype: `reference/prototype/CrewRequest.dc.html`
- Exact copy and controls in every state: `reference/copy/CrewRequest.md`
- Board-specific CSS: `reference/css/boards/CrewRequest.css`
- Default screenshot: `reference/shots/CrewRequest.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `state` | Waiting; Merged; Teamed up only; Declined | `CrewRequest__state-*.jpg` (3) |

Links out, as wired on the board: S-09 (Rejection SMS codes confuse investors, With the review desk Investors call to); S-H6 (Your profile and settings, Ravi Nair, ); S-08 (Say hello to Kavya)
