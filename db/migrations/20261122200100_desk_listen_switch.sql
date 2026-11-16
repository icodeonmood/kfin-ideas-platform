-- migrate:up
-- BLD-B230 (lane B): the review desk's listen player has its own switch, so it can be taken away on its own; it is
-- first in Thursday's drop order (SHIP_PLAN §4). Every feature is on from day one (DEC-088), so it starts on; the
-- insert is audited like any other switch change (§7.6).
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by)
  VALUES ('desk.listen', 'on', 'BLD-B230: the review desk''s listen player, on from day one (DEC-088)', 'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "on"}',
       'BLD-B230: the review desk''s listen player, on from day one (DEC-088)'
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'desk.listen';
