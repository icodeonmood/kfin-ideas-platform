---
id: L-TEAMUP
title: Team up: asking to join a crew
rev: 1
status: baseline
source: reference/css/team-up-module.js
depends_on: [L-MERGE, L-NOTIFY, E-ENTITIES]
last_delta: none
---

# L-TEAMUP: Team up: asking to join a crew

## `L-TEAMUP.rules` Rules

1. Any employee can ask to team up on any shared idea that is not closed, withdrawn or merged away, and that they are not already on.
2. A request carries: a note to the lead (at least 30 characters; a first draft is generated from the requester's own closest idea and their role), and optionally one or more of the requester's own shared ideas "brought along". Nothing is selected by default.
3. The lead of the idea decides. Until then the requester sees "Waiting for {lead}" and can withdraw.
4. One open request per person per idea.
5. The lead receives it in their Inbox (`S-H2B`) with the note, and for each idea brought along a summary and "Open her idea". The lead has three answers:

| Answer | Effect |
|---|---|
| **Merge it** (only when an idea was brought) | The requester joins the crew, and the brought idea merges into the lead's (`L-MERGE.effects`) |
| **Team up only** | The requester joins the crew; any brought idea stays separate |
| **Decline** | Nothing changes. An optional reason goes to the requester ("The crew is full for now") |

6. With no idea brought, the answers are Approve (= team up only) and Decline.
7. The requester is told in their Inbox at once: "Ravi Nair approved your team-up request", or the decline with its reason.
8. Joining a crew gives: the idea's conversation, its updates in the Inbox, a place in "Teamed up" on My ideas, and the option to join the build if it is picked.
9. The lead's result screen says what happened and offers "Say hello to {requester}" (opens the conversation): "Merged. Kavya's idea is now part of yours, and she is on your crew, credited. We've told her." / "Teamed up. Kavya is on your crew. Her idea stays separate, and she sends it on its own. We've told her." / "Declined. Kavya sees your reason: "…". She can send hers on its own."
10. A crew has one lead (the sharer). If ideas merge, the lead of the surviving idea leads.
11. Leaving a crew: `NOT DRAWN:` default: a member can leave from the idea's page; the lead can remove a member; both are logged and announced in the conversation.
12. Crew size is shown everywhere as "N colleagues on it" (including the lead) or "{lead} and N others on it".

## `L-TEAMUP.states` Request states

`composing → sent (waiting) → approved_merged | approved_team_only | declined | withdrawn`, plus `closed` if the idea is withdrawn, closed or merged away first.

Contract: `A-API.team-up`.

## `L-TEAMUP.touchpoints` Where the front end depends on this

`S-03`, `S-06`, `S-09`, `S-H2`, `S-H2B`, `C-SHEET-TEAMUP`
