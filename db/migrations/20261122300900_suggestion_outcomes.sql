-- migrate:up
-- DEC-122 (lane C, BLD-C207): the assistant's suggestions kept beside what people did with them, so they can be tuned
-- or trained on later. Append-only and worker-only; masked text only, never the sharer's sealed words or restored
-- tags. Removed with the idea. Writing stays switched off (`learning.outcomes`, below) until the privacy notice
-- names this purpose and the product lead switches it on; nothing is written while the assistant is off either.
CREATE TABLE suggestion_outcomes (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid      uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  -- a draft part (L-DRAFT.parts) or a sorting field (L-SORT.fields)
  field          text        NOT NULL CHECK (field IN (
                   'title', 'summary', 'often', 'who', 'value', 'area',
                   'sorting.affects', 'sorting.kind', 'sorting.area', 'sorting.brings')),
  suggested      jsonb       NOT NULL,   -- as the model returned it, masked, tags as stored
  final          jsonb,                  -- what the person kept, masked; NULL when asked again before choosing
  outcome        text        NOT NULL CHECK (outcome IN ('accepted', 'changed', 'pinned', 'suggested_again')),
  agent          text        NOT NULL CHECK (agent ~ '^[a-z][a-z0-9-]{1,40}$'),
  agent_version  text        NOT NULL CHECK (agent_version ~ '^[0-9A-Za-z.+-]{1,20}$'),
  run_id         uuid,                   -- the draft run that suggested it, when known
  side           text        NOT NULL CHECK (side IN ('sharer', 'reviewer')),
  at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX suggestion_outcomes_idea ON suggestion_outcomes (idea_uuid);
CREATE INDEX suggestion_outcomes_at ON suggestion_outcomes (at);
-- Worker-only (non-negotiable 6's pinned list, test_b4_service_roles.py) and append-only: the worker adds rows and
-- reads them; the idea's removal takes its rows with it (the cascade runs as the table's owner).
REVOKE ALL ON suggestion_outcomes FROM ideas_web_svc;
REVOKE UPDATE, DELETE, TRUNCATE ON suggestion_outcomes FROM ideas_worker_svc;

-- Writing starts off (DEC-122): the privacy notice does not name this purpose yet. Audited like any other switch
-- change (§7.6); the go/no-go report lists it as off by design.
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by)
  VALUES ('learning.outcomes', 'off', 'Off until the privacy notice names this purpose (DEC-122)', 'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "off"}',
       'Off until the privacy notice names this purpose (DEC-122)'
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'learning.outcomes';
DROP TABLE IF EXISTS suggestion_outcomes;
