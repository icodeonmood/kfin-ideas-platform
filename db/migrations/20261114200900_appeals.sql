-- Appeals (§4.12, BLD-222): one per decision. A LOB committee's decision is heard by the core committee; a core
-- committee decision by a panel of three. The statement is tagged under the cluster's scope; evidence links are
-- stored as given and never fetched (non-negotiable 8). A preliminary review's park or decline is a decision too,
-- so `decisions` gains the round it came from.

-- migrate:up
ALTER TABLE decisions ADD COLUMN round_id text REFERENCES scoring_rounds (id);
ALTER TABLE decisions ALTER COLUMN members_present SET DEFAULT 0;

CREATE TABLE appeals (
  id                text        PRIMARY KEY CHECK (id ~ '^APL-[0-9]{4}-[0-9]{4}$'),
  decision_id       text        NOT NULL UNIQUE REFERENCES decisions (id),          -- one appeal per decision
  cluster_id        text        NOT NULL REFERENCES clusters (id),
  appellant_code    text        NOT NULL CHECK (appellant_code ~ '^CTR-[0-9a-f]{6,8}$'),
  grounds           text[]      NOT NULL CHECK (cardinality(grounds) > 0 AND grounds <@ ARRAY['process_not_followed', 'misunderstood_or_wrongly_merged', 'new_evidence']),
  statement         text        NOT NULL,                                           -- tagged
  links             jsonb       NOT NULL DEFAULT '[]',                              -- as given, never fetched
  hearing_requested boolean     NOT NULL DEFAULT false,
  heard_by          text        NOT NULL CHECK (heard_by IN ('panel', 'core_committee')),
  panel             uuid[]      NOT NULL CHECK (cardinality(panel) > 0),            -- the first member chairs
  state             text        NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'decided')),
  outcome           text        CHECK (outcome IN ('upheld', 're_score', 'overturned')),
  reasons           text,                                                           -- tagged
  due_at            timestamptz NOT NULL,
  filed_at          timestamptz NOT NULL DEFAULT now(),
  decided_by        text        CHECK (decided_by ~ '^REV-[0-9]{4}$'),
  decided_at        timestamptz,
  repo_path         text,
  repo_commit       text,
  CHECK ((state = 'open') = (outcome IS NULL))
);
CREATE INDEX appeals_cluster ON appeals (cluster_id);

-- Appeals hold the appellant's statement: the web app reads them through the worker only.
REVOKE ALL ON appeals FROM ideas_web_svc;

INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
  ('appeals.filing', 'off', 'New feature: off until its gates pass', 'migration')
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'appeals.filing';
DROP TABLE IF EXISTS appeals;
ALTER TABLE decisions ALTER COLUMN members_present DROP DEFAULT;
ALTER TABLE decisions DROP COLUMN IF EXISTS round_id;
