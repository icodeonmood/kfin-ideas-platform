---
id: L-SUBMIT
title: Sending, the edit window, withdrawing and restoring
rev: 1
status: baseline
source: reference/copy/Status.md
depends_on: [L-SORT, L-HIDE, L-SIMILAR, E-ENTITIES]
last_delta: none
---

# L-SUBMIT: Sending, the edit window, withdrawing and restoring

## `L-SUBMIT.pre` Before sending: what must be true

1. The draft is ready (`L-DRAFT.parts/7`).
2. Sorting is confirmed (`L-SORT.rules/2`).
3. No attached file is in the state "personal data found" or "checking" (the person hides it, removes it, or waits).
4. No merge request is waiting on a lead (`L-MERGE.request/4`); a merged draft is not sent at all.
5. The declaration is shown beside the button: "By submitting, you confirm there's no customer personal data in it or its files, and it's your own work or you've credited others." Pressing Submit is the acceptance; record the declaration text version and time.
6. Everything else is optional: proof, a fix, who would help.

## `L-SUBMIT.send` Sending

1. On success the idea gets its reference at once, in the form `IDEA-<year>-<six-digit running number>`, and stage "Shared". The person lands on their idea's page (`S-06`, "Just shared").
2. The first-share moment: the mark draws once in the page header (≤ 1.6s) and never covers content; the reference and the next step are readable immediately.
3. "Checked and matched" then runs in the background (final hidden-detail pass, similar ideas) and completes within minutes; its result line appears on the track.
4. The review clock starts: decision due 5 working days after sharing ("The review desk will look at it by Friday 20 November"). Working days follow the KFintech holiday calendar.
5. The sharer is told on Teams and by email when anything changes (`L-NOTIFY`).
6. Button label: "Submit", or "Submit with my fix" when a fix is included.

| Failure | Behaviour |
|---|---|
| Send fails | Stay on Check it: "Couldn't send. Your draft is safe." + "Try again". Nothing is lost. The request is idempotent (a retry never creates two ideas) |
| Offline | "You're offline. Your draft is saved on this device. Submit now and it sends when you're back online." Submit stays enabled: the idea is queued on the device and sent on reconnect; the person can leave the screen |
| Sorting unconfirmed | `L-SORT.rules/4` |

## `L-SUBMIT.edit` The edit window

1. The sharer can edit or withdraw from sharing until the review desk opens the idea, and at the latest 3 days after sharing, whichever comes first. The page says so with the date: "Open to changes until Tuesday 17 November." and a countdown ("3 days left").
2. Edit opens the same content as Check it in one page (`S-06B`) with "Save changes" and "Back to your idea". Nothing changes for anyone else until Save. After Save: "Saved. The review desk will see the latest version."
3. Editing re-runs hidden-detail detection and, if the summary changed, similar-idea matching.
4. Each save is a version. The reviewer sees "Draft history: 3 versions. Title changed once, sorting confirmed." and can view the changes.
5. Once the desk opens it: "The review desk opened it on Monday 16 November, so the idea itself can't be changed now. Write to them in the conversation." Edits become messages.
6. Empty optional parts show a prompt during the window: "No fix added. Add one until Tuesday 17 November", "Nothing attached. Add one until …".

## `L-SUBMIT.withdraw` Withdraw and restore

1. "Withdraw" is available during the edit window. It confirms in place (optional reason), with no pop-up.
2. A withdrawn idea leaves every queue and the Wall at once: "Withdrawn. It's back in your drafts. Nobody else can see it now." Its reference is kept and never reused. Its stage track shows the remaining stages as "not going ahead".
3. "Restore it" shares it again as it was, with the same reference; the review clock restarts from the restore time. Restoring is possible at any time (`P-DECISIONS.signoff/3`).
4. Crew members of a withdrawn idea are told; their team-up ends. Requests waiting on that idea are closed as "withdrawn by the sharer".

## `L-SUBMIT.states` Idea status changes owned here

`draft → shared (checking) → with_review_desk`, `shared|with_review_desk (unopened) → withdrawn → shared`. The full machine is `E-ENUMS.idea-status`.

## `L-SUBMIT.touchpoints` Where the front end depends on this

`S-05`, `S-06`, `S-06B`
