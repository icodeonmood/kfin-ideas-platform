---
id: L-INBOX
title: Inbox: one list of what waits on you and what changed
rev: 1
status: baseline
source: reference/copy/Inbox.md
depends_on: [L-NOTIFY, E-ENTITIES]
last_delta: none
---

# L-INBOX: Inbox: one list of what waits on you and what changed

## `L-INBOX.rules` Rules

1. The Inbox is the only list of notifications and requests. Home shows its top two "Needs you" items with "All N in Inbox". The sidebar and tab-bar count is the number of unread items. All three always agree.
2. Tabs: All, Needs you, Unread, Archived, each with a count.
3. An item is **unread** until opened in the reader. An item **needs you** while its action is outstanding; it leaves "Needs you" when the action is done (answers sent, request answered, check completed), whether or not it was done from the Inbox.
4. Items are grouped by time: Today, This week, Earlier. Newest first.
5. Archiving hides an item from All; it cannot archive an item that still needs the person.
6. Each item links to its idea's conversation ("Open the conversation").

## `L-INBOX.kinds` Item kinds

| Kind | Who gets it | Row reads | Needs you? | Reader action |
|---|---|---|---|---|
| Questions from the review desk | Sharer | "asked you 3 questions" + countdown | Yes, until answered | "Answer the questions" → `S-R3` |
| Team-up or merge request | Lead | "asks to team up and merge her idea into yours" | Yes | Decline / Team up only / Merge it (`S-H2B`) |
| Request answered | Requester | "approved your team-up request" / declined with reason | No | Open the idea / "Say hello" |
| Decision | Sharer, crew | "picked your idea" / "didn't pick your idea, with a reason" / "Not now" | No | Read the decision → `S-06` |
| Decision reversed | Sharer, crew, the reviewer | "reversed a decision on your idea" | No | Read the note → `S-06` |
| Ideas merged by the desk (`NOT DRAWN:` row text) | Both sharers | "merged your idea with Ravi's" | No | Open the idea |
| Worth revised (`NOT DRAWN:` row text) | Sharer | "revised what your idea is worth" | No | Open the idea |
| Stage moved | Sharer, crew | "moved your idea to Being built" (sender: the system, shown with the mark) | No | Open the idea |
| A build team asks | Sharer, crew | "asked you to check new messages" + "By Thu, 19 Nov" | Yes, until done | Opens the conversation |
| Mention | The person mentioned | "mentioned you" | No | Opens the conversation at the message |
| Joined your crew | Lead | "joined your crew" | No | Open the idea |
| Comment on your idea | Sharer | "commented on your idea" | No | Opens the conversation |
| Draft kept | The person | "kept your draft from your phone" / from email / from Teams | No | "Carry on" → `S-04B` |
| Sent to the review desk | Sharer | "sent your idea to the review desk" | No | Open the idea |
| Answer reminder (`NOT DRAWN:` row text) | Sharer | "1 day left to answer Meera's questions" | Yes | "Answer the questions" |

Sender display: a person's name with their role where it matters ("Meera from the review desk", "Rohan Mehta from the Ones Committee"); the system shows as "1%" with the mark.

Contract: `A-API.inbox`.

## `L-INBOX.touchpoints` Where the front end depends on this

`S-H5`, `S-H2B`, `S-03`, `C-INBOX-READER`, `C-SIDEBAR`
