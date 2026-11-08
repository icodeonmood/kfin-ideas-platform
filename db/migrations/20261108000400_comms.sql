-- migrate:up
-- In-app inbox and the send log (§3.7). Bodies are rendered from comms/templates/ at send time,
-- so neither table stores message text (BLD-020).

CREATE TABLE notifications (
  id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  channel    text        NOT NULL CHECK (channel IN ('in_app', 'email', 'teams', 'digest')),
  template   text        NOT NULL,
  payload    jsonb       NOT NULL DEFAULT '{}',        -- IDs and template variables by reference
  state      text        NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'held', 'sent', 'failed', 'read')),
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at    timestamptz,
  read_at    timestamptz
);
CREATE INDEX notifications_user ON notifications (user_id, created_at DESC);
CREATE INDEX notifications_queue ON notifications (state, created_at) WHERE state IN ('queued', 'held');

CREATE TABLE comms_log (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event            text        NOT NULL,
  template_version text        NOT NULL,
  recipients       uuid[]      NOT NULL,
  channel          text        NOT NULL CHECK (channel IN ('in_app', 'email', 'teams', 'calendar', 'manager_note', 'digest')),
  signer_id        uuid        REFERENCES users (id) ON DELETE SET NULL,
  approved_at      timestamptz,
  sent_at          timestamptz,
  state            text        NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'awaiting_approval', 'held', 'sent', 'failed')),
  read_at          timestamptz,                         -- in-app only; email opens are never tracked
  message_ref      text,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX comms_log_event ON comms_log (event, created_at);

-- migrate:down
DROP TABLE IF EXISTS comms_log;
DROP TABLE IF EXISTS notifications;
