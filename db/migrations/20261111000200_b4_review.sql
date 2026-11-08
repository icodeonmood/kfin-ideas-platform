-- migrate:up
-- B4 review fixes (BLD-081).
-- Tag numbers per scope and type only ever go up, so a deleted vault row (erasure, expiry) can never hand its
-- number to a different value that stored outputs would then restore to.
CREATE TABLE vault_counters (
  scope_id text    NOT NULL,
  type     text    NOT NULL,
  last     integer NOT NULL,
  PRIMARY KEY (scope_id, type)
);
INSERT INTO vault_counters (scope_id, type, last)
SELECT scope_id, type, max(substring(tag from '_([0-9]+)\]\]$')::int) FROM pseudonym_vault GROUP BY scope_id, type;
REVOKE ALL ON vault_counters FROM ideas_web_svc;

-- The web app records a person's choice on a scan; it never writes the scan's results or timing.
REVOKE INSERT, UPDATE ON scans FROM ideas_web_svc;
GRANT UPDATE (overrides, override_reason_encrypted, state, step, outcome, finished_at) ON scans TO ideas_web_svc;

-- migrate:down
GRANT INSERT, UPDATE ON scans TO ideas_web_svc;
DROP TABLE IF EXISTS vault_counters;
