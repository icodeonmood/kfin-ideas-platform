-- migrate:up
-- Ones are inducted, and their tier rises, on measured and confirmed impact (L-ONES.rules/1, /3; DEC-102, DEC-106;
-- lane A, BLD-A214). A tier that rises because a measurement landed has no proposal behind it, so a glow-up's
-- proposal becomes optional. `measurement_id` names the measurement that lifted it, for the audit trail.
ALTER TABLE one_glow_ups
  ALTER COLUMN proposal_id DROP NOT NULL,
  ADD COLUMN measurement_id bigint REFERENCES delivery_measurements (id) ON DELETE SET NULL;

-- migrate:down
DELETE FROM one_glow_ups WHERE proposal_id IS NULL;
ALTER TABLE one_glow_ups
  DROP COLUMN IF EXISTS measurement_id,
  ALTER COLUMN proposal_id SET NOT NULL;
