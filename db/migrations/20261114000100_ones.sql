-- migrate:up
-- The Ones (DEC-034 to DEC-083): people whose ideas the core committee accepted, plus sponsored and founding
-- Ones. One record per person for life: a One who retires and comes back returns to the same record, so their
-- spark (drawn from `induction_no`, never from personal data) stays theirs. Citations, reasons, titles and
-- impact briefs are checked (patterns, then the gatekeeper) and stored encrypted; none of it is logged.

-- The CEO sponsors Ones (DEC-042, DEC-045).
ALTER TABLE role_grants DROP CONSTRAINT IF EXISTS role_grants_role_check;
ALTER TABLE role_grants ADD CONSTRAINT role_grants_role_check CHECK (role IN (
  'reviewer', 'lob_committee', 'core_committee', 'core_chair', 'appeal_panel',
  'working_group', 'sponsor', 'admin', 'infosec', 'hr', 'ceo'));

CREATE TABLE ones (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  induction_no      integer     NOT NULL UNIQUE CHECK (induction_no > 0),   -- permanent, never reused
  user_id           uuid        NOT NULL UNIQUE REFERENCES users (id) ON DELETE RESTRICT,
  number            integer     CHECK (number BETWEEN 1 AND 999),           -- the jersey number while active
  status            text        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
  way_in            text        NOT NULL CHECK (way_in IN ('accepted_idea', 'sponsored', 'founding')),
  idea_id           text        CHECK (idea_id ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  tier              smallint    NOT NULL DEFAULT 1 CHECK (tier BETWEEN 1 AND 7),
  title_encrypted   bytea,      -- what they built or are building, one line (sponsored and founding Ones)
  brief_encrypted   bytea,      -- the approved impact brief, "If this works: …" (DEC-073)
  brief_approved_at timestamptz,
  measures          jsonb       NOT NULL DEFAULT '{}'::jsonb,               -- time, money, effort, scale (DEC-071)
  inducted_at       timestamptz NOT NULL DEFAULT now(),
  swap_until        timestamptz NOT NULL,                                   -- 30 days to choose a number (DEC-067)
  retired_at        timestamptz,
  announced_at      timestamptz,                                            -- named in an org announcement
  CHECK ((status = 'active') = (number IS NOT NULL))
);
CREATE UNIQUE INDEX ones_number_active ON ones (number) WHERE number IS NOT NULL;
CREATE INDEX ones_status ON ones (status, inducted_at DESC);

-- Every number a One has worn. A freed number rests for 6 months before anyone may claim it (DEC-040).
CREATE TABLE one_number_history (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  one_id      bigint      NOT NULL REFERENCES ones (id) ON DELETE CASCADE,
  number      integer     NOT NULL CHECK (number BETWEEN 1 AND 999),
  how         text        NOT NULL CHECK (how IN ('allocated', 'chosen')),
  from_at     timestamptz NOT NULL DEFAULT now(),
  to_at       timestamptz,
  rests_until timestamptz
);
CREATE INDEX one_number_history_number ON one_number_history (number, rests_until);
CREATE INDEX one_number_history_one ON one_number_history (one_id, from_at);

-- Numbers retired for good to honour a legend, at most one a year (DEC-041). Only that One may wear it.
CREATE TABLE one_legend_numbers (
  number      integer     PRIMARY KEY CHECK (number BETWEEN 1 AND 999),
  one_id      bigint      NOT NULL REFERENCES ones (id) ON DELETE RESTRICT,
  retired_on  date        NOT NULL DEFAULT current_date
);

-- Every change to the Ones goes through a proposal: proposed, approved by the chair or a meeting majority, then
-- carried out by the admin member (DEC-040, DEC-044, DEC-045, DEC-076, DEC-082). An impact brief is proposed by the
-- One and takes effect when the committee approves it (DEC-073).
CREATE TABLE one_proposals (
  id               bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind             text        NOT NULL CHECK (kind IN ('include', 'remove', 'tier_up', 'tier_down', 'impact_brief', 'legend')),
  one_id           bigint      REFERENCES ones (id) ON DELETE CASCADE,
  subject_user_id  uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  way_in           text        CHECK (way_in IN ('accepted_idea', 'sponsored', 'founding')),
  idea_id          text        CHECK (idea_id ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  tier_to          smallint    CHECK (tier_to BETWEEN 1 AND 7),
  reason_encrypted bytea,      -- citation or reason (checked text)
  text_encrypted   bytea,      -- the title (include) or the brief (impact_brief)
  proposed_by      uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  proposed_at      timestamptz NOT NULL DEFAULT now(),
  state            text        NOT NULL DEFAULT 'proposed'
                   CHECK (state IN ('proposed', 'approved', 'declined', 'carried_out', 'withdrawn')),
  approval         text        CHECK (approval IN ('chair', 'majority')),
  meeting_on       date,
  decided_by       uuid        REFERENCES users (id) ON DELETE RESTRICT,
  decided_at       timestamptz,
  carried_out_by   uuid        REFERENCES users (id) ON DELETE RESTRICT,
  carried_out_at   timestamptz,
  CHECK (approval IS DISTINCT FROM 'majority' OR meeting_on IS NOT NULL)
);
CREATE INDEX one_proposals_open ON one_proposals (state, proposed_at) WHERE state IN ('proposed', 'approved');
CREATE UNIQUE INDEX one_proposals_one_open ON one_proposals (subject_user_id, kind)
  WHERE state IN ('proposed', 'approved');

-- Messages to a One for a tier change (DEC-084): the committee's (required), the CEO's and invited colleagues'
-- (optional). Checked text, encrypted.
CREATE TABLE one_messages (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  proposal_id    bigint      NOT NULL REFERENCES one_proposals (id) ON DELETE CASCADE,
  author_user_id uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  author_role    text        NOT NULL CHECK (author_role IN ('committee', 'ceo', 'peer')),
  text_encrypted bytea,
  written_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (proposal_id, author_user_id)
);
CREATE UNIQUE INDEX one_messages_committee ON one_messages (proposal_id) WHERE author_role = 'committee';
CREATE UNIQUE INDEX one_messages_ceo ON one_messages (proposal_id) WHERE author_role = 'ceo';

CREATE TABLE one_message_invites (
  proposal_id bigint      NOT NULL REFERENCES one_proposals (id) ON DELETE CASCADE,
  user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  invited_by  uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  invited_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (proposal_id, user_id)
);

-- The glow-up that plays once on the One's dashboard after a tier change (DEC-084).
CREATE TABLE one_glow_ups (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  one_id      bigint      NOT NULL REFERENCES ones (id) ON DELETE CASCADE,
  proposal_id bigint      NOT NULL UNIQUE REFERENCES one_proposals (id) ON DELETE CASCADE,
  tier_from   smallint    NOT NULL CHECK (tier_from BETWEEN 1 AND 7),
  tier_to     smallint    NOT NULL CHECK (tier_to BETWEEN 1 AND 7),
  created_at  timestamptz NOT NULL DEFAULT now(),
  seen_at     timestamptz
);
CREATE INDEX one_glow_ups_unseen ON one_glow_ups (one_id) WHERE seen_at IS NULL;

-- The Ones Night impact awards (DEC-085): one a year for each of time, money, effort and scale.
CREATE TABLE one_awards (
  id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  one_id     bigint      NOT NULL REFERENCES ones (id) ON DELETE RESTRICT,
  year       integer     NOT NULL CHECK (year BETWEEN 2026 AND 2100),
  category   text        NOT NULL CHECK (category IN ('time', 'money', 'effort', 'scale')),
  awarded_by uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  awarded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (year, category)
);

-- The Showcase brief (DEC-086): the One's own words for the parts their record can't fill. Checked text,
-- encrypted; the committee reads it before the Showcase.
CREATE TABLE one_showcase_briefs (
  one_id          bigint      PRIMARY KEY REFERENCES ones (id) ON DELETE CASCADE,
  parts_encrypted bytea       NOT NULL,
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- What the office screens show: the static sky, or ambient mode for events (DEC-069). One row.
CREATE TABLE screen_settings (
  id         boolean     PRIMARY KEY DEFAULT true CHECK (id),
  mode       text        NOT NULL DEFAULT 'static' CHECK (mode IN ('static', 'ambient')),
  changed_by text,
  changed_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO screen_settings (id) VALUES (true);

-- Hides Ones from the wall, home and screens (§7.6).
INSERT INTO kill_switches (name) VALUES ('ones.public') ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'ones.public';
DROP TABLE IF EXISTS screen_settings;
DROP TABLE IF EXISTS one_showcase_briefs;
DROP TABLE IF EXISTS one_awards;
DROP TABLE IF EXISTS one_glow_ups;
DROP TABLE IF EXISTS one_message_invites;
DROP TABLE IF EXISTS one_messages;
DROP TABLE IF EXISTS one_proposals;
DROP TABLE IF EXISTS one_legend_numbers;
DROP TABLE IF EXISTS one_number_history;
DROP TABLE IF EXISTS ones;
DELETE FROM role_grants WHERE role = 'ceo';
ALTER TABLE role_grants DROP CONSTRAINT IF EXISTS role_grants_role_check;
ALTER TABLE role_grants ADD CONSTRAINT role_grants_role_check CHECK (role IN (
  'reviewer', 'lob_committee', 'core_committee', 'core_chair', 'appeal_panel',
  'working_group', 'sponsor', 'admin', 'infosec', 'hr'));
