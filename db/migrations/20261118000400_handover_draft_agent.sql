-- migrate:up
-- The handover-draft agent (BLD-138) drafts a picked idea's handover pack for its owner to edit; its own switch, so
-- it can be turned off without touching the rest of the assistant (§7.6, `agent.*`).
INSERT INTO kill_switches (name, state, reason, changed_by) VALUES ('agent.handover-draft', 'on', NULL, NULL)
  ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'agent.handover-draft';
