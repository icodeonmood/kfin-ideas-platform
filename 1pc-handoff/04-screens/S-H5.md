---
id: S-H5
title: Inbox
rev: 1
status: baseline
source: reference/prototype/Inbox.dc.html
depends_on: [C-SIDEBAR, C-TABS, C-INBOX-READER, C-QCARD, L-INBOX]
last_delta: none
---

# S-H5: Inbox

**Route (proposed):** `/inbox`. **Boards:** `Inbox`, `PhoneInbox`

## `S-H5.purpose` Purpose

The one list of what waits on the person and what changed.

## `S-H5.layout` Layout

A full-height mail reader (`C-INBOX-READER`) in two panes beside the sidebar. **List pane**: the title "Inbox" with the unread line ("2 unread") and a mark-all-read icon; a search field ("Search your inbox"); the tabs All 9, Needs you 3, Unread 2, Archived 0; then the list grouped Today / This week / Earlier, the open row as a white card. **Reader pane**: a top row with archive and mark-unread icons at the left and the position ("1 of 9") with up and down arrows at the right; the item; and a foot row pinned to the bottom with the actions at the right.

## `S-H5.states` States (board tweak `filter`)

All; Needs you ("1 of 3"); Unread ("1 of 2"); Archived (empty: "Nothing here." in the list and "Pick something on the left to read it here." in the reader).

## `S-H5.rules` Rules

1. Item kinds, their row text and actions: `L-INBOX.kinds`. Counts: `L-INBOX.rules/1–3`.
2. The first item of the tab is open by default on desktop. Arrow keys move through the list; Enter opens.
3. The reader's forward action is a primary button at its bottom right; "Open the conversation" is a line button to its left.
4. Opening an item marks it read and updates every count at once.
5. New items arrive live at the top of Today with one soft wash.
6. Phone: the list is the screen (tabs as a sideways row, tab bar at the bottom); an item opens as its own screen with the compact bar and its action in the dock.

## `S-H5.reference` Reference (generated)

### Board `Inbox` (1440×1000)

- Canvas caption: H5 · Inbox: the one list of what waits on you and what changed; Needs you is its tab (tweak: filter)
- Prototype: `reference/prototype/Inbox.dc.html`
- Exact copy and controls in every state: `reference/copy/Inbox.md`
- Board-specific CSS: `reference/css/boards/Inbox.css`
- Default screenshot: `reference/shots/Inbox.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `filter` | All; Needs you; Unread; Archived | `Inbox__filter-*.jpg` (3) |

Links out, as wired on the board: S-08 (Open the conversation); S-R3 (Answer the questions)

### Board `PhoneInbox` (390×844)

- Canvas caption: Inbox: every update in one place, grouped by when (tweak: filter)
- Prototype: `reference/prototype/PhoneInbox.dc.html`
- Exact copy and controls in every state: `reference/copy/PhoneInbox.md`
- Board-specific CSS: `reference/css/boards/PhoneInbox.css`
- Default screenshot: `reference/shots/PhoneInbox.jpg`

| Tweak | Options (default first) | Screenshots |
|---|---|---|
| `filter` | All; Needs you; Unread; Archived | `PhoneInbox__filter-*.jpg` (3) |

Links out, as wired on the board: S-03 (1% Club); S-R3 (MI Meera from the review desk asked yo); S-09 (RN Ravi Nair approved your team-up req); S-08 (AR Arjun Rao asked you to check new me, SP Sanjay Pillai mentioned you No scri); S-04B (1% 1% Club kept your draft from your p); S-07 (My ideas, RM Rohan Mehta from the Ones Committee); S-06 (1% 1% Club moved your idea to Being bu, MI Meera from the review desk didn’t p, MI Meera from the review desk picked y); S-04 (Share a problem); S-WALL (Wall)
