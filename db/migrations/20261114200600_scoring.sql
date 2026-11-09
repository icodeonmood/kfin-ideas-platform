-- migrate:up
-- Preliminary review and shortlist (§4.6): decision cycles, blind scoring rounds, sealed scores, the AI pre-score
-- and conflict-of-interest flags. Individual scores never leave the database (non-negotiable 6); the web app's
-- role cannot read them at all: every read goes through the worker, which keeps them sealed until reveal.

CREATE TABLE cycles (
  id                 text        PRIMARY KEY CHECK (id ~ '^CYC-[0-9]{4}-[0-9]{2}(-[0-9]+)?$'),
  opens_at           timestamptz NOT NULL DEFAULT now(),
  shortlist_by       timestamptz,
  presentations_from timestamptz,
  presentations_to   timestamptz,
  decisions_by       timestamptz,
  state              text        NOT NULL DEFAULT 'open'
                       CHECK (state IN ('open', 'shortlisting', 'presenting', 'deciding', 'closed')),
  opened_by          text        CHECK (opened_by ~ '^REV-[0-9]{4}$'),
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE capacity (
  cycle_id          text        PRIMARY KEY REFERENCES cycles (id),
  presentation_slots integer    NOT NULL DEFAULT 8 CHECK (presentation_slots BETWEEN 0 AND 50),
  garage_slots      integer     CHECK (garage_slots >= 0),
  wg_hours          integer     CHECK (wg_hours >= 0),
  capex_budget_inr  numeric     CHECK (capex_budget_inr >= 0),
  declared_by       text        CHECK (declared_by ~ '^REV-[0-9]{4}$'),
  declared_at       timestamptz
);

CREATE TABLE scoring_rounds (
  id                    text        PRIMARY KEY CHECK (id ~ '^RND-[0-9]{4}-[0-9]{4}$'),
  cluster_id            text        NOT NULL REFERENCES clusters (id),
  cycle_id              text        REFERENCES cycles (id),
  body                  text        NOT NULL CHECK (body IN ('core', 'lob')),
  lob_id                text        CHECK (lob_id ~ '^LOB-[a-z0-9-]+$'),
  scorecard_version     text        NOT NULL,
  roster                uuid[]      NOT NULL,                  -- members at open (role grants)
  quorum                numeric     NOT NULL DEFAULT 0.6,
  evidence_type         text        CHECK (evidence_type IN ('data_backed', 'estimate', 'anecdote')),
  suggested_band        smallint    CHECK (suggested_band BETWEEN 1 AND 5),
  confidence_multiplier numeric     NOT NULL DEFAULT 1.0,
  opens_at              timestamptz NOT NULL DEFAULT now(),
  closes_at             timestamptz NOT NULL,
  state                 text        NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'revealed', 'decided', 'cancelled')),
  revealed_at           timestamptz,
  medians               jsonb,                                  -- dimension → median (after reveal)
  ranges                jsonb,
  flags                 jsonb,                                  -- dimension → [members_disagree, ai_differs]
  final_score           numeric,
  outcome               text        CHECK (outcome IN ('shortlisted', 'parked', 'declined', 'nominated')),
  reason_code           text,
  outcome_note          text,                                   -- tagged under the cluster's scope
  below_threshold_reason text,                                  -- tagged; the chair shortlisting under the line
  queue_position        integer,                                -- shortlisted beyond this cycle's slots
  decided_by            text        CHECK (decided_by ~ '^REV-[0-9]{4}$'),
  decided_at            timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  CHECK (body = 'core' OR lob_id IS NOT NULL)
);
CREATE INDEX scoring_rounds_cluster ON scoring_rounds (cluster_id);
CREATE UNIQUE INDEX scoring_rounds_open ON scoring_rounds (cluster_id, body) WHERE state IN ('open', 'revealed');

CREATE TABLE sealed_scores (
  round_id      text        NOT NULL REFERENCES scoring_rounds (id) ON DELETE CASCADE,
  member_id     uuid        NOT NULL REFERENCES users (id),
  dimension     text        NOT NULL,
  value         smallint    NOT NULL CHECK (value BETWEEN 1 AND 5),
  comment       text,                                         -- tagged
  submitted_at  timestamptz NOT NULL DEFAULT now(),
  revised_value smallint    CHECK (revised_value BETWEEN 1 AND 5),
  revised_at    timestamptz,
  PRIMARY KEY (round_id, member_id, dimension)
);

CREATE TABLE ai_prescores (
  round_id      text        NOT NULL REFERENCES scoring_rounds (id) ON DELETE CASCADE,
  dimension     text        NOT NULL,
  value         smallint    NOT NULL CHECK (value BETWEEN 1 AND 5),
  rationale     text        NOT NULL,                         -- tagged under the cluster's scope
  evidence_refs jsonb       NOT NULL DEFAULT '[]',
  generated_by  text        NOT NULL,
  PRIMARY KEY (round_id, dimension)
);

CREATE TABLE coi_flags (
  round_id     text        NOT NULL REFERENCES scoring_rounds (id) ON DELETE CASCADE,
  member_id    uuid        NOT NULL REFERENCES users (id),
  reason       text        NOT NULL CHECK (reason IN ('contributor', 'declared')),
  status       text        NOT NULL CHECK (status IN ('flagged', 'recused', 'cleared')),
  cleared_by   text,
  clear_reason text,                                          -- tagged
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (round_id, member_id)
);

-- Sealed: the web app's role cannot read individual scores or the AI pre-score at all (BLD-077 pattern).
REVOKE ALL ON sealed_scores, ai_prescores FROM ideas_web_svc;

-- migrate:down
DROP TABLE IF EXISTS coi_flags;
DROP TABLE IF EXISTS ai_prescores;
DROP TABLE IF EXISTS sealed_scores;
DROP TABLE IF EXISTS scoring_rounds;
DROP TABLE IF EXISTS capacity;
DROP TABLE IF EXISTS cycles;
