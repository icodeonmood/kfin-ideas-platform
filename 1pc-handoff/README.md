# 1% Club: build handoff

**Baseline: draft 0.** Taken from the design canvas at version 106, 16 November 2026.
This pack tells Claude Code everything needed to build the 1% Club web app so that it matches the design canvas: what each screen is, how it looks and moves, what it must check, and what the back end must do behind it.

Read this file once. After that, you should only ever need `CHANGELOG.md` and the module files a change names.

---

## 1. What you are building

1% Club is KFintech's internal programme for sharing problems seen at work. Any employee signs in, tells the problem in their own words, checks the draft the assistant builds from those words, and sends it. A review desk decides on it. Picked ideas get a team; shipped ideas get measured; the people behind them become "Ones".

One responsive web app: 25 screens. The canvas draws them as 23 desktop boards (1440px wide), 15 phone boards (390×844) and 2 wall displays (1920×1080), plus 2 record boards that are not screens (Handoff, Motion). Desktop and phone boards are the same app at two widths, not two products.

Start with `00-overview/PRODUCT.md`.

## 2. What wins when two sources disagree

1. The latest entry in `CHANGELOG.md` that touches the module.
2. **For behaviour** (rules, states, transitions, validation, permissions, data, what the back end does): the module file in this pack.
3. **For look** (layout, spacing, colour, type, motion, exact copy): the prototype board in `reference/prototype/`, with its screenshots in `reference/shots/`, its resolved values in `reference/computed/` and its copy in `reference/copy/`.

A module's description of a layout is a guide to reading the board, written so you know what each region is for. If the prose and the board disagree on how something looks, build what the board shows and note the mismatch in your PR so the module can be corrected. If they disagree on what something does, the module wins.

The prototype is a design artefact, not production code. Take values, copy and behaviour from it. Do not copy its structure: each board carries the whole stylesheet with many layered overrides, and its logic is a demo that fakes the back end. `reference/computed/` holds the resolved values (what the browser actually paints), which is what you should build from. The board files need the design canvas's own runtime, so they do not open on their own from this folder: read them as source (markup, CSS and the demo logic in the `Component` class at the end of each file), and use the screenshots to see each state. Every state named in a screen module has a screenshot (`<Board>.jpg` for the default, `<Board>__<tweak>-<option>.jpg` for each state; boards taller than 2,600px also have `<Board>__full.jpg` showing the whole page). The live canvas, where every board can be clicked through, is with the product owner.

Everyone named on the boards (Kavya Menon, Meera Iyer, Ravi Nair and the rest) is a fictional demo person. Every figure is demo data. Do not seed production with them.

## 3. Map of the pack

| Folder | Holds | ID prefix |
|---|---|---|
| `00-overview/` | Product, roles, vocabulary, routes, decisions, repo mapping | `P-` |
| `01-foundations/` | Colour, type, space and layout, motion, accessibility, copy rules, icons | `F-` |
| `02-components/` | One file per shared component | `C-` |
| `03-journeys/` | End-to-end user journeys, step by step | `J-` |
| `04-screens/` | One file per screen (desktop and phone together) | `S-` |
| `05-logic/` | What the back end must do: engines, rules, state machines, clocks | `L-` |
| `06-contracts/` | Entities, enums, API shapes each screen expects | `E-`, `A-` |
| `07-validation/` | Field rules, error messages, acceptance tests | `V-` |
| `reference/` | Prototype boards, screenshots, extracted CSS, resolved styles, copy per state | none |
| `manifest.json` | Every module: id, file, revision, source board, source hash, dependencies | none |
| `CHANGELOG.md` | Every change since draft 0, as old → new | `D-` |
| `CLAUDE-snippet.md` | The block to paste into the repo's `CLAUDE.md`, where to put the pack, and a first prompt | none |
| `tools/changed_boards.py` | Lists the boards that changed since the pack was built and the modules that depend on them | none |

## 4. IDs

Every module has a stable ID. IDs are how changes are communicated, so they follow three rules:

- **An ID never changes and is never reused.** If a module is removed, its ID is marked `retired` in `manifest.json` and stays retired.
- **Sections inside a module have anchors:** `S-R2.panel`, `C-SHEET-TEAMUP.states`, `L-MERGE.rules`. Headings carry the anchor in backticks, so you can search for it.
- **Requirement lines are numbered inside a section:** `S-R2.panel/3` is the third numbered line under that anchor. A change that edits one rule names that line.

