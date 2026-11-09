-- migrate:up
-- Delivery review fixes (BLD-126): who sent a pack for approval and who submitted a fix's numbers, so neither can
-- approve their own.
ALTER TABLE deliveries
  ADD COLUMN submitted_by uuid REFERENCES users (id) ON DELETE RESTRICT,
  ADD COLUMN completed_by uuid REFERENCES users (id) ON DELETE RESTRICT;

-- migrate:down
ALTER TABLE deliveries DROP COLUMN IF EXISTS completed_by, DROP COLUMN IF EXISTS submitted_by;
