-- migrate:up
-- Learning from core committee decisions (§5.9, BLD-149) and scoring-band proposals (§3.4, BLD-150).
-- New report kinds: what the committee rewards (a readable model of picked versus declined on the scorecard
-- dimensions) and where the committee actually draws the shortlist line. New proposal kinds wait for the core
-- committee: scorecard weights and the shortlist threshold. Approval records the decision; writing the new rule
-- version into the company repo is "Coming soon" (the product team edits the rule by hand until then).
ALTER TABLE learning_reports DROP CONSTRAINT IF EXISTS learning_reports_kind_check;
ALTER TABLE learning_reports ADD CONSTRAINT learning_reports_kind_check
  CHECK (kind IN ('canvas', 'calibration', 'drift', 'autonomy', 'agreement', 'committee_rewards', 'scoring_band'));

ALTER TABLE learning_proposals DROP CONSTRAINT IF EXISTS learning_proposals_kind_check;
ALTER TABLE learning_proposals ADD CONSTRAINT learning_proposals_kind_check
  CHECK (kind IN ('area_tag', 'glossary_term', 'scorecard_weights', 'scoring_band'));

-- migrate:down
DELETE FROM learning_proposals WHERE kind IN ('scorecard_weights', 'scoring_band');
DELETE FROM learning_reports WHERE kind IN ('committee_rewards', 'scoring_band');
ALTER TABLE learning_proposals DROP CONSTRAINT IF EXISTS learning_proposals_kind_check;
ALTER TABLE learning_proposals ADD CONSTRAINT learning_proposals_kind_check
  CHECK (kind IN ('area_tag', 'glossary_term'));
ALTER TABLE learning_reports DROP CONSTRAINT IF EXISTS learning_reports_kind_check;
ALTER TABLE learning_reports ADD CONSTRAINT learning_reports_kind_check
  CHECK (kind IN ('canvas', 'calibration', 'drift', 'autonomy', 'agreement'));
