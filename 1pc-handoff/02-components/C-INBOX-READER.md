---
id: C-INBOX-READER
title: Inbox: list and reader
rev: 1
status: baseline
source: reference/css/boards/Inbox.css
depends_on: [C-TABS, C-AVATAR, C-QCARD]
last_delta: none
---

# C-INBOX-READER: Inbox: list and reader

## `C-INBOX-READER.layout` Layout

Desktop: a full-height mail reader. Left, the list (grouped "Today", "This week", "Earlier"); right, the open item. Phone: the list is the screen; an item opens as its own screen with a compact bar.

## `C-INBOX-READER.row` A row

Sender avatar (a person's initials, or the mark for the system), sender ("Meera from the review desk"), time ("11:20 am", "Sun, 15 Nov", "2 Nov"), the idea's title, what happened in a few words ("asked you 3 questions", "approved your team-up request", "kept your draft from your phone", "reversed a decision on your idea", "mentioned you", "picked your idea"), and, if it waits on the person, a countdown ("3 days left", "By Thu, 19 Nov"). Unread rows are weight 500 with a blue dot.

## `C-INBOX-READER.reader` The reader

Header: position ("1 of 9") with previous and next; the item's kind ("Questions from the review desk", "Merge request"); sender and time. Body: the content for that kind (a `C-QCARD`, a note, a decision with its reason, a merge request with its three answers). Footer, pinned to the bottom of the reader: the item's actions at the right, the forward one last as a primary button ("Answer the questions"), with "Open the conversation" as a line button before it.

Opening an item marks it read. Archive is in a "More" menu. Empty: "Nothing here." and, in the reader, "Pick something on the left to read it here."

Item kinds and their actions: `L-INBOX.kinds`.

## `C-INBOX-READER.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Inbox.css` (classes: `.mmsg`)
- Used on: `S-H2B`, `S-H5`
