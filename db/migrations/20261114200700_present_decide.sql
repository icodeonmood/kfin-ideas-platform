-- migrate:up
-- Present and decide (§4.7) and working groups (§2.5). Sealed assessments and decision sheets stay in the database
-- (non-negotiable 6); the web app's role cannot read them: the worker serves each member their own assessment
-- and the core committee the collated sheet. Decision files in the repo carry counts, themes and reasons, never
-- who voted what.

CREATE TABLE presentations (
  id              text        PRIMARY KEY CHECK (id ~ '^PRS-[0-9]{4}-[0-9]{4}$'),
  cluster_id      text        NOT NULL REFERENCES clusters (id),
  round_id        text        REFERENCES scoring_rounds (id),
  cycle_id        text        REFERENCES cycles (id),
  presenters      text[]      NOT NULL DEFAULT '{}' CHECK (cardinality(presenters) <= 3),   -- contributor codes
  slot_options    timestamptz[] NOT NULL DEFAULT '{}',
  slot_at         timestamptz,
  state           text        NOT NULL DEFAULT 'invited'
                    CHECK (state IN ('invited', 'scheduled', 'held', 'no_show', 'withdrawn', 'decided')),
  invited_at      timestamptz NOT NULL DEFAULT now(),
  reply_due       timestamptz,
  accepted_by     text,                                     -- contributor code
  accepted_at     timestamptz,
  held_at         timestamptz,
  outline         jsonb,                                    -- pitch-prep draft, then the presenters' edits (tagged)
  outline_by      text,                                     -- pitch-prep/<version> or a contributor code
  qna_notes       text,                                     -- tagged; recorded by the chair in the session
  assessments_due timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX presentations_cluster ON presentations (cluster_id);
CREATE TRIGGER presentations_updated_at BEFORE UPDATE ON presentations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE assessments (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  presentation_id  text        NOT NULL REFERENCES presentations (id),
  cluster_id       text        NOT NULL REFERENCES clusters (id),
  member_id        uuid        NOT NULL REFERENCES users (id),
  stage            text        NOT NULL DEFAULT 'post_presentation' CHECK (stage IN ('post_presentation')),
  dimension_scores jsonb       NOT NULL,
  vote             text        NOT NULL CHECK (vote IN ('accept', 'accept_with_conditions', 'park', 'decline')),
  route_pref       text        CHECK (route_pref IN ('reuse', 'build', 'buy', 'partner')),
  strengths        jsonb       NOT NULL DEFAULT '[]',     -- tagged, up to 3
  concerns         jsonb       NOT NULL DEFAULT '[]',     -- tagged, up to 3
  conditions       jsonb       NOT NULL DEFAULT '[]',     -- tagged
  open_questions   text,                                  -- tagged
  will_sponsor     boolean     NOT NULL DEFAULT false,
  submitted_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (presentation_id, member_id)
);

CREATE TABLE decision_sheets (
  presentation_id  text        PRIMARY KEY REFERENCES presentations (id),
  cluster_id       text        NOT NULL REFERENCES clusters (id),
  cycle_id         text        REFERENCES cycles (id),
  tallies          jsonb       NOT NULL,                  -- vote → count
  medians          jsonb       NOT NULL,
  spread           jsonb       NOT NULL,
  change_from_prelim jsonb     NOT NULL DEFAULT '{}',
  route_prefs      jsonb       NOT NULL DEFAULT '{}',
  themes           jsonb,                                 -- collation output, tagged
  conditions       jsonb,                                 -- merged, tagged
  divergence_flags text[]      NOT NULL DEFAULT '{}',
  sponsors_willing integer     NOT NULL DEFAULT 0,
  final_score      numeric,
  generated_by     text,
  generated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE decisions (
  id                   text        PRIMARY KEY CHECK (id ~ '^DEC-[0-9]{4}-[0-9]{4}$'),
  cluster_id           text        NOT NULL REFERENCES clusters (id),
  presentation_id      text        REFERENCES presentations (id),
  cycle_id             text        REFERENCES cycles (id),
  body                 text        NOT NULL DEFAULT 'core' CHECK (body IN ('core', 'lob')),
  outcome              text        NOT NULL CHECK (outcome IN ('picked', 'parked', 'declined')),
  route                text        CHECK (route IN ('reuse', 'build', 'buy', 'partner')),
  reason_code          text,
  plain_reason         text,                              -- tagged; reason-writer draft as the chair approved it
  what_would_change    text,                              -- tagged
  conditions           jsonb       NOT NULL DEFAULT '[]', -- tagged
  votes                jsonb       NOT NULL,              -- counts only, never names
  members_present      integer     NOT NULL,
  recused              integer     NOT NULL DEFAULT 0,
  sponsor_id           uuid        REFERENCES users (id),
  casting_vote         boolean     NOT NULL DEFAULT false,
  override_reason      text,                              -- tagged; moving a cluster across the capacity line
  decided_by           text        NOT NULL CHECK (decided_by ~ '^REV-[0-9]{4}$'),
  decided_at           timestamptz NOT NULL DEFAULT now(),
  appeal_window_closes timestamptz,
  repo_path            text,
  repo_commit          text
);
CREATE INDEX decisions_cluster ON decisions (cluster_id);

CREATE TABLE working_groups (
  id               text        PRIMARY KEY CHECK (id ~ '^WG-[0-9]{4}$'),
  cluster_id       text        NOT NULL REFERENCES clusters (id),
  decision_id      text        REFERENCES decisions (id),
  sponsor_id       uuid        REFERENCES users (id),
  product_owner_id uuid        REFERENCES users (id),
  members          jsonb       NOT NULL DEFAULT '[]',     -- [{contributor_code, role, protected_hours, manager_ack_at}]
  charter_path     text,
  state            text        NOT NULL DEFAULT 'forming' CHECK (state IN ('forming', 'active', 'showcasing', 'closed')),
  formed_at        timestamptz NOT NULL DEFAULT now(),
  closed_at        timestamptz
);
CREATE UNIQUE INDEX working_groups_cluster ON working_groups (cluster_id) WHERE state <> 'closed';

REVOKE ALL ON assessments, decision_sheets FROM ideas_web_svc;

-- migrate:down
DROP TABLE IF EXISTS working_groups;
DROP TABLE IF EXISTS decisions;
DROP TABLE IF EXISTS decision_sheets;
DROP TABLE IF EXISTS assessments;
DROP TABLE IF EXISTS presentations;
