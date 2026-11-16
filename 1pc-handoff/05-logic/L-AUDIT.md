---
id: L-AUDIT
title: Permissions, audit trail, feature flags, configuration
rev: 1
status: baseline
source: reference/prototype/Handoff.dc.html
depends_on: [E-ENTITIES]
last_delta: none
---

# L-AUDIT: Permissions, audit trail, feature flags, configuration

## `L-AUDIT.permissions` Permissions

Enforce on the server for every read and write, from `P-PRODUCT.roles` and `P-PRODUCT.privacy`. The front end hides what a person cannot do, but never relies on hiding.

| Action | Allowed for |
|---|---|
| Read a draft | Its owner only |
| Read an idea's public summary | Any employee, once shared and not withdrawn |
| Read own words, conversation, answers, files | Sharer, crew (not own words), reviewers, committee, build team once chosen |
| Edit or withdraw an idea | Sharer, inside the edit window |
| Ask questions, revise worth, decide, merge | Reviewers, not on their own ideas |
| Extend or reverse | Committee members, inside the window, not on their own ideas |
| Answer a team-up request | The idea's lead |
| See points | The person only |
| Un-hide a detail | The person who typed it, with a reason |

## `L-AUDIT.trail` Audit trail

Record, with who and when, never with hidden values: sign-ins and failures; draft created and shared; every hide, show and file check; sorting suggested, confirmed, changed; every edit version; withdraw and restore; opened by the desk; questions sent, seen, answered, extended, reminded; worth revised; decisions; committee extend and reverse; merge requests and outcomes; desk merges; team-up requests and outcomes; role changes; flag changes.

## `L-AUDIT.config` Configuration (changeable without a release)

Every number in `P-PRODUCT.promises`; the lists of areas, groups and worth options; the hidden-detail patterns; the holiday calendar; the area-to-queue mapping; role assignments; notification templates; the tier and points rules; the three placeholders (`F-COPY.placeholders`).

## `L-AUDIT.flags` Feature flags

S1, S2, S3 (`P-DECISIONS.experiments`), each assignable per person or per percentage, with exposure logged. Plus kill switches for: voice input, email and Teams intake, search by meaning, the listen player. When a switch is off the feature's entry point is hidden and everything else works.

## `L-AUDIT.metrics` Product metrics to instrument

Time from first keystroke to share; share completion and where people drop; share of drafts with how-often, who and worth filled; how often each suggested sorting is changed; "Show it" rate by reason; similar-idea outcomes (previewed, merge asked, kept separate); duplicates reaching the desk; time to decision against the 5-day promise; answer rate and time; reversal rate; team-up request outcomes; channel of intake.
