---
id: J-BROWSE
title: Browse, open, come back to the same place
rev: 1
status: baseline
source: reference/prototype/MyIdeas.dc.html
depends_on: [S-07, S-WALL, S-09, S-06, S-R1, S-H5]
last_delta: none
---

# J-BROWSE: Browse, open, come back to the same place

| # | What the person does | What must be true |
|---|---|---|
| 1 | On My ideas: picks a tab, a filter, a sort, maybe a search; scrolls | The state is in the URL |
| 2 | Opens a row | Grow-from-row hand-over to the idea |
| 3 | Presses Back (browser or the page's own link) | The same tab, filter, sort, search and scroll position; the opened row is highlighted once and has focus; "Back where you were: Yours." |
| 4 | Same on the Review desk and the Inbox | Tab, sort, search and the open item are restored |
| 5 | From the Wall, opens an idea | The idea's Back link says "Back to the Wall" and returns to the same scroll position and sort |
| 6 | Shares a link to a filtered list | Opening it reproduces the view (for what that person is allowed to see) |

Rules: `S-07.return`, `P-ROUTES.state`. Acceptance: `V-ACC.browse`.

## `J-BROWSE.boards` Boards to walk on the canvas

`MyIdeas`, `Wall`, `Idea`
