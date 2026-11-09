-- migrate:up
-- The committee flow (§4.5–§4.7) starts switched off (§7.6, DEC-057) until its gates pass; its agents start on so
-- they run as soon as the flow does (each still needs `ai.all`).
INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
  ('committee.flow', 'off', 'New feature: off until its gates pass', 'migration'),
  ('agent.prescore', 'on', NULL, NULL),
  ('agent.pitch-prep', 'on', NULL, NULL),
  ('agent.collation', 'on', NULL, NULL),
  ('agent.reason-writer', 'on', NULL, NULL)
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name IN ('committee.flow', 'agent.prescore', 'agent.pitch-prep', 'agent.collation',
  'agent.reason-writer');
