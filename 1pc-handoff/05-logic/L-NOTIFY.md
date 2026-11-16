---
id: L-NOTIFY
title: Notifications outside the app: Teams and email
rev: 1
status: baseline
source: reference/copy/Profile.md
depends_on: [L-INBOX]
last_delta: none
---

# L-NOTIFY: Notifications outside the app: Teams and email

1. `L-NOTIFY/1` Every Inbox item can also be sent on Teams and by email. The Inbox always gets it; the other two follow the person's settings (`S-H6`).
2. `L-NOTIFY/2` Settings (each on by default): "Teams messages: when the review desk asks you something, or one of your ideas moves a stage." "Email: the same updates, for your records." "Reminders before a question is due: a day before, and again two hours before."
3. `L-NOTIFY/3` Messages contain the idea title, what happened, any date, and a link into the app. They never contain hidden details, the person's raw words, or a decision's full reason: the reason is read in the app. `NOT DRAWN:` default.
4. `L-NOTIFY/4` Decisions, reversals and merge notices are always sent on at least one outside channel even if the person turned both off; the default fallback is email.
5. `L-NOTIFY/5` Reminders: for an open question set, 24 hours and 2 hours before the deadline, skipped if already answered. For a lead with a waiting request: once after 2 working days (`NOT DRAWN:` default).
6. `L-NOTIFY/6` Delivery failures are retried and do not block the action that caused them.
7. `L-NOTIFY/7` The person can ask to be told when the native app is out ("Tell me when it's out" on `S-H3`): store the request per person.

## `L-NOTIFY.touchpoints` Where the front end depends on this

`S-H6`
