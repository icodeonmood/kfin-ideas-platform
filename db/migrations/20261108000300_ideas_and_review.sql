-- migrate:up
-- Ideas, attachments, links, clusters, the review queue, corrections, timers and points (§2.5).
-- Text lives only in ideas (and the search index); other tables hold IDs and codes (BLD-020).

CREATE TABLE ideas (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),   -- drafts exist before an IDEA- ID
  idea_id           text        UNIQUE CHECK (idea_id ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  submission_id     text        UNIQUE CHECK (submission_id ~ '^SUB-[0-9]{4}-[0-9]{6}$'),
  stage             text        NOT NULL DEFAULT 'draft' CHECK (stage IN (
                      'draft', 'scanning', 'blocked', 'redirected', 'scanned', 'merged', 'adoption_requested',
                      'reviewed', 'needs_info', 'withdrawn', 'in_cluster', 'ready_for_scoring', 'already_solved',
                      'already_planned', 'parked', 'declined', 'scored', 'shortlisted', 'presenting', 'picked',
                      'appealed', 'handover', 'in_garage', 'in_fix_track', 'shipped', 'resolved', 'measuring', 'closed')),
  capture_mode      text        NOT NULL DEFAULT 'full' CHECK (capture_mode IN ('quick', 'full')),
  kind              text        CHECK (kind IN ('problem', 'problem_with_solution', 'business_idea')),
  category          text        CHECK (category IN ('cost_saving', 'new_revenue', 'both', 'not_sure')),
  play              text        CHECK (play IN ('process_improvement', 'upsell', 'cross_sell', 'new_product', 'other')),
  basis             text        CHECK (basis IN ('own_data', 'document', 'conversation', 'hunch')),
  strength          smallint    CHECK (strength BETWEEN 0 AND 5),
  scope             text        CHECK (scope IN ('lob', 'cross-lob', 'org-wide')),
  area_ids          text[]      NOT NULL DEFAULT '{}',
  lobs              text[]      NOT NULL DEFAULT '{}',
  systems           text[]      NOT NULL DEFAULT '{}',
  roles_affected    text[]      NOT NULL DEFAULT '{}',
  cluster_id        text        CHECK (cluster_id ~ '^CL-[0-9]{4}$'),
  visibility        text        NOT NULL DEFAULT 'org' CHECK (visibility IN ('org', 'committee')),
  visibility_reason text,
  contributor_code  text        NOT NULL CHECK (contributor_code ~ '^CTR-[0-9a-f]{6,8}$'),  -- no FK: erasure deletes the map row only
  language          text,
  canvas            jsonb,      -- the confirmed card: tagged values only, with provenance (§4.2 step 4)
  draft_encrypted   bytea,      -- draft while stage = draft; encrypted; purged after 30 days
  raw_encrypted     bytea,      -- submitted text waiting for a passing scan; encrypted; cleared after
  repo_path         text,
  repo_commit       text,
  submitted_at      timestamptz,
  draft_expires_at  timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CHECK ((idea_id IS NULL) = (submission_id IS NULL)),
  CHECK (idea_id IS NULL OR substr(idea_id, 6) = substr(submission_id, 5))   -- same year and number
);
CREATE INDEX ideas_stage        ON ideas (stage);
CREATE INDEX ideas_contributor  ON ideas (contributor_code);
CREATE INDEX ideas_cluster      ON ideas (cluster_id);
CREATE INDEX ideas_draft_expiry ON ideas (draft_expires_at) WHERE stage = 'draft';
CREATE TRIGGER ideas_updated_at BEFORE UPDATE ON ideas FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE attachments (
  id               text        PRIMARY KEY CHECK (id ~ '^ATT-[0-9]{4}-[0-9]{6}$'),
  idea_uuid        uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  uploaded_by_code text        NOT NULL CHECK (uploaded_by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  name             text        NOT NULL,
  mime             text,
  bytes            bigint      NOT NULL CHECK (bytes >= 0),
  sha256           text        CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  store_key        text        NOT NULL,
  state            text        NOT NULL DEFAULT 'quarantine'
                     CHECK (state IN ('quarantine', 'processing', 'awaiting_check', 'clean', 'rejected')),
  rejection        jsonb,      -- {type, location}: data type and page/sheet/cell, never the value
  digest           text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX attachments_idea ON attachments (idea_uuid);
CREATE TRIGGER attachments_updated_at BEFORE UPDATE ON attachments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Joins, +1s and adoption requests. Exactly one target per row.
CREATE TABLE idea_links (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_id          text        CHECK (idea_id ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  cluster_id       text        CHECK (cluster_id ~ '^CL-[0-9]{4}$'),
  solution_id      text        CHECK (solution_id ~ '^SOL-[0-9]{4}$'),
  from_idea_id     text        CHECK (from_idea_id ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  contributor_code text        NOT NULL CHECK (contributor_code ~ '^CTR-[0-9a-f]{6,8}$'),
  link_type        text        NOT NULL CHECK (link_type IN ('originator', 'joiner', 'plus_one', 'adoption')),
  context_text     text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(idea_id, cluster_id, solution_id) = 1)
);
CREATE UNIQUE INDEX idea_links_once ON idea_links (coalesce(idea_id, cluster_id, solution_id), contributor_code, link_type);

CREATE TABLE clusters (
  id                    text        PRIMARY KEY CHECK (id ~ '^CL-[0-9]{4}$'),
  stage                 text        NOT NULL DEFAULT 'in_cluster',
  scope                 text        CHECK (scope IN ('lob', 'cross-lob', 'org-wide')),
  route_to              text,
  lobs                  text[]      NOT NULL DEFAULT '{}',
  member_count          integer     NOT NULL DEFAULT 0,
  distinct_contributors integer     NOT NULL DEFAULT 0,
  centroid              vector(1024),
  repo_path             text,
  repo_commit           text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER clusters_updated_at BEFORE UPDATE ON clusters FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE review_items (
  id           bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  item_type    text        NOT NULL CHECK (item_type IN (
                 'idea', 'cluster_proposal', 'taxonomy_proposal', 'glossary_proposal',
                 'working_group_trigger', 'disagreement')),
  ref_id       text        NOT NULL,
  proposal     jsonb       NOT NULL DEFAULT '{}',
  confidence   jsonb       NOT NULL DEFAULT '{}',
  reasons      jsonb       NOT NULL DEFAULT '{}',
  state        text        NOT NULL DEFAULT 'open' CHECK (state IN (
                 'open', 'in_progress', 'awaiting_second_reviewer', 'decided', 'vetoed', 'closed')),
  assigned_to  uuid        REFERENCES users (id) ON DELETE SET NULL,
  due_at       timestamptz,
  decided_by   uuid        REFERENCES users (id) ON DELETE SET NULL,
  decided_at   timestamptz,
  final        jsonb,
  vetoed_by    uuid        REFERENCES users (id) ON DELETE SET NULL,
  veto_reason  text,
  vetoed_at    timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK ((vetoed_by IS NULL) = (veto_reason IS NULL))
);
CREATE INDEX review_items_queue ON review_items (state, due_at);
CREATE INDEX review_items_ref   ON review_items (item_type, ref_id);
CREATE TRIGGER review_items_updated_at BEFORE UPDATE ON review_items FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE corrections (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  review_item_id bigint      NOT NULL REFERENCES review_items (id) ON DELETE CASCADE,
  field          text        NOT NULL,
  proposed       jsonb,
  final          jsonb,
  reviewer_id    uuid        REFERENCES users (id) ON DELETE SET NULL,
  note           text,
  card_embedding vector(1024),                         -- the original card's embedding, for plan P6 (§5.1)
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX corrections_item ON corrections (review_item_id);

CREATE TABLE sla_timers (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_type    text        NOT NULL,
  entity_id      text        NOT NULL,
  stage          text        NOT NULL,                 -- key in rules/sla.md: review, veto_window, needs_info …
  started_at     timestamptz NOT NULL DEFAULT now(),
  due_at         timestamptz NOT NULL,
  paused_at      timestamptz,
  paused_total   interval    NOT NULL DEFAULT '0',
  state          text        NOT NULL DEFAULT 'running' CHECK (state IN ('running', 'paused', 'stopped', 'breached')),
  reminders_sent numeric[]   NOT NULL DEFAULT '{}',    -- fractions already reminded, e.g. {0.5}
  escalated_at   timestamptz,
  stopped_at     timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX sla_timers_open ON sla_timers (entity_type, entity_id, stage) WHERE state IN ('running', 'paused');
CREATE INDEX sla_timers_due ON sla_timers (due_at) WHERE state = 'running';
CREATE TRIGGER sla_timers_updated_at BEFORE UPDATE ON sla_timers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE points_ledger (
  id               bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contributor_code text         NOT NULL CHECK (contributor_code ~ '^CTR-[0-9a-f]{6,8}$'),
  event            text         NOT NULL,
  points           numeric(6,1) NOT NULL,
  ref_id           text,
  created_at       timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX points_ledger_contributor ON points_ledger (contributor_code, created_at);
CREATE TRIGGER points_ledger_append_only BEFORE UPDATE OR DELETE ON points_ledger
  FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();

-- migrate:down
DROP TABLE IF EXISTS points_ledger;
DROP TABLE IF EXISTS sla_timers;
DROP TABLE IF EXISTS corrections;
DROP TABLE IF EXISTS review_items;
DROP TABLE IF EXISTS clusters;
DROP TABLE IF EXISTS idea_links;
DROP TABLE IF EXISTS attachments;
DROP TABLE IF EXISTS ideas;
