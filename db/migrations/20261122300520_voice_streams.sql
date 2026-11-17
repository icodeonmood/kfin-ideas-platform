-- migrate:up
-- DEC-108 (2), lane C BLD-C112: a voice note for a draft, streamed to Sarvam through the worker as the person speaks.
-- The audio is relayed and never stored, decoded or opened here: no recording exists, so there is no file, no bucket
-- object and no virus scan step. One row per stream holds counts while it is live, then what was heard until the
-- draft takes it as a message (voice_to_message) or 24 hours pass:
--   * own_words_sealed: the person's own words as heard, unmasked, encrypted with the vault key (DEC-103: readable
--     by them alone). Worker only.
--   * masked_encrypted: the same words masked (kind + •••• + last two characters), the copy anyone else may see.
--   * text_en_encrypted: the English translation of the masked words (mayura:v1), itself masked again.
-- WORKER ONLY: the web role is revoked below and the table is pinned in tests/test_b4_service_roles.py.
CREATE TABLE voice_streams (
  id                 uuid          PRIMARY KEY,
  -- CASCADE is safe here: unlike voice_notes there is no recording in a bucket to delete first.
  idea_uuid          uuid          NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  by_code            text          NOT NULL,
  state              text          NOT NULL DEFAULT 'live' CHECK (state IN ('live', 'done', 'failed')),
  failure            text          CHECK (failure ~ '^[a-z0-9_]+$'),     -- a code only, never text
  ended_by           text          CHECK (ended_by IN ('person', 'idle', 'limit', 'replaced', 'paused')),
  speech_seconds     numeric(6,2)  NOT NULL DEFAULT 0 CHECK (speech_seconds >= 0),
  chunk_count        integer       NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
  lang               text          CHECK (lang ~ '^[a-z]{2,3}-IN$'),
  own_words_sealed   bytea,
  masked_encrypted   bytea,
  text_en_encrypted  bytea,
  translated         boolean,
  spans              jsonb         NOT NULL DEFAULT '[]',                -- [{start, end, kind}], never values
  hidden_count       integer       NOT NULL DEFAULT 0 CHECK (hidden_count >= 0),
  created_at         timestamptz   NOT NULL DEFAULT now(),
  ended_at           timestamptz,
  handed_at          timestamptz,                                         -- taken by the draft as a message
  delete_after       timestamptz   NOT NULL DEFAULT now() + interval '24 hours'
);
CREATE INDEX voice_streams_idea ON voice_streams (idea_uuid, created_at DESC);
CREATE INDEX voice_streams_person_hour ON voice_streams (by_code, created_at);
CREATE INDEX voice_streams_due ON voice_streams (delete_after) WHERE own_words_sealed IS NOT NULL;
REVOKE ALL ON voice_streams FROM ideas_web_svc;

-- migrate:down
DROP TABLE IF EXISTS voice_streams;
