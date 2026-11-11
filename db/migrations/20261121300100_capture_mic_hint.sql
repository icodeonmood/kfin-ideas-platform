-- migrate:up
-- DEC-094 and DEC-096 (lane C, BLD-C001): quick capture is one box, and under it a tip suggests the phone
-- keyboard's mic. The tip has its own switch so an admin or InfoSec can hide it with a reason. Every feature is on
-- from day one (DEC-088), so it starts on; the insert is audited like any other switch change (§7.6).
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by)
  VALUES ('capture.mic_hint', 'on', 'DEC-096: the keyboard-mic tip under quick capture, on from day one (DEC-088)',
          'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "on"}',
       'DEC-096: the keyboard-mic tip under quick capture, on from day one (DEC-088)'
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'capture.mic_hint';
