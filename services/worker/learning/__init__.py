"""The learning loops (§5). Nothing here retrains a model or changes anything on its own: reports hold counts and
rates, and every proposal waits for a person (non-negotiable 5). All of it stops while `learning.jobs` is off.

- Corrections as examples (§5.1): already live, through plan P6 (`router/corrections.py`) in canvas assist and judge.
- Area tags (§5.2, monthly): poorly fitting ideas pooled and grouped; each group waits for the product team.
- Glossary (§5.3, weekly): new terms in at least 3 ideas wait for the product team.
- Outcome calibration (§5.4, quarterly): actual against target for every delivery closed in the quarter.
- Evaluation before every change (§5.5): `make eval` blocks a failing agent change; `evalrunner` switches a failing
  agent off on deploy.
- Autonomy (§5.6, daily): acceptance rates per eligible action type. Autonomy itself stays off (non-negotiable 5).
- Drift (§5.7, weekly): acceptance, cost, scan time and fallback; alerts on a 5-point acceptance drop or cost over
  budget.
- The canvas (§5.8, monthly): skip rates, time to complete and quick captures.
- Committee decisions (§5.9): waits for the committee flow's decisions (coming soon).
"""
