---
id: L-SIMILAR
title: Matching similar ideas
rev: 1
status: baseline
source: reference/copy/Review.md
depends_on: [E-ENTITIES]
last_delta: none
---

# L-SIMILAR: Matching similar ideas

## `L-SIMILAR.rules` Rules

1. Matching runs on the masked summary, title, sorting and the person's masked words, against every shared idea that is not withdrawn, plus ideas merged into others (which resolve to the surviving idea).
2. Matching is by meaning, not keywords. Each match has a strength: `close` ("Close match: same SMS, same calls") or `related` ("Related: the calls you describe"), and a one-line reason written in plain words that names what is shared.
3. Return at most 8, closest first; `close` before `related`. The person's own ideas are excluded.
4. It first runs as one of the six draft parts and re-runs when the summary changes materially. The result is stored with the draft so Check it does not wait.
5. After sharing, matching runs again as part of "Checked and matched"; the count shows on the stage track ("2 similar ideas found") and the matches show on the sharer's Status page and to the reviewer.
6. New ideas shared later can match an existing idea: the existing idea's sharer sees them under "Colleagues on something similar", and the reviewer under "Similar ideas".
7. What the sharer can do with a match before sending: Preview it; ask its lead to merge theirs in (`L-MERGE.request`); or keep theirs separate. After sending: Team up (`L-TEAMUP`), optionally bringing ideas along.
8. "Keep mine separate" is recorded and shown to the reviewer: "2 found while she wrote. She kept hers separate."
9. `L-SIMILAR.failure` If matching fails, sharing is not blocked: Check it shows "Couldn't check for similar ideas. The review desk will." and matching is retried after sharing.
10. Each preview needs, for the other idea: status, reference, title, area, city, lead, crew (names and count), "the problem, in their words" (a one-sentence masked quote), "they're looking for", and for reviewers the comparison facts (how often, who, worth).

Flag S2 ("Check first"): when the top match is `close`, Check it opens on the comparison before the other parts.

## `L-SIMILAR.touchpoints` Where the front end depends on this

`S-04B`, `S-05`, `S-06`, `S-R2`, `S-H2`, `C-SIMGRID`
