-- migrate:up
-- Gateway cache (§3.2 step 4). The key is a hash of agent, version, model and the TAGGED inputs, so the cache
-- never holds real values. The output is stored encrypted because it carries tagged idea text, and plain
-- columns must never hold idea sentences (AT-B4-06, BLD-071).
CREATE TABLE llm_cache (
  key              bytea       PRIMARY KEY,
  agent            text        NOT NULL,
  version          text        NOT NULL,
  output_encrypted bytea       NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  expires_at       timestamptz NOT NULL
);
CREATE INDEX llm_cache_expiry ON llm_cache (expires_at);

-- Cached and switched-off calls have no model; agent errors carry a code, never text.
ALTER TABLE llm_calls ADD COLUMN cache_read_tokens integer;
ALTER TABLE llm_calls ADD COLUMN error_code text CHECK (error_code ~ '^[a-z0-9_.]{1,60}$');
CREATE INDEX llm_calls_agent ON llm_calls (agent, created_at);

-- migrate:down
DROP INDEX IF EXISTS llm_calls_agent;
ALTER TABLE llm_calls DROP COLUMN IF EXISTS error_code;
ALTER TABLE llm_calls DROP COLUMN IF EXISTS cache_read_tokens;
DROP TABLE IF EXISTS llm_cache;
