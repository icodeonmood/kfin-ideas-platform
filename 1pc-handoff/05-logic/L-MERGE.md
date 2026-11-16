---
id: L-MERGE
title: Merging ideas
rev: 1
status: baseline
source: reference/copy/DeskIdea.md
depends_on: [L-TEAMUP, L-COMMITTEE, L-NOTIFY, E-ENTITIES]
last_delta: none
---

# L-MERGE: Merging ideas

Two ideas about the same problem become one, with credit to both sharers. There are two ways in.

## `L-MERGE.request` A sharer asks, before sending (Check it)

1. On Check it's "Similar ideas" part, the sharer can open the team-up sheet from their unsent draft and choose "Ask {lead} to merge mine in" or "Keep mine separate".
2. Merging is always a request. Only the other idea's lead can accept. The sharer cannot merge unilaterally.
3. The request carries the note and a masked summary of the draft. The draft is not shared with anyone else by this.
4. While the request is waiting, the draft is held: the Similar ideas part reads "Waiting on {lead} to merge", the bar under the steps says "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own." with "Withdraw the request", and Submit is unavailable.
5. **Accepted**: "Merged into IDEA-2026-001412. Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send." The button becomes "See the merged idea". The draft is closed as merged.
6. **Team up only** (the lead's middle answer): the sharer joins the crew and their draft stays theirs, ready to send on its own.
7. **Declined**: the lead's reason shows ("Ravi kept that idea separate: "Mine is about the SMS wording, yours is about the calls it causes. Better as two." Send yours on its own."). The button becomes "Send mine on its own" (individual filing).
8. Withdrawing the request returns the draft to normal.
9. `NOT DRAWN:` a request unanswered after 3 working days: the sharer is offered "Send mine on its own" without waiting; the request stays open for the lead.

## `L-MERGE.desk` The review desk merges (forced team-up)

1. From the reviewer's idea page, any listed similar idea can be merged with the one being reviewed (`C-SHEET-MERGE`).
2. The reviewer chooses which idea leads (default: the one shared first; if equal, the larger crew), whether to "Team them up" (default yes: the other sharer joins the lead's crew without a request), and writes a note to both (at least 20 characters).
3. No consent is needed from either sharer. Both are told at once in their Inbox, with the note.
4. The Ones Committee sees the merge for 30 days and can reverse it (`L-COMMITTEE`, same window rules). `OPEN:` `P-DECISIONS.open/7`.
5. A reviewer can merge at any working state before a decision is sent, and can merge as part of a Pick ("joined it with IDEA-2026-001412 from Hyderabad, so one team builds one fix").

## `L-MERGE.effects` What a merge does

1. One idea survives (the lead idea) with its reference; the other is marked `merged` and points to it. The merged idea's page shows where it went and stays readable by its sharer.
2. Both sharers are credited on the surviving idea ("with credit to you"); credit carries through to the Wall and to becoming a One.
3. The merged idea's words, facts, answers and files are attached to the surviving idea as a contribution, labelled with their sharer.
4. The merged idea's crew joins the surviving idea's crew (when "Team them up" is on, or always for a lead-accepted merge).
5. From then on the review desk decides on one idea. Any open question set on the merged idea closes.
6. Both conversations stay; the merged one gets a closing line with a link.
7. Reversal (committee, desk merges only): the merged idea is restored to its previous status with its own crew; crew joins made by the merge are undone; both sharers get the note.

## `L-MERGE.states` States

Draft merge request: `none → waiting → accepted | team_only | declined | withdrawn`. Idea: `… → merged (into: id)`, reversible to its prior status within the window.

## `L-MERGE.touchpoints` Where the front end depends on this

`S-05`, `S-H2B`, `S-R2`, `C-SHEET-MERGE`
