# Back-end logic

What the back end must do behind the screens: engines, rules, state machines and clocks. Each file says what must be true, not how to build it.

| ID | Title | File | Depends on |
|---|---|---|---|
| `L-AUDIT` | Permissions, audit trail, feature flags, configuration | `L-AUDIT.md` | E-ENTITIES |
| `L-AUTH` | Sign-in, session and keeping intent | `L-AUTH.md` | E-ENTITIES |
| `L-COMMITTEE` | The Ones Committee's window: view, extend, reverse | `L-COMMITTEE.md` | L-DECIDE, L-NOTIFY |
| `L-CONVO` | An idea's conversation | `L-CONVO.md` | L-INBOX, L-HIDE |
| `L-CREW` | Find your crew: what is suggested, in what order | `L-CREW.md` | L-SIMILAR, L-TEAMUP |
| `L-DECIDE` | Decisions: Pick, Not now, Not picked | `L-DECIDE.md` | L-COMMITTEE, L-NOTIFY, E-ENUMS |
| `L-DISPLAY` | Office screen and launch screen | `L-DISPLAY.md` | L-ONES |
| `L-DRAFT` | Building the draft from the person's words | `L-DRAFT.md` | L-HIDE, L-SORT, L-SIMILAR, E-ENTITIES |
| `L-HIDE` | Hiding customers' personal details | `L-HIDE.md` | E-ENTITIES |
| `L-IMPACT` | Measuring what a shipped idea changed | `L-IMPACT.md` | E-ENTITIES |
| `L-INBOX` | Inbox: one list of what waits on you and what changed | `L-INBOX.md` | L-NOTIFY, E-ENTITIES |
| `L-LISTEN` | Reading an idea aloud | `L-LISTEN.md` | L-HIDE |
| `L-MERGE` | Merging ideas | `L-MERGE.md` | L-TEAMUP, L-COMMITTEE, L-NOTIFY, E-ENTITIES |
| `L-NOTIFY` | Notifications outside the app: Teams and email | `L-NOTIFY.md` | L-INBOX |
| `L-ONES` | The Ones: numbers, tiers, points | `L-ONES.md` | L-IMPACT, E-ENTITIES |
| `L-QUESTIONS` | Questions from the review desk, and answers | `L-QUESTIONS.md` | L-NOTIFY, E-ENTITIES |
| `L-REVIEW` | The review desk's queue and working states | `L-REVIEW.md` | L-QUESTIONS, L-DECIDE, L-MERGE, E-ENUMS |
| `L-SEARCH` | Search and "ask in your own words" | `L-SEARCH.md` | E-ENTITIES |
| `L-SIMILAR` | Matching similar ideas | `L-SIMILAR.md` | E-ENTITIES |
| `L-SORT` | Sorting: suggested, then confirmed by the sharer | `L-SORT.md` | L-DRAFT, E-ENUMS |
| `L-SUBMIT` | Sending, the edit window, withdrawing and restoring | `L-SUBMIT.md` | L-SORT, L-HIDE, L-SIMILAR, E-ENTITIES |
| `L-TEAMUP` | Team up: asking to join a crew | `L-TEAMUP.md` | L-MERGE, L-NOTIFY, E-ENTITIES |
| `L-WALL` | The Wall: what everyone sees | `L-WALL.md` | L-ONES, L-IMPACT, E-ENTITIES |
| `L-WORTH` | What it's worth, and the reviewer's revision | `L-WORTH.md` | L-SORT, E-ENTITIES |
