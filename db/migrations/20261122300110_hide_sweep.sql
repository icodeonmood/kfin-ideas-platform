-- migrate:up
-- L-HIDE.rules/7 (lane C, BLD-C066). Additive only. When the review desk hides a detail, every copy of the idea is
-- masked and each changed copy gets a `hidden_details` row, so these copies can be sources too: the fix (`fix`,
-- also a "Hide this" source), a saved version (`version`, source_id = its n), a similar-idea reason (`similar`,
-- source_id = the other idea's uuid) and a draft run's receipt (`run`, source_id = the run id). A desk question
-- stays `desk`, the idea's lines `title`, the parts `part`.
ALTER TABLE hidden_details DROP CONSTRAINT IF EXISTS hidden_details_source_check;
ALTER TABLE hidden_details ADD CONSTRAINT hidden_details_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file', 'desk', 'title', 'part',
                    'fix', 'version', 'similar', 'run'));

-- migrate:down
DELETE FROM hidden_details WHERE source IN ('fix', 'version', 'similar', 'run');
ALTER TABLE hidden_details DROP CONSTRAINT IF EXISTS hidden_details_source_check;
ALTER TABLE hidden_details ADD CONSTRAINT hidden_details_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file', 'desk', 'title', 'part'));