Prefixes: `P-` product, `F-` foundation, `C-` component, `J-` journey, `S-` screen, `L-` logic, `E-` entity, `A-` API, `V-` validation, `D-` delta (a change entry).

Screen IDs follow the canvas numbering: `S-01` Landing to `S-09` a colleague's idea, `S-R1` to `S-R4` for the review side, `S-H2` to `S-H6` for the Home boxes, and named IDs for the rest (`S-WALL`, `S-ONE`, `S-OFFICE`, `S-LAUNCH`). The full list is in `00-overview/ROUTES.md`.

## 5. Module file format

Every module file starts with the same header:

```
---
id: S-R2
title: The idea, for the reviewer
rev: 1                      # goes up by one each time a delta changes this file
status: baseline            # baseline | changed | retired
source: reference/prototype/DeskIdea.dc.html
depends_on: [C-SIDEBAR, C-LISTEN, C-PREVIEW, C-SHEET-MERGE, L-REVIEW, L-MERGE]
last_delta: none            # the D- entry that last touched it
---
```

`depends_on` lists what you must have built, or must re-check, when this module changes. `manifest.json` holds the same data for every module, plus the reverse (`used_by`), so you can find the blast radius of a change without opening files.

## 6. How changes arrive (read this before any later task)

After draft 0, the design keeps moving. You will not be asked to re-read the pack. Each change arrives as one entry in `CHANGELOG.md`. The entry below is an example of the format, not a real change:

```
## D-0007 · 2026-11-20 · canvas v112
Summary: The reviewer's panel opens on "Review this idea"; asking the sharer is optional.

| # | Type   | ID                  | Old                                   | New                                         | Build impact |
|---|--------|---------------------|---------------------------------------|---------------------------------------------|--------------|
| 1 | CHANGE | S-R2.panel          | Opens on "Ask Kavya", 3 questions queued | Opens on "Review this idea", none queued  | FE           |
| 2 | ADD    | S-R2.panel.ask      | none                                  | Collapsed "Ask Kavya first (Optional)"      | FE           |
| 3 | CHANGE | L-REVIEW.states/2   | reviewing → asked → answered → deciding | reviewing → deciding allowed directly     | BE, contract |
| 4 | CHANGE | V-ACC.review/4      | (old test text)                       | (new test text)                             | test         |

Read: 04-screens/S-R2.md#panel, 05-logic/L-REVIEW.md#states
Unchanged, do not re-read: everything else.
```

Change types:

| Type | Means | What you do |
|---|---|---|
| `ADD` | New module, section or rule | Build it. Read the named file or anchor. |
| `CHANGE` | Same ID, different content | Replace the old behaviour with the new one. The module file already holds the new text; the Old column tells you what to look for in the code. |
| `REMOVE` | Gone | Delete the behaviour and its tests. The ID is retired. |
| `RENAME` | Label or term changed everywhere | Search and replace; `F-COPY.vocabulary` is updated. |
| `MOVE` | Same thing, new place (screen, route, order) | Move it; nothing else about it changed. |
| `TOKEN` | A value in `tokens.json` changed | Change the token, not the call sites. |

Rules for working a delta:

1. Read only the entry and the files under **Read**. If something you need is not listed, check `manifest.json` → `used_by` for the IDs in the entry before opening anything else.
2. The module files are always current: after a delta they describe the new state. The **Old** column exists so you can find the code to change; it is not in the module file any more.
3. Build impact tells you which side moves: `FE` front end, `BE` back-end logic, `contract` API or data shape, `test` acceptance tests, `copy` words only, `token` design tokens.
4. When done, run the acceptance tests named in the entry (`V-` IDs), then add the delta ID to the repo's own change record.
5. Deltas are applied in order. Never skip one.

If a later instruction in chat says "apply D-0007", this is the whole procedure.

## 7. Suggested build order for draft 0

