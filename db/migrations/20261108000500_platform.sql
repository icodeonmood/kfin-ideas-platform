-- migrate:up
-- Outbox, job queue, model-call log, pseudonym vault, autonomy, kill switches and audit (§2.5, §7.6).

-- Feeds the repo writer. Payload holds IDs and codes only (BLD-020); errors are stored as codes.
CREATE TABLE outbox (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_type   text        NOT NULL CHECK (event_type ~ '^[a-z_]+\.[a-z_]+$'),
  aggregate_id text        NOT NULL,
  actor        text        NOT NULL CHECK (actor ~ '^(CTR-[0-9a-f]{6,8}|REV-[0-9]{4}|system|process:[a-z0-9._-]+)$'),
  payload      jsonb       NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now(),
  committed_at timestamptz,
  commit_sha   text        CHECK (commit_sha ~ '^[0-9a-f]{40}$'),
  attempts     integer     NOT NULL DEFAULT 0,
  last_error   text        CHECK (last_error ~ '^[A-Za-z0-9_.:-]{1,120}$'),
  CHECK ((committed_at IS NULL) = (commit_sha IS NULL))
);
CREATE INDEX outbox_pending ON outbox (id) WHERE committed_at IS NULL;

-- Job queue, claimed with SELECT … FOR UPDATE SKIP LOCKED.
CREATE TABLE jobs (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  type         text        NOT NULL CHECK (type ~ '^[a-z_]+(\.[a-z_]+)*$'),
  payload      jsonb       NOT NULL DEFAULT '{}',
  run_at       timestamptz NOT NULL DEFAULT now(),
  state        text        NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'done', 'failed', 'dead')),
  attempts     integer     NOT NULL DEFAULT 0,
  max_attempts integer     NOT NULL DEFAULT 5,
  locked_by    text,
  locked_at    timestamptz,
  last_error   text        CHECK (last_error ~ '^[A-Za-z0-9_.:-]{1,120}$'),
  dedupe_key   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX jobs_ready ON jobs (run_at) WHERE state = 'queued';
CREATE UNIQUE INDEX jobs_dedupe ON jobs (dedupe_key) WHERE dedupe_key IS NOT NULL AND state IN ('queued', 'running');
CREATE TRIGGER jobs_updated_at BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- One row per model call. No prompt or response text, by design (§3.2 step 9).
CREATE TABLE llm_calls (
  id             bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  agent          text          NOT NULL,
  prompt_version text          NOT NULL,
  model          text          NOT NULL,
  input_tokens   integer,
  output_tokens  integer,
  latency_ms     integer,
  cost_inr       numeric(10,4),
  tags_by_type   jsonb         NOT NULL DEFAULT '{}',
  outcome        text          NOT NULL CHECK (outcome IN (
                   'ok', 'ok_after_retry', 'cached', 'agent_failed', 'leak_abort', 'tag_mismatch',
                   'route_error', 'switched_off')),
  ref_id         text,
  created_at     timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX llm_calls_created ON llm_calls (created_at);
CREATE INDEX llm_calls_outcome ON llm_calls (outcome, created_at);

-- Tag map (tag → real value), scoped to an idea or cluster. Values encrypted; lookups by keyed hash.
-- Readable only by the gateway's restore service (database roles arrive with the gateway in B4).
CREATE TABLE pseudonym_vault (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scope_id        text        NOT NULL CHECK (scope_id ~ '^(IDEA-[0-9]{4}-[0-9]{6}|CL-[0-9]{4}|DRAFT-[0-9a-f-]{36})$'),
  tag             text        NOT NULL CHECK (tag ~ '^\[\[[A-Z_]+_[0-9]+\]\]$'),
  type            text        NOT NULL,
  value_hmac      bytea       NOT NULL,
  value_encrypted bytea       NOT NULL,
  subject_user_id uuid        REFERENCES users (id) ON DELETE CASCADE,   -- erasure on exit (§6.2)
  created_at      timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz,
  UNIQUE (scope_id, tag),
  UNIQUE (scope_id, value_hmac)
);

CREATE TABLE autonomy (
  action_type        text         PRIMARY KEY CHECK (action_type IN (
                       'accept_area_tags', 'accept_scope', 'attach_to_cluster', 'mark_as_new')),
  mode               text         NOT NULL DEFAULT 'gated' CHECK (mode IN ('gated', 'auto')),
  window_accept_rate numeric(5,4),
  window_size        integer      NOT NULL DEFAULT 0,
  changed_by         text,
  changed_at         timestamptz
);
INSERT INTO autonomy (action_type) VALUES
  ('accept_area_tags'), ('accept_scope'), ('attach_to_cluster'), ('mark_as_new');

-- §7.6. "on" means the feature runs; "off" means it is killed. Read on every request, cached 10 s.
CREATE TABLE kill_switches (
  name       text        PRIMARY KEY CHECK (name ~ '^[a-z]+(\.[a-z_-]+)?$'),
  state      text        NOT NULL DEFAULT 'on' CHECK (state IN ('on', 'off')),
  reason     text,
  changed_by text,
  changed_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO kill_switches (name) VALUES
  ('ai.all'), ('agent.gatekeeper'), ('agent.canvas-assist'), ('agent.judge'),
  ('attachments.upload'), ('attachments.open'), ('submissions'), ('matching.show'),
  ('comms.email'), ('wall.public');

-- Every privileged action and every identity reveal. Append-only.
CREATE TABLE audit_log (
  id     bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor  text        NOT NULL,
  action text        NOT NULL,
  entity text        NOT NULL,
  before jsonb,
  after  jsonb,
  reason text,
  at     timestamptz NOT NULL DEFAULT now(),
  ip     inet
);
CREATE INDEX audit_log_entity ON audit_log (entity, at);
CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();

-- migrate:down
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS kill_switches;
DROP TABLE IF EXISTS autonomy;
DROP TABLE IF EXISTS pseudonym_vault;
DROP TABLE IF EXISTS llm_calls;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS outbox;
