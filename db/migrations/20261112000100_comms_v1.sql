-- migrate:up
-- Communication module v1 (§3.7, BLD-088). A notification holds the event and IDs only; its text is rendered
-- from the repo's templates when it is sent or viewed, so no message text sits in the database.
ALTER TABLE notifications ADD COLUMN event        text;
ALTER TABLE notifications ADD COLUMN urgency      text CHECK (urgency IN ('immediate', 'routine'));
ALTER TABLE notifications ADD COLUMN send_after   timestamptz;
ALTER TABLE notifications ADD COLUMN attempts     integer NOT NULL DEFAULT 0;
ALTER TABLE notifications ADD COLUMN error_code   text CHECK (error_code ~ '^[a-z0-9_.]{1,60}$');
ALTER TABLE notifications ADD COLUMN comms_log_id bigint REFERENCES comms_log (id) ON DELETE SET NULL;
CREATE INDEX notifications_due ON notifications (send_after) WHERE state = 'queued' AND channel = 'email';

-- A reviewer's question and the person's answer (needs_info). Text is tagged and encrypted.
CREATE TABLE idea_questions (
  id                 bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid          uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  review_item_id     bigint      REFERENCES review_items (id) ON DELETE SET NULL,
  asked_by           uuid        REFERENCES users (id) ON DELETE SET NULL,
  question_encrypted bytea       NOT NULL,
  answer_encrypted   bytea,
  asked_at           timestamptz NOT NULL DEFAULT now(),
  due_at             timestamptz NOT NULL,
  answered_at        timestamptz
);
CREATE INDEX idea_questions_open ON idea_questions (idea_uuid) WHERE answered_at IS NULL;

-- migrate:down
DROP TABLE IF EXISTS idea_questions;
DROP INDEX IF EXISTS notifications_due;
ALTER TABLE notifications DROP COLUMN IF EXISTS comms_log_id;
ALTER TABLE notifications DROP COLUMN IF EXISTS error_code;
ALTER TABLE notifications DROP COLUMN IF EXISTS attempts;
ALTER TABLE notifications DROP COLUMN IF EXISTS send_after;
ALTER TABLE notifications DROP COLUMN IF EXISTS urgency;
ALTER TABLE notifications DROP COLUMN IF EXISTS event;