| Phase | Build | Modules |
|---|---|---|
| 0 | Map the pack to the repo | `P-REPO.first-task` |
| 1 | Tokens, type, layout shell, motion primitives | `F-*`, `C-SIDEBAR`, `C-PHONE-TABS`, `C-TASKBAR` |
| 2 | Core components | `C-BUTTON`, `C-CHIP`, `C-PILL`, `C-FIELD`, `C-FIELD-MSG`, `C-CARD`, `C-AVATAR`, `C-SKELETON`, `C-EMPTY`, `C-SORTS`, `C-TABS`, `C-SEARCH`, `C-TRACK`, `C-FILE`, `C-DROPDOWN` |
| 3 | Share journey | `J-SHARE`, `J-RESUME`, `J-RECOVER`: `S-01` to `S-06`, `C-PROMPT`, `C-DRAFT-PANEL`, `C-DRAFT-LOADER`, `C-HIDDEN`, `C-SIMGRID`, `C-PREVIEW`, `L-AUTH`, `L-DRAFT`, `L-HIDE`, `L-SORT`, `L-SIMILAR`, `L-SUBMIT` |
| 4 | Track and respond | `J-TRACK`, `J-BROWSE`: `S-06`, `S-06B`, `S-07`, `S-08`, `S-R3`, `S-H5`, `C-QCARD`, `C-INBOX-READER`, `L-QUESTIONS`, `L-INBOX`, `L-NOTIFY`, `L-CONVO`, `L-SEARCH` |
| 5 | Review side | `J-REVIEW`, `J-COMMITTEE`: `S-R1`, `S-R2`, `S-R4`, `C-LISTEN`, `C-WORTH`, `C-SHEET-MERGE`, `L-REVIEW`, `L-WORTH`, `L-DECIDE`, `L-COMMITTEE`, `L-MERGE`, `L-LISTEN` |
| 6 | Crew and team-up | `J-TEAMUP`, `J-SIMILAR`: `S-09`, `S-H2`, `S-H2B`, `C-CREW-DECK`, `C-SHEET-TEAMUP`, `L-TEAMUP`, `L-CREW` |
| 7 | Recognition and reach | `J-ONE`: `S-WALL`, `S-ONE`, `S-H6`, `C-ONES-FAN`, `L-ONES`, `L-WALL`, `L-IMPACT` |
| 8 | Launch surfaces | `S-OFFICE`, `S-LAUNCH`, `S-H3`, `S-H4`, `L-DISPLAY` |
| All | Cross-cutting, from phase 1 on | `L-AUDIT` (permissions, audit trail, flags, configuration), `F-A11Y`, `V-FIELDS`, `V-ACC` |

## 8. Conventions used in every module

- **Must / should / may** carry their plain meaning. A numbered line under an anchor is a requirement.
- **States** are named exactly as the canvas tweaks name them, so a state in a spec can be opened on the board.
- **Copy.** Final wording, line by line and state by state, is in `reference/copy/<Board>.md`, in Indian English. Do not rewrite it. Quotes inside module files are for reading: they may join a heading and the line under it into one sentence. Where a quote and `reference/copy/` differ in punctuation or line breaks, `reference/copy/` wins. Names of demo people inside copy (Kavya, Ravi, Meera) stand for real names at run time; modules write them as `{me}`, `{sharer}`, `{lead}`, `{reviewer}` where it matters.
- **Back end.** `05-logic/` says what must be true, not how to build it. Where a number is a business promise (5 working days, 30-day window), it is listed in `P-PRODUCT.promises`, with its owner in `P-DECISIONS.signoff`, and must be configuration, not code.
- **Open items** are marked `OPEN:` with the question and who decides. Do not guess past them; build the default the line gives.
- **`NOT DRAWN:`** marks behaviour the canvas does not show (a failure case, a width, a busy state) but the build needs. The line gives the default to build. If the design later draws it, a delta replaces the line.

## 9. What draft 0 does not know

Read `00-overview/GAPS.md` for the full list. The main points:

1. **The existing repo was not read.** `00-overview/REPO-MAPPING.md` is empty and filling it in is the first task.
2. **Open questions** for the product owner are marked `OPEN:`; each has a default.
3. **Undrawn behaviour** (failure cases, busy states, limits) is marked `NOT DRAWN:`; each has a default.
4. **The phone boards for Tell it and Check it use an earlier structure** than the desktop boards. Desktop rules and copy win; each screen's `phone` section says how to lay it out.
5. **Admin tasks** (choosing a build team, marking shipped, entering measurements, managing roles and the Ember) have no screens. Their rules are in `05-logic/`; build a minimal admin page or API.
6. **Layout between 641px and 1100px** is not drawn; `F-SPACE.breakpoints` gives the default.

## 10. Not in this pack

- The existing repo's code. `00-overview/REPO-MAPPING.md` maps modules to repo paths; it is marked pending until the repo has been read.
- Infrastructure, deployment, monitoring.
- The native phone app ("coming soon" on the canvas). The phone boards here are the responsive web layout.
