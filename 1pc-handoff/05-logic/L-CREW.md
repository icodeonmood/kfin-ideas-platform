---
id: L-CREW
title: Find your crew: what is suggested, in what order
rev: 1
status: baseline
source: reference/copy/Crew.md
depends_on: [L-SIMILAR, L-TEAMUP]
last_delta: none
---

# L-CREW: Find your crew: what is suggested, in what order

1. `L-CREW/1` The deck shows shared ideas the person could help with, that they are not on, have not asked to join and have not passed.
2. `L-CREW/2` Each card carries the one reason it is shown, in this order of strength: close to an idea of theirs ("Same R07 SMS as your idea from Saturday", "The calls your idea is about"); touches their work ("Investors call your branch about this too"); same area ("Your area, Investor service"); same office ("Same office as you, Hyderabad").
3. `L-CREW/3` Order: by that strength, then by how recently the idea was shared.
4. `L-CREW/4` Each card needs: status, title, area, city, the reason, "the problem, in their words" (one masked sentence), "they're looking for" (from the sharer's "Who would help" answer on Check it, or generated from the idea if empty), crew faces and count, lead.
5. `L-CREW/5` Filters, each with live counts: Location, Category (area), Idea status, Team size (Just the lead; 2 to 3 people; 4 or more), Looking for. "Show N ideas" applies; "Clear all" resets. An active filter shows as a chip above the deck.
6. `L-CREW/6` "Next" passes a card. Passed cards are remembered per person; "Undo last pass" brings the last one back; "See them again" resets all passes.
7. `L-CREW/7` After the last card: "That's everyone for now." with how many requests were sent and how many passed.
8. `L-CREW/8` With no shared ideas of their own and nothing in their area: "No crews to join yet" with "Browse the Wall".
9. `L-CREW/9` "Your crews" lists ideas the person has joined or asked to join, with state ("Waiting for Ravi", "On the crew"), and links to My ideas → Teamed up.
10. `L-CREW/10` Home shows the top three as cards with "Idea 1 of 3" and "See all".

## `L-CREW.touchpoints` Where the front end depends on this

`S-H2`, `S-03`, `C-CREW-DECK`
