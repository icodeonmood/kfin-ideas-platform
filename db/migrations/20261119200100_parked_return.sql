-- Parked groups come back at the next cycle (§4.7, BLD-228). After `parked.archive_after_cycles_without_joiners`
-- parks with no colleague joining, a group is archived instead: it keeps its "parked" stage, so nothing new shows on
-- screen, and its last decision can still be appealed.

-- migrate:up
ALTER TABLE clusters ADD COLUMN archived_at timestamptz;

-- migrate:down
ALTER TABLE clusters DROP COLUMN IF EXISTS archived_at;
