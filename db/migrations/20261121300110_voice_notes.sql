-- migrate:up
-- DEC-096 (lane C, BLD-C003): voice notes in quick capture. A recording lives only in the quarantine bucket until it
-- has been heard; the text is held encrypted for the person to fetch, then everything goes (on fetch, on share, on
-- draft purge, or after 24 hours). The row stays as a tombstone so each deletion can be audited.
CREATE TABLE voice_notes (
  id                   uuid        PRIMARY KEY,
  -- RESTRICT, not CASCADE (BLD-C006): an idea cannot go while it holds voice notes, so every path that deletes
  -- ideas must call voice.service.drop_for_ideas first, which deletes the recordings from the bucket and audits it.
  idea_uuid            uuid        NOT NULL REFERENCES ideas (id) ON DELETE RESTRICT,
  uploaded_by_code     text        NOT NULL,
  mime                 text        NOT NULL CHECK (mime IN ('audio/webm', 'audio/ogg', 'audio/mp4', 'audio/wav')),
  bytes                integer     NOT NULL CHECK (bytes > 0),
  store_key            text,                    -- NULL once the recording is deleted
  state                text        NOT NULL DEFAULT 'quarantine'
                                   CHECK (state IN ('quarantine', 'transcribing', 'ready', 'failed')),
  failure              text        CHECK (failure ~ '^[a-z0-9_]+$'),  -- a code only, never text
  transcript_encrypted bytea,                   -- AES-GCM, context 'voice:<id>'; NULL once fetched or deleted
  removed_count        integer     NOT NULL DEFAULT 0,  -- values the patterns block, left out of the text
  language             text,
  created_at           timestamptz NOT NULL DEFAULT now(),
  delete_after         timestamptz NOT NULL DEFAULT now() + interval '24 hours',
  deleted_at           timestamptz
);
CREATE INDEX voice_notes_idea ON voice_notes (idea_uuid) WHERE deleted_at IS NULL;
CREATE INDEX voice_notes_due ON voice_notes (delete_after) WHERE deleted_at IS NULL;
-- Only the worker handles recordings and their text; the web app goes through /internal/voice.
REVOKE ALL ON voice_notes FROM ideas_web_svc;

-- Two switches (§7.6), OFF BY DESIGN: the first exceptions to DEC-088 (every feature on from day one). They start
-- off with these reasons, the go/no-go report prints them as "off as expected", and nobody switches them on until
-- the approvals in the reasons land:
-- capture.voice waits for IT's server memory, InfoSec (the microphone and the model) and the DPO's privacy notice
-- by go/no-go 2 (DEC-096); speech.hosted stays off until InfoSec and the DPO approve a hosted speech service, since
-- raw voice cannot be tagged before it leaves (non-negotiables 1 and 2; the same position as D1).
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
    ('capture.voice', 'off', 'Off until IT deploys the isolated speech service and the memory, InfoSec agrees to the microphone and the model, and the DPO''s privacy notice covers voice notes (DEC-096)', 'migration'),
    ('speech.hosted', 'off', 'Off until InfoSec and the DPO approve a hosted route (DEC-096)', 'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "off"}', reason
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name IN ('capture.voice', 'speech.hosted');
DROP TABLE IF EXISTS voice_notes;
