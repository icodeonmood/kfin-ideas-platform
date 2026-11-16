---
id: E-ENUMS
title: Enums, statuses and state machines
rev: 1
status: baseline
source: reference/copy/
depends_on: [F-COLOR, F-COPY]
last_delta: none
---

# Enums, statuses and state machines

Values are the wire values. Labels are exactly what the interface shows. If the repo already has these enums under other names, keep the repo's wire values and map them in `REPO-MAPPING.md`; the labels and pill variants here do not change.

## `E-ENUMS.idea-status` Idea status

| Value | Label | Pill | Stage on the track | Means |
|---|---|---|---|---|
| `draft` | Draft | neutral | none | Not sent. Visible to its owner only |
| `checking` | Checking | blue | Checked and matched (now) | Sent; the automatic check is running |
| `with_review_desk` | With the review desk | blue | Reviewed (now) | Waiting for or under review |
| `needs_you` | Needs you | warn | Reviewed (now) | A question set is open. This is a view of `with_review_desk` for the sharer; the desk sees "Waiting on the sharer" |
| `picked` | Picked | blue | Built (now) | Decided: go ahead; team being chosen |
| `being_built` | Being built | blue | Built (now) | A team is building it |
| `shipped` | Shipped | ok | Shipped (done) | Live |
| `not_now` | Not now | warn | Reviewed (done), rest paused | Comes back on a date |
| `not_picked` | Not picked | neutral | Reviewed (done), rest "not going ahead" | Closed |
| `withdrawn` | Withdrawn | neutral | all remaining "not going ahead" | Taken back by the sharer; restorable |
| `merged` | Merged | neutral | none; links to the surviving idea | Part of another idea |

"Closed" in filters = `not_picked`, `not_now`, `withdrawn`, `merged`. "Picked and building" = `picked`, `being_built`.

## `E-ENUMS.idea-machine` Idea state machine

```
draft ──submit──▶ checking ──auto──▶ with_review_desk
with_review_desk ◀──questions sent / answered──▶ (needs_you view)
with_review_desk ──decide: pick──▶ picked ──team chosen──▶ being_built ──mark shipped──▶ shipped
with_review_desk ──decide: not now──▶ not_now ──return date──▶ with_review_desk
with_review_desk ──decide: not picked──▶ not_picked
checking | with_review_desk (not yet opened) ──withdraw──▶ withdrawn ──restore──▶ checking
draft ──merge request accepted──▶ merged
with_review_desk ──desk merge (non-lead idea)──▶ merged ──committee reverses──▶ with_review_desk
picked | not_now | not_picked ──committee reverses──▶ one of the other two (final)
```

Guards: edit and withdraw only before `opened_at` is set and within the edit window (`L-SUBMIT.edit/1`). Decide only by a reviewer who is not the sharer. Reverse only by a committee member inside an open window, once.

## `E-ENUMS.stage` Stages

`shared`, `checked_matched`, `reviewed`, `built`, `shipped`. Labels: Shared; Checked and matched; Reviewed; Built; Shipped. Each stage on an idea has a state: `done`, `now`, `to_come`, `not_going_ahead`, plus a detail line and a date.

## `E-ENUMS.kind` What kind it is

| Value | Label on Check it | Label on the Wall |
|---|---|---|
| `problem` | A problem to fix | Problem (filter: Problems) |
| `fix` | (a problem shared with a fix) | Fix (filter: Fixes) |
| `business_idea` | A new business idea | Business idea (filter: Business ideas) |

`OPEN:` Check it offers two kinds; the Wall shows three. Default: an idea shared as "A problem to fix" shows on the Wall as "Fix" once it includes a fix, else "Problem". Confirm with the product owner.

## `E-ENUMS.sorting` Sorting lists (configuration; values drawn on the boards)

| List | Values drawn |
|---|---|
| `affects` (multi) | Investors, KFin teams, Distributors; more behind "Search all groups" |
| `area` (single) | Investor service, Operations, Distributor experience, Corporate registry, Technology, Compliance, Sales, New business, Distributor services |
| `brings` (multi) | `saves_time` Saves time; `saves_cost` Saves cost; `earns_revenue` Earns revenue; `less_outside_tools` Cuts reliance on outside tools; `not_sure` Not sure yet |
| `sorting_source` | `suggested`, `confirmed`, `changed` |
| `helper` (multi; "Who would help") | Someone at a branch; Someone in operations; Someone from tech; Someone who knows the rules; Data or reports; plus free text |

## `E-ENUMS.part` Parts of an idea (for questions, answers and the listen player)

`summary` The problem; `often` How often; `who` Who it affects; `cost` What it's worth; `evidence` Attached; `fix` Fix.

## `E-ENUMS.decision` Decisions

`pick` Picked; `not_now` Not now; `not_picked` Not picked. `return_in`: `1m`, `3m` (default), `6m`.

## `E-ENUMS.windows` Committee window

`open`, `extended`, `reversed`, `expired`.

## `E-ENUMS.questions` Question sets

Set: `queued`, `sent`, `seen`, `partly_answered`, `answered`, `closed`; flag `overdue`. Time to answer: `1d`, `3d` (default), `1w`.

## `E-ENUMS.teamup` Team-up and merge requests

`sent`, `approved_merged`, `approved_team_only`, `declined`, `withdrawn`, `closed`. Draft merge request (on Check it): `none`, `waiting`, `accepted`, `team_only`, `declined`, `withdrawn`.

## `E-ENUMS.file` File and link states

`uploading`, `checking`, `checked`, `upload_failed`, `personal_data_found`, `hidden_checked`, `too_big`, `locked`, `infected`; links: `ok`, `unreachable`; `link_scope`: `internal`, `external`.

## `E-ENUMS.hidden` Hidden detail

Kinds: `folio`, `pan`, `phone`, `email`, `account`, `aadhaar`, `name`. State: `hidden`, `shown`. Show reasons: `scheme_or_product_code` "it's a scheme or product code"; `internal_reference` "it's an internal reference"; `made_up_example` "it's made up for the example".

## `E-ENUMS.fix` Fix sheet

Solved already: `yes`, `partly`, `no`, `dont_know`. Basis: `own_research` My own research; `verified_documents` Verified documents; `report` A report or document; `conversation` A conversation; `hunch` A hunch. Outside tools (reviewer): `none`, `partly`, `fully`.

## `E-ENUMS.draft` Draft parts and channels

Part: `title`, `often`, `who`, `value`, `area`, `similar`. Part state: `waiting`, `updating`, `filled`, `pinned`, `failed`. Channel: `web`, `voice`, `email`, `teams`. Step: `tell`, `check:<1-7>`, `send`.

## `E-ENUMS.inbox` Inbox item kinds

`questions`, `teamup_request`, `teamup_answer`, `decision`, `decision_reversed`, `desk_merge`, `worth_revised`, `stage_moved`, `build_ask`, `mention`, `crew_joined`, `comment`, `draft_kept`, `sent_to_desk`, `answer_reminder`.

## `E-ENUMS.roles` Roles

`employee`, `reviewer`, `committee`, `build_team` (per idea), `admin`, `display`. Per idea: `sharer`, `lead`, `crew`.

## `E-ENUMS.tier` Tiers

1 Spark, 2 Glow, 3 Flame, 4 Blaze, 5 White heat, 6 Blue flame, 7 Star. One flag: `founding`, `one`.

## `E-ENUMS.match` Similar-idea match

`close` ("Close match: …"), `related` ("Related: …"). Crew reason: `close_to_yours`, `touches_your_work`, `same_area`, `same_office`.
