"""The programme team's admin path (lane A; SHIP_PLAN_1PC §5, §6.3; journey J-ONE steps 1, 2, 3 and 6).

- `build`: choose a picked idea's build team and lead, then mark it shipped (`L-DECIDE.after`).
- `impact`: the 30- and 90-day measurements, Finance's confirmation, the due list and the sweep (`L-IMPACT`).
- `ones`: Ones inducted on measured, confirmed impact, tiers that rise with it, Founding Ones and removal
  (`L-ONES.rules/1-3`, DEC-106).
- `wall`: "Take off the Wall" and restore, for the review desk and admins (DEC-106, SHIP_PLAN §6.3).
- `flags`: the S1 to S3 experiments, per person or by percentage, with exposure logged (`L-AUDIT.flags`).

Every change is a privileged action: checked against the person's live grants here (the web app checked the
capability first) and written to `audit_log` with IDs, numbers and staff-written reasons only (non-negotiables 3,
9). Nobody's idea text is logged.
"""
