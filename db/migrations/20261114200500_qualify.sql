-- migrate:up
-- Qualify (§4.5): the four gates for an approved cluster, the impact estimate, and the route to a committee.
-- Gate evidence holds IDs, counts and codes; notes are tagged under the cluster's scope.

ALTER TABLE review_items DROP CONSTRAINT review_items_item_type_check;
ALTER TABLE review_items ADD CONSTRAINT review_items_item_type_check CHECK (item_type IN (
  'idea', 'cluster_proposal', 'taxonomy_proposal', 'glossary_proposal', 'working_group_trigger', 'disagreement',
  'qualify'));

ALTER TABLE clusters
  ADD COLUMN route_lob     text CHECK (route_lob ~ '^LOB-[a-z0-9-]+$'),   -- route_to = 'lob'
  ADD COLUMN reason_code   text,                                       -- a gate outcome: ALREADY_SOLVED …
  ADD COLUMN qualified_at  timestamptz;

CREATE TABLE cluster_gates (
  cluster_id   text        NOT NULL REFERENCES clusters (id),
  gate         text        NOT NULL CHECK (gate IN ('evidence', 'not_solved', 'not_planned', 'no_conflict')),
  proposed     text        NOT NULL CHECK (proposed IN ('pass', 'fail', 'check')),   -- the rules' pre-check
  evidence     jsonb       NOT NULL DEFAULT '{}',                                     -- IDs, counts, codes
  result       text        CHECK (result IN ('pass', 'fail')),                       -- the reviewer's call
  detail       text        CHECK (detail IN ('clear', 'clear_with_conditions', 'conflict')),  -- no_conflict only
  note         text,                                                                  -- tagged
  confirmed_by text        CHECK (confirmed_by ~ '^REV-[0-9]{4}$'),
  confirmed_at timestamptz,
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (cluster_id, gate)
);
CREATE TRIGGER cluster_gates_updated_at BEFORE UPDATE ON cluster_gates FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE impact_estimates (
  cluster_id         text        PRIMARY KEY REFERENCES clusters (id),
  version            integer     NOT NULL DEFAULT 1,
  fields             jsonb       NOT NULL DEFAULT '{}',   -- the §4.5 step 2 form: numbers, units fixed
  basis              jsonb       NOT NULL DEFAULT '{}',   -- where each prefilled number came from (IDEA- IDs)
  annual_net_benefit numeric,
  payback_months     numeric,
  finance_required   boolean     NOT NULL DEFAULT false,
  finance_validated_by text      CHECK (finance_validated_by ~ '^REV-[0-9]{4}$'),
  finance_validated_at timestamptz,
  updated_by         text        CHECK (updated_by ~ '^REV-[0-9]{4}$'),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER impact_estimates_updated_at BEFORE UPDATE ON impact_estimates FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- migrate:down
DROP TABLE IF EXISTS impact_estimates;
DROP TABLE IF EXISTS cluster_gates;
ALTER TABLE clusters DROP COLUMN IF EXISTS route_lob, DROP COLUMN IF EXISTS reason_code, DROP COLUMN IF EXISTS qualified_at;
DELETE FROM review_items WHERE item_type = 'qualify';
ALTER TABLE review_items DROP CONSTRAINT review_items_item_type_check;
ALTER TABLE review_items ADD CONSTRAINT review_items_item_type_check CHECK (item_type IN (
  'idea', 'cluster_proposal', 'taxonomy_proposal', 'glossary_proposal', 'working_group_trigger', 'disagreement'));
