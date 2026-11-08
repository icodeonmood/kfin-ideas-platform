---
type: rule
title: Working calendar
description: Time zone, weekends and KFin holidays used for every working-day calculation.
tags:
- rules
- calendar
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-calendar
  version: '1.0'
  approver: null
---

**Replace with KFin's official holiday list for 2026 and 2027 (open point O10).** The November dates below are assumptions for Diwali week.
A working day is Monday to Friday, in IST, excluding the holidays listed.

```yaml
version: '0.1'
timezone: Asia/Kolkata
weekend:
- sat
- sun
holidays:
- date: '2026-11-09'
  name: Diwali holiday (assumed)
  confirmed: false
- date: '2026-11-10'
  name: Diwali holiday (assumed)
  confirmed: false
- date: '2026-12-25'
  name: Christmas (assumed)
  confirmed: false
quiet_hours:
  from: '20:00'
  to: 08:00
```
