-- migrate:up
-- Live scan progress over server-sent events (§8, week 3; replaces polling while on). Starts off (§7.6, DEC-057);
-- with it off the waiting screen polls exactly as on day one.
INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
  ('scan.live', 'off', 'New feature: off until its gates pass', 'migration')
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'scan.live';
