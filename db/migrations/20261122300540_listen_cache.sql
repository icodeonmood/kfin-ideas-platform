-- migrate:up
-- DEC-108 (4), L-LISTEN, lane C BLD-C114: Listen's audio in Sarvam's voice (bulbul:v4-flash), made from lane B's masked
-- script, cached per (script version, voice) with its chapters. The object is in the clean bucket under `listen/`;
-- this row holds where, the chapters ({part, start_s}, each part's length computed from the audio) and the total.
-- No text: the script is lane B's and masked. A new version (an edit, an answer, a revised worth) replaces the
-- idea's older rows (L-LISTEN/3); rows older than 30 days are swept with their objects.
CREATE TABLE listen_cache (
  idea_uuid   uuid          NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  version     text          NOT NULL CHECK (version ~ '^[A-Za-z0-9_-]{8,64}$'),
  voice       text          NOT NULL CHECK (voice ~ '^[a-z0-9_]{1,60}$'),
  lang        text          NOT NULL CHECK (lang ~ '^[a-z]{2,3}-IN$'),
  store_key   text          NOT NULL,
  chapters    jsonb         NOT NULL,
  duration_s  numeric(8,2)  NOT NULL CHECK (duration_s >= 0),
  byte_count  integer       NOT NULL CHECK (byte_count >= 0),
  created_at  timestamptz   NOT NULL DEFAULT now(),
  PRIMARY KEY (idea_uuid, version, voice)
);
CREATE INDEX listen_cache_created ON listen_cache (created_at);
-- The worker makes and serves the audio; the web app reads nothing here directly.
REVOKE INSERT, UPDATE, DELETE ON listen_cache FROM ideas_web_svc;

-- A prefetch that failed for a script and voice is remembered, so the 15-minute prefetch waits 6 hours before trying
-- again instead of paying for the parts that worked every time (BLD-C117). A code only, never text.
CREATE TABLE listen_failures (
  idea_uuid   uuid          NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  version     text          NOT NULL CHECK (version ~ '^[A-Za-z0-9_-]{8,64}$'),
  voice       text          NOT NULL CHECK (voice ~ '^[a-z0-9_]{1,60}$'),
  error_code  text          NOT NULL CHECK (error_code ~ '^[a-z0-9_.]{1,60}$'),
  attempts    integer       NOT NULL DEFAULT 1 CHECK (attempts > 0),
  failed_at   timestamptz   NOT NULL DEFAULT now(),
  PRIMARY KEY (idea_uuid, version, voice)
);
REVOKE INSERT, UPDATE, DELETE ON listen_failures FROM ideas_web_svc;

-- migrate:down
DROP TABLE IF EXISTS listen_failures;
DROP TABLE IF EXISTS listen_cache;
