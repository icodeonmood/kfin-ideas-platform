---
id: L-WORTH
title: What it's worth, and the reviewer's revision
rev: 1
status: baseline
source: reference/copy/DeskIdea.md
depends_on: [L-SORT, E-ENTITIES]
last_delta: none
---

# L-WORTH: What it's worth, and the reviewer's revision

1. `L-WORTH/1` The sharer's side captures worth loosely: "What it would bring" (multi-choice) and, inside the optional fix, a rough size as free text or a range ("70 to 150 hours a month", "about ₹25,000 a month saved"). The system reads figures back in a normal form and the sharer confirms ("70 to 150 hours a month. Is that right?").
2. `L-WORTH/2` The reviewer can revise four measures (hours a month, cost a month, revenue a month, reliance on outside tools: None / Partly / Fully), the kind and the area, with an optional note. This exists because an idea can have more merit than its sharer was able to put into numbers.
3. `L-WORTH/3` A revision never overwrites the sharer's figures. Both are stored. The reviewer's page marks changed tiles with the original ("was …"); the sharer's page shows the reviewer's figures next to theirs, with the note.
4. `L-WORTH/4` The sharer is told at once (Inbox item: "Meera revised what your idea is worth", with the note).
5. `L-WORTH/5` Revised figures are what the decision, the Wall and later impact comparison use.
6. `L-WORTH/6` Units: hours per month; rupees per month for cost and revenue (displayed with Indian grouping; lakh and crore in summaries). Ranges are allowed; store low and high.
7. `L-WORTH/7` Every revision is versioned with who, when and the note.

## `L-WORTH.touchpoints` Where the front end depends on this

`S-R2`, `S-05`, `S-06`, `C-WORTH`
