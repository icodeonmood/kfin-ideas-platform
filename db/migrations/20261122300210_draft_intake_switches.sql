-- migrate:up
-- L-DRAFT.channels (BLD-C077): a forwarded email or a Teams message lands as a draft. Built and off until IT gives
-- the 1% Club mailbox and the Teams app (DEC-105); nobody switches them on before then.
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
    ('intake.email', 'off', 'Off until IT gives the 1% Club mailbox (DEC-105): forwarded emails land as drafts once it is on', 'migration'),
    ('intake.teams', 'off', 'Off until IT gives the 1% Club Teams app (DEC-105): Teams messages land as drafts once it is on', 'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "off"}', reason
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name IN ('intake.email', 'intake.teams');
