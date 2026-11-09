-- migrate:up
-- Delivery and learning (§4.8 to §4.11, §4.14, §5). Handover packs, delivery status read back from the delivery
-- pipeline, the non-tech fix track, measure and close, lenses, and the learning loops' reports and proposals.
-- Free text people type here (metric names, milestone titles, notes) is checked like any other text (patterns,
-- then the gatekeeper) and stored encrypted; packs and results hold codes, numbers and booleans only (BLD-020).

-- One delivery per picked idea or cluster (§4.8). `pack` holds codes, numbers and booleans only.
CREATE TABLE deliveries (
  id                  bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  subject_type        text        NOT NULL CHECK (subject_type IN ('idea', 'cluster')),
  subject_id          text        NOT NULL CHECK (subject_id ~ '^(IDEA-[0-9]{4}-[0-9]{6}|CL-[0-9]{4})$'),
  track               text        NOT NULL DEFAULT 'build' CHECK (track IN ('build', 'fix', 'procurement')),
  state               text        NOT NULL DEFAULT 'drafting' CHECK (state IN (
                        'drafting', 'awaiting_sponsor', 'in_delivery', 'shipped', 'resolved', 'closed')),
  owner_user_id       uuid        REFERENCES users (id) ON DELETE RESTRICT,
  sponsor_user_id     uuid        REFERENCES users (id) ON DELETE RESTRICT,
  pm_user_id          uuid        REFERENCES users (id) ON DELETE RESTRICT,   -- the delivery PM who takes it (BLD-011)
  pack                jsonb       NOT NULL DEFAULT '{}'::jsonb,
  metric_encrypted    bytea,      -- the success metric's name, checked text
  objective_encrypted bytea,      -- the fix track's objective, checked text
  sponsor_approved_by uuid        REFERENCES users (id) ON DELETE RESTRICT,
  sponsor_approved_at timestamptz,
  slug                text        CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  pipeline_page_id    text        CHECK (pipeline_page_id ~ '^[A-Za-z0-9-]{8,64}$'),
  link_state          text        NOT NULL DEFAULT 'none' CHECK (link_state IN ('none', 'queued', 'manual', 'linked')),
  phase               text,       -- the delivery pipeline's current-phase (contracts/garage/phases.yaml)
  gate_status         text        CHECK (gate_status IN ('clear', 'blocked')),
  blocked_since       timestamptz,
  blocked_flagged_at  timestamptz,
  phase_updated_at    timestamptz,
  completion          jsonb,      -- fix track: before and after numbers, submitted by the owner
  completion_notes    bytea,      -- checked text, encrypted
  completed_at        timestamptz,
  shipped_at          timestamptz,
  resolved_at         timestamptz,
  closed_at           timestamptz,
  outcome             text        CHECK (outcome IN ('target_met', 'target_not_met')),
  created_by          uuid        REFERENCES users (id) ON DELETE RESTRICT,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (subject_type, subject_id)
);
CREATE INDEX deliveries_state ON deliveries (state, updated_at DESC);
CREATE INDEX deliveries_owner ON deliveries (owner_user_id);
CREATE INDEX deliveries_sponsor ON deliveries (sponsor_user_id);
CREATE UNIQUE INDEX deliveries_slug ON deliveries (slug) WHERE slug IS NOT NULL;
CREATE TRIGGER deliveries_updated_at BEFORE UPDATE ON deliveries FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- The fix track's action plan (§4.10): milestones with an owner and a due date.
CREATE TABLE delivery_milestones (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  delivery_id     bigint      NOT NULL REFERENCES deliveries (id) ON DELETE CASCADE,
  title_encrypted bytea       NOT NULL,
  owner_user_id   uuid        REFERENCES users (id) ON DELETE RESTRICT,
  due_on          date        NOT NULL,
  status          text        NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
  done_at         timestamptz,
  overdue_sent_on date,
  escalated_on    date,       -- a plan more than 10 working days late goes to the core committee chair (§4.10)
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX delivery_milestones_delivery ON delivery_milestones (delivery_id, due_on);
CREATE INDEX delivery_milestones_open ON delivery_milestones (due_on) WHERE status = 'open';

-- Measure and close (§4.11): results at 30 and 90 days, filled by the owner and confirmed by the sponsor.
CREATE TABLE delivery_measurements (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  delivery_id     bigint      NOT NULL REFERENCES deliveries (id) ON DELETE CASCADE,
  mark            text        NOT NULL CHECK (mark IN ('day_30', 'day_90')),
  due_at          timestamptz NOT NULL,
  results         jsonb       NOT NULL DEFAULT '{}'::jsonb,
  notes_encrypted bytea,
  filled_by       uuid        REFERENCES users (id) ON DELETE RESTRICT,
  filled_at       timestamptz,
  confirmed_by    uuid        REFERENCES users (id) ON DELETE RESTRICT,
  confirmed_at    timestamptz,
  finance_confirmed_by uuid   REFERENCES users (id) ON DELETE RESTRICT,
  finance_confirmed_at timestamptz,
  reminded_on     date,
  UNIQUE (delivery_id, mark)
);
CREATE INDEX delivery_measurements_due ON delivery_measurements (due_at) WHERE confirmed_at IS NULL;

-- Lenses (§4.14): weekly snapshots, counts only. The people lens is never stored here; it is computed for
-- admins on request (database only, never the repo).
CREATE TABLE lens_snapshots (
  kind     text        NOT NULL CHECK (kind IN ('lob', 'role')),
  key      text        NOT NULL,
  data     jsonb       NOT NULL,
  built_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (kind, key)
);

-- Learning loops (§5): reports (counts and rates only) and proposals that wait for a person.
CREATE TABLE learning_reports (
  id       bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind     text        NOT NULL CHECK (kind IN ('canvas', 'calibration', 'drift', 'autonomy', 'agreement')),
  period   text        NOT NULL CHECK (period ~ '^[0-9]{4}-(Q[1-4]|[0-9]{2}|W[0-9]{2}|[0-9]{2}-[0-9]{2})$'),
  data     jsonb       NOT NULL,
  built_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kind, period)
);

CREATE TABLE learning_proposals (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind           text        NOT NULL CHECK (kind IN ('area_tag', 'glossary_term')),
  period         text        NOT NULL,
  payload        jsonb       NOT NULL DEFAULT '{}'::jsonb,   -- counts, idea IDs, codes; never idea text
  text_encrypted bytea,      -- the candidate term (glossary), checked by the patterns before it is stored
  state          text        NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'approved', 'declined')),
  decided_by     uuid        REFERENCES users (id) ON DELETE RESTRICT,
  decided_at     timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX learning_proposals_open ON learning_proposals (kind, created_at DESC) WHERE state = 'proposed';
CREATE UNIQUE INDEX learning_proposals_term ON learning_proposals (kind, (payload ->> 'key'))
  WHERE payload ? 'key';

-- New kill switch (§7.6): stops every learning loop's job (reports and proposals); nothing else depends on them.
INSERT INTO kill_switches (name) VALUES ('learning.jobs') ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'learning.jobs';
DROP TABLE IF EXISTS learning_proposals;
DROP TABLE IF EXISTS learning_reports;
DROP TABLE IF EXISTS lens_snapshots;
DROP TABLE IF EXISTS delivery_measurements;
DROP TABLE IF EXISTS delivery_milestones;
DROP TABLE IF EXISTS deliveries;
