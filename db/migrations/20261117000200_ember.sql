-- migrate:up
-- The Ember, the monthly newsletter (DEC-062, DEC-070, DEC-079; BLD-128). An admin drafts the month's issue,
-- the core committee chair types a note, the admin sends it to everyone. A sent issue keeps what it said
-- (`content`), built only from what everyone may already see: consented names, checked summaries, counts.
CREATE TABLE ember_issues (
  id                   bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  month                date        NOT NULL UNIQUE CHECK (extract(day FROM month) = 1),
  state                text        NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'sent')),
  chair_note_encrypted bytea,      -- checked text, encrypted until the issue is sent
  chair_note_by        uuid        REFERENCES users (id) ON DELETE RESTRICT,
  content              jsonb,      -- the issue as sent
  created_by           uuid        REFERENCES users (id) ON DELETE RESTRICT,
  sent_by              uuid        REFERENCES users (id) ON DELETE RESTRICT,
  sent_at              timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  CHECK ((state = 'sent') = (sent_at IS NOT NULL AND content IS NOT NULL))
);
CREATE INDEX ember_issues_sent ON ember_issues (sent_at DESC) WHERE state = 'sent';
CREATE TRIGGER ember_issues_updated_at BEFORE UPDATE ON ember_issues FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO kill_switches (name) VALUES ('ember.send') ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'ember.send';
DROP TABLE IF EXISTS ember_issues;
