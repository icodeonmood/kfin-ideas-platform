-- migrate:up
-- L-DRAFT, the live draft (BLD-C070 to BLD-C079), on the cut-over's tables (20261121500100). New code sets
-- ideas.status and the draft columns, never ideas.stage. Every number the product promises (the minimum to check,
-- the 30 days a draft is kept) stays in rules/promises.md, never here.

-- One active editor at a time (L-DRAFT.autosave/5): the device that has the draft open now. An opaque per-device
-- id only, never a name, address or user agent.
ALTER TABLE ideas
  ADD COLUMN editor_device_id text        CONSTRAINT ideas_editor_device_id_check CHECK (char_length(editor_device_id) BETWEEN 8 AND 64),
  ADD COLUMN editor_device    text        CONSTRAINT ideas_editor_device_check CHECK (editor_device IN ('phone', 'laptop')),
  ADD COLUMN editor_at        timestamptz;

-- A message typed offline is sent again on reconnect with the id the device gave it (L-DRAFT.autosave/7): the same
-- id twice is one message, so nothing is kept twice and nothing typed is lost.
-- A voice note or a message in another language can carry an English translation (DEC-108), labelled as one: the
-- masked copy, sealed like text_encrypted ("idea_messages.text_en_encrypted:<id>"). Context for drafting only; the
-- quotes behind every suggestion still come from the person's own words (DEC-095).
ALTER TABLE idea_messages
  ADD COLUMN client_id         text  CONSTRAINT idea_messages_client_id_check CHECK (char_length(client_id) BETWEEN 8 AND 200),
  ADD COLUMN text_en_encrypted bytea;
CREATE UNIQUE INDEX idea_messages_client ON idea_messages (idea_uuid, client_id) WHERE client_id IS NOT NULL;
CREATE INDEX idea_messages_order ON idea_messages (idea_uuid, created_at, seq);

-- The newest run first per draft, and the 7-day p50 per part (L-DRAFT.parts/6) over finished runs.
CREATE INDEX draft_runs_running ON draft_runs (started_at) WHERE state = 'running';

-- The part agent (L-DRAFT.parts) has its own switch, on like the other agents; every call still needs `ai.all`,
-- which stays off until D1 is approved (DEC-105): then every part is filled by hand.
INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
  ('agent.draft-part', 'on', NULL, NULL)
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'agent.draft-part';
DROP INDEX IF EXISTS draft_runs_running;
DROP INDEX IF EXISTS idea_messages_order;
DROP INDEX IF EXISTS idea_messages_client;
ALTER TABLE idea_messages DROP COLUMN IF EXISTS text_en_encrypted, DROP COLUMN IF EXISTS client_id;
ALTER TABLE ideas
  DROP COLUMN IF EXISTS editor_at,
  DROP COLUMN IF EXISTS editor_device,
  DROP COLUMN IF EXISTS editor_device_id;
