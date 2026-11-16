# Screens

One file per screen; desktop and phone together. Routes and the navigation graph are in `00-overview/ROUTES.md`.

| ID | Title | File | Depends on |
|---|---|---|---|
| `S-01` | Landing | `S-01.md` | C-BUTTON, C-TRACK, C-CARD, L-AUTH, F-MOTION |
| `S-02` | Sign in | `S-02.md` | C-FIELD, C-FIELD-MSG, C-BUTTON, L-AUTH |
| `S-03` | Home | `S-03.md` | C-SIDEBAR, C-PROMPT, C-QCARD, C-ONES-FAN, C-CREW-DECK, C-SHEET-TEAMUP, C-EMPTY, L-INBOX, L-CREW, L-ONES, L-DRAFT |
| `S-04` | Tell it (a new problem) | `S-04.md` | C-SIDEBAR, C-TASKBAR, C-PROMPT, C-DRAFT-PANEL, C-DRAFT-LOADER, C-HIDDEN, L-DRAFT, L-HIDE |
| `S-04B` | Tell it: the conversation (from Home, or a saved draft) | `S-04B.md` | C-SIDEBAR, C-TASKBAR, C-PROMPT, C-DRAFT-PANEL, C-DRAFT-LOADER, C-HIDDEN, C-FILE, L-DRAFT, L-HIDE, L-SIMILAR |
| `S-05` | Check it, then send it | `S-05.md` | C-SIDEBAR, C-TASKBAR, C-CHIP, C-HIDDEN, C-SIMGRID, C-PREVIEW, C-SHEET-TEAMUP, C-FILE, C-WORTH, C-FIELD-MSG, L-SORT, L-SIMILAR, L-MERGE, L-SUBMIT, L-HIDE |
| `S-06` | Status: your idea's page | `S-06.md` | C-SIDEBAR, C-TRACK, C-PILL, C-HIDDEN, C-FILE, C-QCARD, C-SIMGRID, C-PREVIEW, C-SHEET-TEAMUP, C-WORTH, L-SUBMIT, L-QUESTIONS, L-DECIDE, L-COMMITTEE, L-CONVO |
| `S-06B` | Edit after sharing | `S-06B.md` | C-TASKBAR, C-CHIP, C-HIDDEN, C-FILE, C-WORTH, C-FIELD-MSG, L-SUBMIT, L-SORT, L-HIDE |
| `S-07` | My ideas | `S-07.md` | C-SIDEBAR, C-SEARCH, C-TABS, C-SORTS, C-PILL, C-EMPTY, C-SKELETON, L-SEARCH |
| `S-08` | An idea's conversation | `S-08.md` | C-SIDEBAR, C-QCARD, C-FILE, C-AVATAR, C-FIELD-MSG, L-CONVO, L-QUESTIONS |
| `S-09` | A colleague's idea | `S-09.md` | C-SIDEBAR, C-TRACK, C-PILL, C-AVATAR, C-SHEET-TEAMUP, L-TEAMUP |
| `S-H2` | Find your crew | `S-H2.md` | C-SIDEBAR, C-CREW-DECK, C-SHEET-TEAMUP, C-CHIP, C-EMPTY, L-CREW, L-TEAMUP |
| `S-H2B` | A team-up or merge request, in the lead's Inbox | `S-H2B.md` | C-SIDEBAR, C-INBOX-READER, C-BUTTON, L-TEAMUP, L-MERGE, L-INBOX |
| `S-H3` | Share another way | `S-H3.md` | C-SIDEBAR, C-CARD, C-PILL, L-DRAFT, L-NOTIFY |
| `S-H4` | What happens after you share | `S-H4.md` | C-SIDEBAR, C-TRACK, C-BUTTON |
| `S-H5` | Inbox | `S-H5.md` | C-SIDEBAR, C-TABS, C-INBOX-READER, C-QCARD, L-INBOX |
| `S-H6` | Profile and settings | `S-H6.md` | C-SIDEBAR, C-AVATAR, C-CARD, L-ONES, L-NOTIFY |
| `S-LAUNCH` | Launch screen (inauguration) | `S-LAUNCH.md` | L-DISPLAY |
| `S-OFFICE` | Office screen (wall display) | `S-OFFICE.md` | L-DISPLAY, L-ONES |
| `S-ONE` | A One's dashboard | `S-ONE.md` | C-SIDEBAR, C-CARD, C-FIELD, L-ONES, L-IMPACT |
| `S-R1` | Review desk | `S-R1.md` | C-SIDEBAR, C-SEARCH, C-TABS, C-SORTS, C-PILL, L-REVIEW, L-QUESTIONS |
| `S-R2` | The idea, for the reviewer | `S-R2.md` | C-SIDEBAR, C-LISTEN, C-WORTH, C-FILE, C-SIMGRID, C-PREVIEW, C-SHEET-MERGE, C-FIELD, C-FIELD-MSG, C-PILL, L-REVIEW, L-QUESTIONS, L-DECIDE, L-MERGE, L-WORTH, L-LISTEN, L-COMMITTEE |
| `S-R3` | Answer the review desk | `S-R3.md` | C-TASKBAR, C-FIELD, C-FILE, C-PROMPT, C-FIELD-MSG, L-QUESTIONS, L-HIDE |
| `S-R4` | Ones Committee | `S-R4.md` | C-SIDEBAR, C-TABS, C-SORTS, C-PILL, C-FIELD, C-FIELD-MSG, L-COMMITTEE |
| `S-WALL` | The Wall | `S-WALL.md` | C-SIDEBAR, C-CHIP, C-SORTS, C-PILL, C-CARD, L-WALL, L-ONES, L-IMPACT |
