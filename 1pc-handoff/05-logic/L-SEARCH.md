---
id: L-SEARCH
title: Search and "ask in your own words"
rev: 1
status: baseline
source: reference/copy/MyIdeas.md
depends_on: [E-ENTITIES]
last_delta: none
---

# L-SEARCH: Search and "ask in your own words"

1. `L-SEARCH/1` Scope is always the list the person is on and what they are allowed to see: My ideas searches their own and teamed-up ideas; the desk searches the desk's queues.
2. `L-SEARCH/2` Search is by meaning across: titles, summaries, the person's own words (their own only), text extracted from their files, and the review desk's notes and reasons. It never searches hidden details.
3. `L-SEARCH/3` A result set comes with one plain sentence saying what was found and the closest hit, and a second saying what it matched on. Rows show a matching snippet.
4. `L-SEARCH/4` A question is interpreted into filters where possible ("Which of my ideas need me this week?" → the Needs you filter) and answered in one sentence with the facts from the list; the applied filter is shown and removable.
5. `L-SEARCH/5` Suggestions when the bar is focused: the filters with live counts, and three example questions relevant to the person's ideas.
6. `L-SEARCH/6` Latency target: first results within 500ms for filters and titles; the sentence may follow. No blocking state.
7. `L-SEARCH/7` No result: the filtered-to-nothing empty state with "Show all ideas".

## `L-SEARCH.touchpoints` Where the front end depends on this

`S-07`, `S-R1`, `C-SEARCH`
