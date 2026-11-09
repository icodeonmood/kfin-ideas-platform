-- migrate:up
-- Points (DEC-078, BLD-130): each award is recorded once. The ledger stays append-only (its trigger is unchanged);
-- this index lets the hourly sync insert every award it finds without ever counting one twice.
CREATE UNIQUE INDEX points_ledger_once ON points_ledger (contributor_code, event, ref_id) WHERE ref_id IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS points_ledger_once;
