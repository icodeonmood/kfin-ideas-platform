-- migrate:up
-- L-HIDE, L-TEAMUP, L-MERGE.request (lane C's source, carried on lane F's branch: BLD-F097). Additive only. The three
-- team-up texts go through lane C's hide as the sealed source `teamup`: the team-up note (source_id = the request
-- id), the lead's decline reason ("<request id>:decline") and a draft's ask ("<merge request id>:ask"). Each value
-- gets a `hidden_details` row and the typer's own words a sealed row, so both CHECKs take `teamup`. The idea page's
-- hidden details leave these rows out (ideapage/read.py `hidden`).
ALTER TABLE hidden_details DROP CONSTRAINT IF EXISTS hidden_details_source_check;
ALTER TABLE hidden_details ADD CONSTRAINT hidden_details_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file', 'desk', 'title', 'part',
                    'fix', 'version', 'similar', 'run', 'teamup'));
ALTER TABLE idea_words_sealed DROP CONSTRAINT idea_words_sealed_source_check;
ALTER TABLE idea_words_sealed ADD CONSTRAINT idea_words_sealed_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'teamup'));

-- migrate:down
-- The team-up rows go first, as lane C's `forget` drops them: each vault value no other text of the idea still holds,
-- then the hidden details and the sealed words. Then both CHECKs as they were.
DELETE FROM pseudonym_vault v USING hidden_details d
  WHERE d.source = 'teamup' AND d.vault_tag = v.tag AND v.scope_id = 'DRAFT-' || d.idea_uuid::text
    AND NOT EXISTS (SELECT 1 FROM hidden_details o WHERE o.idea_uuid = d.idea_uuid AND o.vault_tag = v.tag
                    AND o.source <> 'teamup');
DELETE FROM hidden_details WHERE source = 'teamup';
DELETE FROM idea_words_sealed WHERE source = 'teamup';
ALTER TABLE hidden_details DROP CONSTRAINT IF EXISTS hidden_details_source_check;
ALTER TABLE hidden_details ADD CONSTRAINT hidden_details_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file', 'desk', 'title', 'part',
                    'fix', 'version', 'similar', 'run'));
ALTER TABLE idea_words_sealed DROP CONSTRAINT idea_words_sealed_source_check;
ALTER TABLE idea_words_sealed ADD CONSTRAINT idea_words_sealed_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit'));
