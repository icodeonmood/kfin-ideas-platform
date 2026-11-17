-- migrate:up
-- DEC-108 (lane C, BLD-C110): every call to Sarvam, metered like llm_calls. IDs, seconds, characters, an outcome and
-- a code only: never audio, text, a transcript or the key (non-negotiable 3). Cost is by seconds of speech (speech to
-- text) or characters (translation, text to speech). The gateway switches `speech.hosted` off, audited, when route
-- errors pass the agents' error rate over 15 minutes (rules `kill_switch_triggers.speech_error_rate_15min`).
CREATE TABLE speech_calls (
  id             bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  call           text          NOT NULL CHECK (call IN ('stt_rest', 'stt_stream', 'translate', 'tts')),
  model          text          NOT NULL CHECK (model ~ '^[a-z0-9:._-]{1,40}$'),
  ref_id         text          CHECK (ref_id ~ '^[A-Za-z0-9:_-]{1,80}$'),   -- a stream, voice note or idea id
  -- bad_input: refused for what we sent (400, 413, 422: bad or too short audio), never counted toward the switch-off
  outcome        text          NOT NULL CHECK (outcome IN ('ok', 'ok_after_retry', 'route_error', 'bad_input', 'cancelled')),
  error_code     text          CHECK (error_code ~ '^[a-z0-9_.]{1,60}$'),
  speech_seconds numeric(8,2)  CHECK (speech_seconds >= 0),
  char_count     integer       CHECK (char_count >= 0),
  latency_ms     integer       CHECK (latency_ms >= 0),
  cost_inr       numeric(10,4),
  created_at     timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX speech_calls_created ON speech_calls (created_at);
CREATE INDEX speech_calls_outcome ON speech_calls (outcome, created_at);
-- Like llm_calls: the web app may read the counts, never write them.
REVOKE INSERT, UPDATE, DELETE ON speech_calls FROM ideas_web_svc;

-- migrate:down
DROP TABLE IF EXISTS speech_calls;
