-- migrate:up
-- A committee reversal to Pick takes a Pick's consequences (L-COMMITTEE.rules/5, L-DECIDE.rules/6; BLD-B259): the
-- build team is chosen by a date the reversal sets, as a desk Pick sets `idea_decisions.team_by`. The reversal keeps
-- it beside its own `return_at`, so the desk's decision stays on record as the desk left it. Only a reversal to Pick
-- has one. Rows reversed before this column have none; the readers work it out from the reversal time.
ALTER TABLE decision_reversals ADD COLUMN team_by timestamptz;
ALTER TABLE decision_reversals ADD CONSTRAINT decision_reversals_team_by_check
  CHECK (team_by IS NULL OR to_choice = 'pick');

-- migrate:down
ALTER TABLE decision_reversals DROP CONSTRAINT IF EXISTS decision_reversals_team_by_check;
ALTER TABLE decision_reversals DROP COLUMN IF EXISTS team_by;
