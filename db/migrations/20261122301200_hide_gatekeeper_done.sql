-- migrate:up
-- L-HIDE.detect, DEC-131 (3), BLD-C231. Additive only. `gatekeeper_done_at` marks a sealed text whose gatekeeper check is
-- complete: the gatekeeper answered on these words, or their re-check gave up (audited as `hide.recheck_gave_up`).
-- NULL means the words have only had the patterns and names: written while the assistant (`ai.all`) or the gatekeeper
-- (`agent.gatekeeper`) was off, or while the gateway failed. Once both switches are on, the ticker's watch queues a
-- `hide.recheck` for each NULL row, a few at a time (`hide/recheck.py` `queue_unchecked`). Every row that exists
-- today starts NULL, so each sealed text written before this column is checked once at the first switch-on. The table
-- stays worker-only (no grant changes).
ALTER TABLE idea_words_sealed ADD COLUMN gatekeeper_done_at timestamptz;
CREATE INDEX idea_words_sealed_unchecked ON idea_words_sealed (id) WHERE gatekeeper_done_at IS NULL;

-- migrate:down
DROP INDEX IF EXISTS idea_words_sealed_unchecked;
ALTER TABLE idea_words_sealed DROP COLUMN IF EXISTS gatekeeper_done_at;
