-- migrate:up
-- L-NOTIFY and L-INBOX (BLD-A180, BLD-A200). `notify.post` keeps one item per person for a dedupe key (reminders,
-- retries, a request posted twice), and `notify.resolve` finds the open items by that key when the action is done
-- elsewhere (a team-up request withdrawn, answers sent). One key per person and channel: the in-app item and its
-- email are deduplicated together. Keys are IDs, enums and times only, never words (non-negotiable 3).
ALTER TABLE notifications
  ADD COLUMN dedupe_key text CONSTRAINT notifications_dedupe_key_check CHECK (dedupe_key ~ '^[A-Za-z0-9_.:+-]{1,200}$');
CREATE UNIQUE INDEX notifications_dedupe ON notifications (user_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX notifications_open_key ON notifications (dedupe_key) WHERE needs_you AND dedupe_key IS NOT NULL;

-- Teams messages are built and switched off until IT approves the Teams app (DEC-105). While off, nothing is queued
-- for Teams, and decisions, reversals and merges fall back to email (L-NOTIFY/4).
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
    ('comms.teams', 'off', 'Off until IT approves the Teams app for 1% Club messages (DEC-105)', 'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "off"}', reason
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'comms.teams';
DROP INDEX IF EXISTS notifications_open_key;
DROP INDEX IF EXISTS notifications_dedupe;
ALTER TABLE notifications DROP COLUMN IF EXISTS dedupe_key;
