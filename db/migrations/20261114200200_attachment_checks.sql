-- migrate:up
-- Week-3 file checks (§4.2 attachments, D3): what each check found, the digest's claims, and when the file's
-- text went into the search index. Text stays out of these columns except the digest, which is tagged.
ALTER TABLE attachments
  ADD COLUMN checks      jsonb,        -- {patterns, ocr, gatekeeper, gatekeeper_skipped, waiting_for}: codes only
  ADD COLUMN digest_meta jsonb,        -- {claims (tagged), kind_of_evidence, generated_by}
  ADD COLUMN indexed_at  timestamptz;

CREATE INDEX chunks_attachment ON chunks (attachment_id) WHERE attachment_id IS NOT NULL;

-- New features start switched off (§7.6, DEC-057) until their gates pass.
INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
  ('attachments.deep_check', 'off', 'New feature: off until its gates pass', 'migration'),
  ('agent.attachment-digest', 'on', NULL, NULL)
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name IN ('attachments.deep_check', 'agent.attachment-digest');
DROP INDEX IF EXISTS chunks_attachment;
ALTER TABLE attachments DROP COLUMN IF EXISTS checks, DROP COLUMN IF EXISTS digest_meta, DROP COLUMN IF EXISTS indexed_at;
