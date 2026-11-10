-- migrate:up
-- DEC-088: every feature is on from day one. Five features shipped switched off ("off until its gates pass"):
-- weekly grouping, deep file checks, live scan progress, the committee flow and appeals. They now start on.
-- Only a row still in the state its own migration left it is changed, so a switch that an admin, a test or the
-- watch process has changed since keeps its state. Each change is audited like any other switch change (§7.6).
WITH changed AS (
  UPDATE kill_switches
     SET state = 'on',
         reason = 'DEC-088: every feature is on from day one',
         changed_by = 'migration',
         changed_at = now()
   WHERE name IN ('clusters.batch', 'attachments.deep_check', 'scan.live', 'committee.flow', 'appeals.filing')
     AND state = 'off'
     AND changed_by = 'migration'
  RETURNING name
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, '{"state": "off"}', '{"state": "on"}',
       'DEC-088: every feature is on from day one'
  FROM changed;

-- migrate:down
-- Puts back only what this migration switched on and nobody has changed since; the audit trail is append-only.
WITH changed AS (
  UPDATE kill_switches
     SET state = 'off',
         reason = 'New feature: off until its gates pass',
         changed_by = 'migration',
         changed_at = now()
   WHERE name IN ('clusters.batch', 'attachments.deep_check', 'scan.live', 'committee.flow', 'appeals.filing')
     AND state = 'on'
     AND changed_by = 'migration'
     AND reason = 'DEC-088: every feature is on from day one'
  RETURNING name
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, '{"state": "on"}', '{"state": "off"}',
       'Rolled back DEC-088 migration'
  FROM changed;
