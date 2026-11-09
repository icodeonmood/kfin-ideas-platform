-- migrate:up
-- Evidence files on deliveries (BLD-131) and Friday check-in replies from the screen (BLD-132).
--
-- Evidence reuses the attachments pipeline: quarantine, virus scan, personal-data check, clean bucket. A row
-- belongs to exactly one idea draft or one delivery; delivery files are uploaded by a person (the owner or an
-- admin), so they carry the user, not a contributor code. Files are never opened before the checks pass.
ALTER TABLE attachments
  ALTER COLUMN idea_uuid DROP NOT NULL,
  ALTER COLUMN uploaded_by_code DROP NOT NULL,
  ADD COLUMN delivery_id bigint REFERENCES deliveries (id) ON DELETE CASCADE,
  ADD COLUMN uploaded_by_user uuid REFERENCES users (id) ON DELETE SET NULL,
  ADD CONSTRAINT attachments_one_owner CHECK (num_nonnulls(idea_uuid, delivery_id) = 1),
  ADD CONSTRAINT attachments_uploader CHECK (
    (idea_uuid IS NOT NULL AND uploaded_by_code IS NOT NULL) OR (delivery_id IS NOT NULL)
  );
CREATE INDEX attachments_delivery ON attachments (delivery_id) WHERE delivery_id IS NOT NULL;

-- One reply per delivery per week (the week starts on Monday, IST). The note is checked text, stored encrypted.
CREATE TABLE delivery_checkins (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  delivery_id     bigint      NOT NULL REFERENCES deliveries (id) ON DELETE CASCADE,
  week_of         date        NOT NULL,
  status          text        NOT NULL CHECK (status IN ('on_track', 'at_risk', 'blocked')),
  note_encrypted  bytea,
  by_user         uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (delivery_id, week_of)
);
CREATE TRIGGER delivery_checkins_updated_at BEFORE UPDATE ON delivery_checkins
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- migrate:down
-- The delivery attachments' files stay in the quarantine and clean buckets: SQL cannot reach the object store.
-- Remove them first (RUNBOOK §4.9, BLD-146).
DROP TABLE IF EXISTS delivery_checkins;
DELETE FROM attachments WHERE delivery_id IS NOT NULL;
DROP INDEX IF EXISTS attachments_delivery;
ALTER TABLE attachments
  DROP CONSTRAINT IF EXISTS attachments_uploader,
  DROP CONSTRAINT IF EXISTS attachments_one_owner,
  DROP COLUMN IF EXISTS uploaded_by_user,
  DROP COLUMN IF EXISTS delivery_id,
  ALTER COLUMN uploaded_by_code SET NOT NULL,
  ALTER COLUMN idea_uuid SET NOT NULL;
