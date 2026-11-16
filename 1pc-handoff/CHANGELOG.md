# Changelog

Every change to the design since draft 0, newest first, as old → new. How to read and apply an entry: `README.md`, section 6.

Rules for whoever writes an entry:

1. One entry per publish of the canvas that changes behaviour, look or copy. Give it the next `D-` number, the date and the canvas version.
2. One row per change. Name the smallest thing that changed: a numbered line (`S-R2.panel/3`), else an anchor (`S-R2.panel`), else a module.
3. **Old** says what the code does today, in words Claude Code can search for (a label, a state name, a value). **New** says what it must do instead. Keep each to one line; the module file carries the detail.
4. Update the module files in the same change, so they always describe the current state. Bump `rev` and set `last_delta` in each touched file's header, then rebuild `manifest.json`.
5. End the entry with **Read** (the files and anchors to open) and the acceptance tests to run. Do not list anything unchanged.
6. If a change settles an `OPEN:` or `NOT DRAWN:` line, say so in the row and remove the marker from the module.
7. If a change renames a term, add a `RENAME` row and update `F-COPY.vocabulary`.
8. Never edit a past entry. Correct it with a new one.

To find what changed between two canvas versions, run `tools/changed_boards.py` against the new prototype folder: it compares each board's hash with `manifest.json` and lists the screens, components and journeys that depend on the boards that moved.

---

## D-0000 · 2026-11-16 · canvas v106 · Baseline (draft 0)

Summary: the whole pack. Everything in `manifest.json` is at `rev: 1`.

| # | Type | ID | Old | New | Build impact |
|---|---|---|---|---|---|
| 1 | ADD | every module | nothing | as written | FE, BE, contract, test |

Read: `README.md`, then the build order in its section 7.
Tests: all of `V-ACC`.

Design history that shaped this baseline (already folded into the modules; listed so the reasons are not lost):

| Canvas version | What changed | Where it lives now |
|---|---|---|
| v93 | Sending from Home's prompt goes to the conversation, never the empty Tell it | `S-03.hero/3`, `P-ROUTES.graph` |
| v94 | Draft loader: skeletons plus one bar weighted across six services, never pausing | `C-DRAFT-LOADER`, `L-DRAFT.parts` |
| v95 | No coloured side stripes; accents conditioned to 87% chroma; contrast raised; four radii; sidebar navigation; labels above headings removed | `F-COLOR.principles`, `F-SPACE.radius`, `C-CARD.rules/1`, `F-TYPE.rules/2` |
| v96 to v97 | Sorting sections made uniform; similar ideas as a grid three across with yours first | `S-05.parts/2–3`, `C-SIMGRID.grid` |
| v98 | Snackbars and Undo removed; field messages sit under their field | `C-FIELD-MSG`, `P-DECISIONS.taken/12` |
| v99 | Merging is a request to the other lead; the review desk can merge and team sharers up | `L-MERGE`, `S-H2B`, `C-SHEET-MERGE` |
| v100 | Team-up sheet: one button; "Bring your ideas along" is a collapsed multi-select with nothing chosen. The Ones on Home move with the wheel | `C-SHEET-TEAMUP`, `C-DROPDOWN`, `C-ONES-FAN.behaviour/4` |
| v101 | Ones cards 12px apart when spread; crew cards move like a pack of cards; "Find your crew" on one line | `C-ONES-FAN.behaviour/2`, `C-CREW-DECK.behaviour`, `S-H2.title` |
| v102 | Wall impact tiles share one build; Just in can be sorted four ways and pages 5 at a time | `S-WALL.impact`, `S-WALL.justin`, `L-WALL.justin` |
| v103 | Reviewer can preview a similar idea in a pop-up; merge sheet has one button | `C-PREVIEW`, `C-SHEET-MERGE` |
| v104 | Reviewer's panel scrolls on its own with its button pinned | `S-R2.panel` |
| v105 | Reviewer's main path is to decide; asking first is optional and collapsed | `S-R2.panel/1–2`, `L-REVIEW.panel` |
| v106 | Reviewer's panel starts level with "Listen to the whole idea" | `S-R2.layout/3` |
