-- migrate:up
-- The design-handoff cut-over (DEC-102, BLD-E006): the 1% Club pack's entities (1pc-handoff/06-contracts/E-ENTITIES,
-- E-ENUMS) in `public`, next to the old domain. ADDITIVE ONLY until Monday's cleanup migration: old code is replaced
-- screen by screen this week, so nothing here removes or narrows what old code writes. New code never reads or sets
-- `ideas.stage` (it keeps its default, 'draft'); it uses `ideas.status`.
--
-- Conventions for every table below:
--   * Enum columns carry a CHECK with exactly the pack's wire values (contracts/1pc/enums.json; a test on each side
--     keeps them equal). Where an old column is reused, its CHECK is widened to old + pack values until Monday.
--   * Numbers the product promises (P-PRODUCT.promises: minimum lengths, windows, clocks, tries, the answer and
--     return periods) are configuration, never a CHECK or a default here.
--   * Text other people may read is the masked copy (L-HIDE.rules/3). Private masked text (messages, answers,
--     notes, reasons) is stored encrypted as `<column>_encrypted` with core/crypto.py's encrypt_json({"text": …}),
--     context "<table>.<column>:<row id>" (see onepc/enums.py and src/lib/contracts/crypto-context.ts).
--   * The sharer's unmasked words live only in `idea_words_sealed`, which the web role cannot read (DEC-103,
--     L-HIDE.rules/4, non-negotiable 6). Hidden values stay in `pseudonym_vault`; `hidden_details` holds the kind,
--     span, masked form and vault tag, never the value.
--   * A person who shares or helps is keyed by contributor code (erasure deletes the contributor_map row and
--     anonymises them everywhere); staff actions (review desk, committee, admin) by users.id.

-- ---------------------------------------------------------------------------------------------------------------
-- 1. People (E-ENTITIES.person)
-- ---------------------------------------------------------------------------------------------------------------
-- `city` is the existing `users.location`; `initials` is derived from `name`.
ALTER TABLE users
  ADD COLUMN first_name text,                                  -- from the directory; the view falls back to the first word
  ADD COLUMN area       text,                                  -- the pack's area list (configuration), not lob_id
  ADD COLUMN tier       smallint NOT NULL DEFAULT 1 CONSTRAINT users_tier_check CHECK (tier BETWEEN 1 AND 7);

-- Channel preferences stay in comms_prefs (Person.settings teams, email, reminders).
ALTER TABLE comms_prefs
  ADD COLUMN teams     boolean NOT NULL DEFAULT true,
  ADD COLUMN email     boolean NOT NULL DEFAULT true,
  ADD COLUMN reminders boolean NOT NULL DEFAULT true;

-- Profile switches (Person.settings, S-H6). Names show unless the person hides theirs from the Wall (DEC-104).
CREATE TABLE person_settings (
  user_id           uuid        PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  show_name_on_wall boolean     NOT NULL DEFAULT true,
  shortcut_p        boolean     NOT NULL DEFAULT true,
  sidebar_folded    boolean     NOT NULL DEFAULT false,
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER person_settings_updated_at BEFORE UPDATE ON person_settings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- E-ENUMS.roles, added to the old values (dropped on Monday: lob_committee, core_committee, core_chair,
-- appeal_panel, working_group, sponsor, ceo). `build_team` is per idea: scope_id is the idea's IDEA- reference.
ALTER TABLE role_grants DROP CONSTRAINT role_grants_role_check;
ALTER TABLE role_grants ADD CONSTRAINT role_grants_role_check CHECK (role IN (
  'employee', 'reviewer', 'committee', 'build_team', 'admin', 'display',
  'lob_committee', 'core_committee', 'core_chair', 'appeal_panel', 'working_group', 'sponsor', 'infosec', 'hr', 'ceo'));

-- ---------------------------------------------------------------------------------------------------------------
-- 2. Ideas and drafts (E-ENTITIES.idea, E-ENTITIES.draft). One row from draft to shipped keeps the reference, the
--    vault scope and the file links.
-- ---------------------------------------------------------------------------------------------------------------
-- E-ENUMS.kind: 'fix' added; 'problem_with_solution' stays for old code until Monday.
ALTER TABLE ideas DROP CONSTRAINT ideas_kind_check;
ALTER TABLE ideas ADD CONSTRAINT ideas_kind_check CHECK (kind IN ('problem', 'fix', 'business_idea', 'problem_with_solution'));

-- L-SUBMIT.send/1: the reference is IDEA-<year>-<6 digits> (ideas_idea_id_check, unchanged). The SUB- twin is
-- retired (SHIP_PLAN §6.2), so new code sets idea_id alone; old code still sets both, with the same number.
ALTER TABLE ideas DROP CONSTRAINT ideas_check, DROP CONSTRAINT ideas_check1;
ALTER TABLE ideas ADD CONSTRAINT ideas_submission_pair CHECK (
  submission_id IS NULL OR (idea_id IS NOT NULL AND substr(idea_id, 6) = substr(submission_id, 5)));

ALTER TABLE ideas
  ADD COLUMN status                    text        NOT NULL DEFAULT 'draft' CONSTRAINT ideas_status_check CHECK (status IN (
                                         'draft', 'checking', 'with_review_desk', 'needs_you', 'picked', 'being_built',
                                         'shipped', 'not_now', 'not_picked', 'withdrawn', 'merged')),
  ADD COLUMN status_changed_at         timestamptz,
  -- what the idea says (masked; public once shared)
  ADD COLUMN title                     text,
  ADD COLUMN summary                   text,
  ADD COLUMN often                     text,
  ADD COLUMN city                      text,                   -- the sharer's city when shared (snapshot)
  -- sorting (E-ENTITIES Sorting; L-SORT): values here, per-field {source, why} in sorting_sources
  ADD COLUMN affects                   text[]      NOT NULL DEFAULT '{}',
  ADD COLUMN area                      text,
  ADD COLUMN brings                    text[]      NOT NULL DEFAULT '{}' CONSTRAINT ideas_brings_check CHECK (
                                         brings <@ ARRAY['saves_time', 'saves_cost', 'earns_revenue', 'less_outside_tools', 'not_sure']::text[]
                                         AND (NOT ('not_sure' = ANY (brings)) OR cardinality(brings) = 1)),
  ADD COLUMN sorting_sources           jsonb       NOT NULL DEFAULT '{}',  -- {affects|kind|area|brings: {source, why}}
  ADD COLUMN sorting_confirmed_at      timestamptz,
  ADD COLUMN helper_picks              text[]      NOT NULL DEFAULT '{}',  -- "Who would help" (configured list)
  ADD COLUMN helper_text               text,
  -- the draft (owner only)
  ADD COLUMN channel                   text        NOT NULL DEFAULT 'web' CONSTRAINT ideas_channel_check CHECK (channel IN ('web', 'voice', 'email', 'teams')),
  ADD COLUMN origin_encrypted          bytea,                  -- {subject, received_at, note} of a forwarded email or Teams arrival
  ADD COLUMN step                      text        CONSTRAINT ideas_step_check CHECK (step IN (
                                         'tell', 'check:1', 'check:2', 'check:3', 'check:4', 'check:5', 'check:6', 'check:7', 'send')),
  ADD COLUMN saved_at                  timestamptz,
  ADD COLUMN saved_device              text        CONSTRAINT ideas_saved_device_check CHECK (saved_device IN ('phone', 'laptop')),
  ADD COLUMN saved_device_id           text,                   -- opaque per-device id, for "this device"
  ADD COLUMN char_count                integer     NOT NULL DEFAULT 0 CHECK (char_count >= 0),
  ADD COLUMN archived_at               timestamptz,            -- drafts are archived, never deleted silently
  -- sharing (L-SUBMIT)
  ADD COLUMN shared_at                 timestamptz,
  ADD COLUMN share_seconds             integer     CHECK (share_seconds >= 0),
  ADD COLUMN declaration_version       text,
  ADD COLUMN declared_at               timestamptz,
  ADD COLUMN edit_closes_at            timestamptz,
  ADD COLUMN withdrawn_at              timestamptz,
  ADD COLUMN withdraw_reason_encrypted bytea,
  ADD COLUMN restored_at               timestamptz,
  ADD COLUMN kept_separate             boolean     NOT NULL DEFAULT false,
  -- review (L-REVIEW)
  ADD COLUMN decide_by                 timestamptz,
  ADD COLUMN reviewer_id               uuid        REFERENCES users (id) ON DELETE SET NULL,
  ADD COLUMN opened_at                 timestamptz,
  ADD COLUMN opened_by                 uuid        REFERENCES users (id) ON DELETE SET NULL,
  -- merge (L-MERGE.effects/1)
  ADD COLUMN merged_into               uuid        REFERENCES ideas (id) ON DELETE SET NULL,
  ADD CONSTRAINT ideas_merged_into_not_self CHECK (merged_into IS DISTINCT FROM id);

-- Existing rows get the pack status nearest their old stage (mapping/contracts.md §2.1) and their shared date,
-- without touching updated_at (old pages sort on it).
ALTER TABLE ideas DISABLE TRIGGER ideas_updated_at;
UPDATE ideas SET
  status = CASE
    WHEN stage IN ('draft', 'blocked') THEN 'draft'
    WHEN stage = 'scanning' THEN 'checking'
    WHEN stage IN ('scanned', 'reviewed', 'needs_info', 'adoption_requested', 'in_cluster', 'ready_for_scoring',
                   'scored', 'shortlisted', 'presenting') THEN 'with_review_desk'
    WHEN stage IN ('picked', 'handover') THEN 'picked'
    WHEN stage IN ('in_garage', 'in_fix_track') THEN 'being_built'
    WHEN stage IN ('shipped', 'resolved', 'measuring', 'closed') THEN 'shipped'
    WHEN stage IN ('parked', 'already_planned') THEN 'not_now'
    WHEN stage IN ('declined', 'already_solved', 'redirected', 'appealed') THEN 'not_picked'
    WHEN stage = 'withdrawn' THEN 'withdrawn'
    WHEN stage = 'merged' THEN 'merged'
  END,
  status_changed_at = updated_at,
  shared_at = submitted_at;
ALTER TABLE ideas ENABLE TRIGGER ideas_updated_at;

CREATE INDEX ideas_status          ON ideas (status, shared_at DESC);
CREATE INDEX ideas_owner_status    ON ideas (contributor_code, status);
CREATE INDEX ideas_desk_due        ON ideas (decide_by) WHERE status = 'with_review_desk';
CREATE INDEX ideas_edit_window     ON ideas (edit_closes_at) WHERE opened_at IS NULL AND status IN ('checking', 'with_review_desk');
CREATE INDEX ideas_draft_saved     ON ideas (contributor_code, saved_at DESC) WHERE status = 'draft' AND archived_at IS NULL;
CREATE INDEX ideas_draft_untouched ON ideas (saved_at) WHERE status = 'draft' AND archived_at IS NULL;
CREATE INDEX ideas_merged_into     ON ideas (merged_into) WHERE merged_into IS NOT NULL;
CREATE INDEX ideas_area            ON ideas (area, status);
CREATE INDEX ideas_reviewer        ON ideas (reviewer_id) WHERE reviewer_id IS NOT NULL;

-- IDEA-<year>-<6-digit running number> (L-SUBMIT.send/1), on the counter old code also uses, so a reference is never
-- given twice. The year is the office year (IST).
CREATE OR REPLACE FUNCTION next_idea_ref(p_at timestamptz DEFAULT now()) RETURNS text
LANGUAGE sql AS $$
  SELECT 'IDEA-' || y || '-' || lpad(next_number('IDEA', y)::text, 6, '0')
  FROM (SELECT to_char(p_at AT TIME ZONE 'Asia/Kolkata', 'YYYY') AS y) AS t
$$;

-- Every status change with its time, for the five-stage track (E-ENTITIES StageState, derived). Kept by a trigger
-- so every path that moves a status is recorded. The old stage history stays as it is.
CREATE TABLE idea_status_history (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid   uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  from_status text,
  to_status   text        NOT NULL,
  at          timestamptz NOT NULL DEFAULT now(),
  source      text        NOT NULL DEFAULT 'live' CHECK (source IN ('live', 'backfill'))
);
CREATE INDEX idea_status_history_idea ON idea_status_history (idea_uuid, at);
CREATE INDEX idea_status_history_to   ON idea_status_history (to_status, at);
INSERT INTO idea_status_history (idea_uuid, from_status, to_status, at, source)
SELECT id, NULL, status, coalesce(status_changed_at, created_at), 'backfill' FROM ideas;

CREATE OR REPLACE FUNCTION record_idea_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status THEN
    INSERT INTO idea_status_history (idea_uuid, from_status, to_status)
    VALUES (NEW.id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER ideas_status_history AFTER INSERT OR UPDATE OF status ON ideas
  FOR EACH ROW EXECUTE FUNCTION record_idea_status();

CREATE OR REPLACE FUNCTION stamp_idea_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status THEN
    NEW.status_changed_at := now();
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ideas_status_stamp BEFORE INSERT OR UPDATE OF status ON ideas
  FOR EACH ROW EXECUTE FUNCTION stamp_idea_status();

-- One row per run of the six draft parts (L-DRAFT.parts). Replaces `scans` for new code. Latency per part feeds the
-- rolling 7-day p50 the loader uses (L-DRAFT.parts/6). Receipt lines and suggestions are masked text.
CREATE TABLE draft_runs (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid   uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  message_id  uuid,                                  -- the message that started it (FK added below)
  state       text        NOT NULL DEFAULT 'running' CHECK (state IN ('running', 'done', 'failed')),
  parts       text[]      NOT NULL DEFAULT '{}',     -- part keys this run re-ran
  part_ms     jsonb       NOT NULL DEFAULT '{}',     -- {part key: took_ms}
  receipt     jsonb       NOT NULL DEFAULT '[]',     -- lines for the conversation
  suggestions jsonb       NOT NULL DEFAULT '[]',     -- up to two next prompts
  ready       boolean,
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX draft_runs_idea    ON draft_runs (idea_uuid, started_at DESC);
CREATE INDEX draft_runs_started ON draft_runs (started_at) WHERE state = 'done';

-- The person's own words, one message at a time (E-ENTITIES Message). `text_encrypted` is the MASKED copy (for the
-- desk and committee); the unmasked words are in idea_words_sealed. Spans are positions in the owner's own text,
-- never values.
CREATE TABLE idea_messages (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid      uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  seq            integer     NOT NULL CHECK (seq > 0),
  via            text        NOT NULL CONSTRAINT idea_messages_via_check CHECK (via IN ('typed', 'voice', 'email', 'teams')),
  device         text        CONSTRAINT idea_messages_device_check CHECK (device IN ('phone', 'laptop')),
  lang           text,
  text_encrypted bytea       NOT NULL,
  spans          jsonb       NOT NULL DEFAULT '[]',  -- [{start, end, kind}]
  char_count     integer     NOT NULL DEFAULT 0 CHECK (char_count >= 0),
  created_at     timestamptz NOT NULL DEFAULT now(),
  edited_at      timestamptz,
  UNIQUE (idea_uuid, seq)
);
ALTER TABLE draft_runs ADD CONSTRAINT draft_runs_message_fk FOREIGN KEY (message_id) REFERENCES idea_messages (id) ON DELETE SET NULL;

-- The six parts of the draft (E-ENUMS.draft part; L-DRAFT.parts). `title` holds {title, summary}; masked values.
CREATE TABLE idea_parts (
  idea_uuid    uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  key          text        NOT NULL CONSTRAINT idea_parts_key_check CHECK (key IN ('title', 'often', 'who', 'value', 'area', 'similar')),
  state        text        NOT NULL DEFAULT 'waiting' CONSTRAINT idea_parts_state_check CHECK (state IN ('waiting', 'updating', 'filled', 'pinned', 'failed')),
  value        jsonb,
  why          text,
  source_quote text,
  run_id       uuid        REFERENCES draft_runs (id) ON DELETE SET NULL,
  took_ms      integer     CHECK (took_ms >= 0),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (idea_uuid, key)
);
CREATE TRIGGER idea_parts_updated_at BEFORE UPDATE ON idea_parts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- WORKER ONLY (revoked below; pinned in tests/test_b4_service_roles.py). The unmasked words of a message, answer,
-- conversation message or edit, readable by the person who typed them alone (DEC-103, L-HIDE.rules/4).
CREATE TABLE idea_words_sealed (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid      uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  source         text        NOT NULL CHECK (source IN ('message', 'answer', 'conversation', 'edit')),
  source_id      text        NOT NULL,             -- the message, answer or entry id, or "<version n>" for an edit
  owner_user_id  uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  text_encrypted bytea       NOT NULL,             -- encrypt with the worker's vault key
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, source_id)
);
CREATE INDEX idea_words_sealed_idea ON idea_words_sealed (idea_uuid);
CREATE TRIGGER idea_words_sealed_updated_at BEFORE UPDATE ON idea_words_sealed
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Hidden details (E-ENTITIES HiddenDetail, HiddenSpan; E-ENUMS.hidden; L-HIDE). Never the value: that is in the
-- vault under `vault_tag`. "Show it" needs a reason (L-HIDE.rules/6) and is also written to audit_log.
CREATE TABLE hidden_details (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid   uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  source      text        NOT NULL CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file')),
  source_id   text        NOT NULL,
  span_start  integer     CHECK (span_start >= 0),
  span_end    integer     CHECK (span_end >= span_start),
  kind        text        NOT NULL CONSTRAINT hidden_details_kind_check CHECK (kind IN ('folio', 'pan', 'phone', 'email', 'account', 'aadhaar', 'name')),
  masked      text        NOT NULL,             -- "Folio ••••89"
  vault_tag   text        CHECK (vault_tag ~ '^\[\[[A-Z_]+_[0-9]+\]\]$'),
  found_by    text        NOT NULL DEFAULT 'patterns' CHECK (found_by IN ('patterns', 'gatekeeper', 'reviewer')),
  state       text        NOT NULL DEFAULT 'hidden' CONSTRAINT hidden_details_state_check CHECK (state IN ('hidden', 'shown')),
  reason      text        CONSTRAINT hidden_details_reason_check CHECK (reason IN ('scheme_or_product_code', 'internal_reference', 'made_up_example')),
  shown_by    uuid        REFERENCES users (id) ON DELETE SET NULL,
  shown_at    timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT hidden_details_shown_has_reason CHECK (state = 'hidden' OR (reason IS NOT NULL AND shown_at IS NOT NULL))
);
CREATE INDEX hidden_details_idea   ON hidden_details (idea_uuid);
CREATE INDEX hidden_details_source ON hidden_details (source, source_id);

-- The optional fix (E-ENTITIES Fix; E-ENUMS.fix). Masked text. The sharer's worth is in idea_worth.
CREATE TABLE idea_fix (
  idea_uuid      uuid        PRIMARY KEY REFERENCES ideas (id) ON DELETE CASCADE,
  how            text,
  needs          text,
  solved_already text        CONSTRAINT idea_fix_solved_already_check CHECK (solved_already IN ('yes', 'partly', 'no', 'dont_know')),
  solved_note    text,
  basis          text        CONSTRAINT idea_fix_basis_check CHECK (basis IN ('own_research', 'verified_documents', 'report', 'conversation', 'hunch')),
  risks          text,
  included       boolean     NOT NULL DEFAULT true,
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER idea_fix_updated_at BEFORE UPDATE ON idea_fix FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- What it's worth, per month (E-ENTITIES Worth, Range; L-WORTH). The sharer's figures and every reviewer revision
-- are separate rows; nothing is overwritten (L-WORTH/3, /7). Rupees per month for cost and revenue.
CREATE TABLE idea_worth (
  id             bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid      uuid          NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  by_side        text          NOT NULL CHECK (by_side IN ('sharer', 'reviewer')),
  by_code        text          CHECK (by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  by_user_id     uuid          REFERENCES users (id) ON DELETE SET NULL,
  hours_low      numeric(12,2) CHECK (hours_low >= 0),
  hours_high     numeric(12,2) CHECK (hours_high >= hours_low),
  cost_low       numeric(14,2) CHECK (cost_low >= 0),
  cost_high      numeric(14,2) CHECK (cost_high >= cost_low),
  revenue_low    numeric(14,2) CHECK (revenue_low >= 0),
  revenue_high   numeric(14,2) CHECK (revenue_high >= revenue_low),
  outside_tools  text          CONSTRAINT idea_worth_outside_tools_check CHECK (outside_tools IN ('none', 'partly', 'fully')),
  kind           text          CONSTRAINT idea_worth_kind_check CHECK (kind IN ('problem', 'fix', 'business_idea')),  -- reviewer recategorise
  area           text,
  note_encrypted bytea,
  at             timestamptz   NOT NULL DEFAULT now(),
  CONSTRAINT idea_worth_by CHECK ((by_side = 'sharer' AND by_code IS NOT NULL) OR (by_side = 'reviewer'))
);
CREATE INDEX idea_worth_idea ON idea_worth (idea_uuid, at DESC);

-- Each saved edit is a version (L-SUBMIT.edit/4). Append-only for the web role.
CREATE TABLE idea_versions (
  id                 bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid          uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  n                  integer     NOT NULL CHECK (n > 0),
  changed_fields     text[]      NOT NULL DEFAULT '{}',
  by_code            text        CHECK (by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  snapshot_encrypted bytea,      -- the masked idea as saved
  at                 timestamptz NOT NULL DEFAULT now(),
  UNIQUE (idea_uuid, n)
);

-- Similar ideas found for an idea (E-ENTITIES SimilarMatch; E-ENUMS.match; L-SIMILAR). The reason is masked text.
CREATE TABLE similar_links (
  idea_uuid       uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  other_idea_uuid uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  strength        text        NOT NULL CONSTRAINT similar_links_strength_check CHECK (strength IN ('close', 'related')),
  reason          text        NOT NULL,
  rank            smallint    NOT NULL DEFAULT 1 CHECK (rank > 0),
  found_while     text        NOT NULL DEFAULT 'drafting' CHECK (found_while IN ('drafting', 'checking', 'later')),
  outcome         text        CHECK (outcome IN ('previewed', 'kept_separate', 'merge_asked')),  -- L-AUDIT.metrics
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (idea_uuid, other_idea_uuid),
  CHECK (idea_uuid <> other_idea_uuid)
);
CREATE INDEX similar_links_other ON similar_links (other_idea_uuid);
CREATE TRIGGER similar_links_updated_at BEFORE UPDATE ON similar_links FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Distinct colleagues who opened an idea's page, per day; counts only, kept 8 days (L-WALL.justin/4).
CREATE TABLE idea_opens (
  idea_uuid uuid NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  user_id   uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  day       date NOT NULL DEFAULT (now() AT TIME ZONE 'Asia/Kolkata')::date,
  PRIMARY KEY (idea_uuid, user_id, day)
);
CREATE INDEX idea_opens_day ON idea_opens (day);

-- ---------------------------------------------------------------------------------------------------------------
-- 3. Questions, answers, decisions, windows (E-ENTITIES.review)
-- ---------------------------------------------------------------------------------------------------------------
-- `time_to_answer` is E-ENUMS.questions' wire value; the choices themselves are a promise (configuration), so no CHECK.
CREATE TABLE question_sets (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid      uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  by_user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  state          text        NOT NULL DEFAULT 'queued' CONSTRAINT question_sets_state_check CHECK (state IN (
                               'queued', 'sent', 'seen', 'partly_answered', 'answered', 'closed')),
  time_to_answer text,
  sent_at        timestamptz,
  seen_at        timestamptz,
  due_at         timestamptz,
  extended_times smallint    NOT NULL DEFAULT 0 CHECK (extended_times >= 0),
  reminded_at    timestamptz,
  answered_at    timestamptz,
  closed_at      timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (state = 'queued' OR (sent_at IS NOT NULL AND due_at IS NOT NULL))
);
CREATE INDEX question_sets_idea ON question_sets (idea_uuid, created_at DESC);
CREATE INDEX question_sets_due  ON question_sets (due_at) WHERE state IN ('sent', 'seen', 'partly_answered');
CREATE UNIQUE INDEX question_sets_one_queued ON question_sets (idea_uuid) WHERE state = 'queued';

CREATE TABLE questions (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  set_id         uuid        NOT NULL REFERENCES question_sets (id) ON DELETE CASCADE,
  seq            smallint    NOT NULL CHECK (seq > 0),
  part           text        NOT NULL CONSTRAINT questions_part_check CHECK (part IN ('summary', 'often', 'who', 'cost', 'evidence', 'fix')),
  text_encrypted bytea       NOT NULL,
  suggested      boolean     NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (set_id, seq)
);

-- One answer per question; saved as a draft while typed, then sent with the set (L-QUESTIONS.answer/4).
CREATE TABLE answers (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id    uuid        NOT NULL UNIQUE REFERENCES questions (id) ON DELETE CASCADE,
  by_code        text        NOT NULL CHECK (by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  text_encrypted bytea,
  added_to       text        CONSTRAINT answers_added_to_check CHECK (added_to IN ('summary', 'often', 'who', 'cost', 'evidence', 'fix')),
  saved_at       timestamptz NOT NULL DEFAULT now(),
  sent_at        timestamptz
);
CREATE INDEX answers_unsent ON answers (by_code) WHERE sent_at IS NULL;

-- The review desk's decision (E-ENTITIES Decision; E-ENUMS.decision; L-DECIDE). Never edited (L-DECIDE.rules/9):
-- the web role may insert, not change or remove. `return_in` is the chosen period (configuration), `return_at` the date.
CREATE TABLE idea_decisions (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid        uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  choice           text        NOT NULL CONSTRAINT idea_decisions_choice_check CHECK (choice IN ('pick', 'not_now', 'not_picked')),
  reason_encrypted bytea       NOT NULL,
  by_user_id       uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  at               timestamptz NOT NULL DEFAULT now(),
  joined_with      uuid        REFERENCES ideas (id) ON DELETE SET NULL,
  return_in        text,
  return_at        timestamptz,
  team_by          timestamptz,
  CHECK (choice <> 'not_now' OR return_at IS NOT NULL),
  CHECK (joined_with IS NULL OR choice = 'pick')
);
CREATE INDEX idea_decisions_idea ON idea_decisions (idea_uuid, at DESC);
CREATE INDEX idea_decisions_at   ON idea_decisions (at DESC);

-- A merge (E-ENTITIES Merge; L-MERGE). `prior_status` restores the merged idea on a committee reversal.
CREATE TABLE merges (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_idea_uuid   uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  merged_idea_uuid uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  via              text        NOT NULL CONSTRAINT merges_via_check CHECK (via IN ('lead_accepted', 'review_desk')),
  by_code          text        CHECK (by_code ~ '^CTR-[0-9a-f]{6,8}$'),   -- the lead, for lead_accepted
  by_user_id       uuid        REFERENCES users (id) ON DELETE RESTRICT,  -- the reviewer, for review_desk
  team_up          boolean     NOT NULL DEFAULT true,
  note_encrypted   bytea,
  prior_status     text        CONSTRAINT merges_prior_status_check CHECK (prior_status IN (
                                 'draft', 'checking', 'with_review_desk', 'needs_you', 'picked', 'being_built',
                                 'shipped', 'not_now', 'not_picked', 'withdrawn', 'merged')),
  at               timestamptz NOT NULL DEFAULT now(),
  reversed_at      timestamptz,
  CHECK (lead_idea_uuid <> merged_idea_uuid),
  CHECK ((via = 'lead_accepted' AND by_code IS NOT NULL) OR (via = 'review_desk' AND by_user_id IS NOT NULL))
);
CREATE UNIQUE INDEX merges_live_once ON merges (merged_idea_uuid) WHERE reversed_at IS NULL;
CREATE INDEX merges_lead ON merges (lead_idea_uuid);

-- The Ones Committee's window over a decision or a desk merge (E-ENTITIES Window; E-ENUMS.windows; L-COMMITTEE).
-- Lengths (30 days, +30, 3 months) are promises: the app sets the dates.
CREATE TABLE decision_windows (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id      uuid        UNIQUE REFERENCES idea_decisions (id) ON DELETE CASCADE,
  merge_id         uuid        UNIQUE REFERENCES merges (id) ON DELETE CASCADE,
  state            text        NOT NULL DEFAULT 'open' CONSTRAINT decision_windows_state_check CHECK (state IN ('open', 'extended', 'reversed', 'expired')),
  opens_at         timestamptz NOT NULL DEFAULT now(),
  closes_at        timestamptz NOT NULL,
  max_closes_at    timestamptz NOT NULL,
  extended_times   smallint    NOT NULL DEFAULT 0 CHECK (extended_times >= 0),
  last_extended_by uuid        REFERENCES users (id) ON DELETE SET NULL,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(decision_id, merge_id) = 1),
  CHECK (closes_at <= max_closes_at)
);
CREATE INDEX decision_windows_closing ON decision_windows (closes_at) WHERE state IN ('open', 'extended');
CREATE TRIGGER decision_windows_updated_at BEFORE UPDATE ON decision_windows FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- A reversal (E-ENTITIES Reversal). Once per window, final (L-COMMITTEE.rules/4): unique per window, and the web role
-- may insert, never change or remove. `to_choice` is the pack's `to`; empty for a reversed desk merge.
CREATE TABLE decision_reversals (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  window_id      uuid        NOT NULL UNIQUE REFERENCES decision_windows (id) ON DELETE CASCADE,
  to_choice      text        CONSTRAINT decision_reversals_to_choice_check CHECK (to_choice IN ('pick', 'not_now', 'not_picked')),
  note_encrypted bytea       NOT NULL,
  by_user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  at             timestamptz NOT NULL DEFAULT now(),
  return_in      text,
  return_at      timestamptz,
  CHECK (to_choice IS DISTINCT FROM 'not_now' OR return_at IS NOT NULL)
);
CREATE INDEX decision_reversals_at ON decision_reversals (at DESC);

-- ---------------------------------------------------------------------------------------------------------------
-- 4. Team-up, merge requests, crew, conversation (E-ENTITIES.crew, E-ENTITIES.inbox)
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE teamup_requests (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid             uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  from_code             text        NOT NULL CHECK (from_code ~ '^CTR-[0-9a-f]{6,8}$'),
  note_encrypted        bytea       NOT NULL,
  state                 text        NOT NULL DEFAULT 'sent' CONSTRAINT teamup_requests_state_check CHECK (state IN (
                                      'sent', 'approved_merged', 'approved_team_only', 'declined', 'withdrawn', 'closed')),
  lead_reason_encrypted bytea,
  answered_by_code      text        CHECK (answered_by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  sent_at               timestamptz NOT NULL DEFAULT now(),
  answered_at           timestamptz
);
CREATE UNIQUE INDEX teamup_requests_one_open ON teamup_requests (idea_uuid, from_code) WHERE state = 'sent';
CREATE INDEX teamup_requests_idea ON teamup_requests (idea_uuid, state);
CREATE INDEX teamup_requests_from ON teamup_requests (from_code, sent_at DESC);

CREATE TABLE teamup_brought (
  request_id uuid NOT NULL REFERENCES teamup_requests (id) ON DELETE CASCADE,
  idea_uuid  uuid NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  PRIMARY KEY (request_id, idea_uuid)
);

-- A sharer asks, from an unsent draft, for their draft to be merged in (E-ENTITIES Draft.merge_request; L-MERGE.request).
CREATE TABLE merge_requests (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_uuid            uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  other_idea_uuid       uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  from_code             text        NOT NULL CHECK (from_code ~ '^CTR-[0-9a-f]{6,8}$'),
  note_encrypted        bytea       NOT NULL,
  state                 text        NOT NULL DEFAULT 'waiting' CONSTRAINT merge_requests_state_check CHECK (state IN (
                                      'none', 'waiting', 'accepted', 'team_only', 'declined', 'withdrawn')),
  lead_reason_encrypted bytea,
  answered_by_code      text        CHECK (answered_by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  sent_at               timestamptz NOT NULL DEFAULT now(),
  answered_at           timestamptz,
  CHECK (draft_uuid <> other_idea_uuid)
);
CREATE UNIQUE INDEX merge_requests_one_waiting ON merge_requests (draft_uuid) WHERE state = 'waiting';
CREATE INDEX merge_requests_other ON merge_requests (other_idea_uuid, state);

ALTER TABLE merges
  ADD COLUMN teamup_request_id uuid REFERENCES teamup_requests (id) ON DELETE SET NULL,
  ADD COLUMN merge_request_id  uuid REFERENCES merge_requests (id) ON DELETE SET NULL;

-- The crew of an idea (Idea.crew; E-ENUMS.roles per idea). One lead. Leaving and removal are kept (L-TEAMUP/11).
CREATE TABLE crew_members (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid         uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  contributor_code  text        NOT NULL CHECK (contributor_code ~ '^CTR-[0-9a-f]{6,8}$'),
  role              text        NOT NULL CONSTRAINT crew_members_role_check CHECK (role IN ('lead', 'crew')),
  via               text        NOT NULL CHECK (via IN ('shared', 'teamup', 'merge', 'desk_merge')),
  teamup_request_id uuid        REFERENCES teamup_requests (id) ON DELETE SET NULL,
  merge_id          uuid        REFERENCES merges (id) ON DELETE SET NULL,   -- undone if the merge is reversed
  joined_at         timestamptz NOT NULL DEFAULT now(),
  left_at           timestamptz,
  left_how          text        CHECK (left_how IN ('left', 'removed', 'merge_reversed', 'idea_withdrawn')),
  removed_by_code   text        CHECK (removed_by_code ~ '^CTR-[0-9a-f]{6,8}$'),
  CHECK ((left_at IS NULL) = (left_how IS NULL))
);
CREATE UNIQUE INDEX crew_members_once ON crew_members (idea_uuid, contributor_code) WHERE left_at IS NULL;
CREATE UNIQUE INDEX crew_members_one_lead ON crew_members (idea_uuid) WHERE role = 'lead' AND left_at IS NULL;
CREATE INDEX crew_members_person ON crew_members (contributor_code) WHERE left_at IS NULL;

-- "Next" on the crew deck (L-CREW/6): per person, undoable, resettable.
CREATE TABLE crew_passes (
  id        bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id   uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  idea_uuid uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  passed_at timestamptz NOT NULL DEFAULT now(),
  undone_at timestamptz
);
CREATE UNIQUE INDEX crew_passes_live ON crew_passes (user_id, idea_uuid) WHERE undone_at IS NULL;
CREATE INDEX crew_passes_last ON crew_passes (user_id, passed_at DESC) WHERE undone_at IS NULL;

-- The idea's one conversation (E-ENTITIES ConversationEntry; L-CONVO). Events carry a code and IDs, rendered at read
-- time; messages carry masked text, encrypted. Question sets and answers appear by reference.
CREATE TABLE conversation_entries (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid       uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  type            text        NOT NULL CONSTRAINT conversation_entries_type_check CHECK (type IN ('event', 'message', 'questions', 'answers')),
  event           text        CHECK (event ~ '^[a-z_]+(\.[a-z_]+)*$'),
  payload         jsonb       NOT NULL DEFAULT '{}',   -- IDs only
  author_code     text        CHECK (author_code ~ '^CTR-[0-9a-f]{6,8}$'),
  author_user_id  uuid        REFERENCES users (id) ON DELETE SET NULL,
  text_encrypted  bytea,
  mentions        uuid[]      NOT NULL DEFAULT '{}',
  question_set_id uuid        REFERENCES question_sets (id) ON DELETE CASCADE,
  at              timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz,
  CHECK (type <> 'event' OR event IS NOT NULL),
  CHECK (type NOT IN ('questions', 'answers') OR question_set_id IS NOT NULL),
  CHECK (type <> 'message' OR num_nonnulls(author_code, author_user_id) = 1)
);
CREATE INDEX conversation_entries_idea ON conversation_entries (idea_uuid, at);
CREATE INDEX conversation_entries_mentions ON conversation_entries USING gin (mentions);

-- The build team chosen for a picked idea (L-DECIDE.after). Members are role_grants rows with role 'build_team' and
-- scope_id = the idea's IDEA- reference.
CREATE TABLE build_teams (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid    uuid        NOT NULL UNIQUE REFERENCES ideas (id) ON DELETE CASCADE,
  name         text        NOT NULL,
  lead_user_id uuid        REFERENCES users (id) ON DELETE SET NULL,
  chosen_by    uuid        REFERENCES users (id) ON DELETE SET NULL,
  chosen_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------------------------------------------
-- 5. Files, Inbox, impact (re-purposed tables, additive)
-- ---------------------------------------------------------------------------------------------------------------
-- E-ENTITIES.files FileItem. `file_state` is the pack's state (E-ENUMS.file, file and link values); the old pipeline
-- keeps `state` until Monday. A link or folder has no object in the store.
ALTER TABLE attachments
  ALTER COLUMN store_key DROP NOT NULL,
  ADD COLUMN kind                  text        NOT NULL DEFAULT 'file' CONSTRAINT attachments_kind_check CHECK (kind IN ('file', 'link', 'folder')),
  ADD COLUMN file_state            text        CONSTRAINT attachments_file_state_check CHECK (file_state IN (
                                                 'uploading', 'checking', 'checked', 'upload_failed', 'personal_data_found',
                                                 'hidden_checked', 'too_big', 'locked', 'infected', 'ok', 'unreachable')),
  ADD COLUMN link_scope            text        CONSTRAINT attachments_link_scope_check CHECK (link_scope IN ('internal', 'external')),
  ADD COLUMN url_encrypted         bytea,
  ADD COLUMN parent_id             text        REFERENCES attachments (id) ON DELETE CASCADE,   -- a file inside a folder
  ADD COLUMN item_count            integer     CHECK (item_count >= 0),                         -- a folder's files
  ADD COLUMN pages                 integer     CHECK (pages >= 0),
  ADD COLUMN masked_store_key      text,                                                        -- the blacked-out copy
  ADD COLUMN hidden_note           text,                                                        -- "Folio hidden"
  ADD COLUMN message_id            uuid        REFERENCES idea_messages (id) ON DELETE SET NULL,
  ADD COLUMN answer_id             uuid        REFERENCES answers (id) ON DELETE SET NULL,
  ADD COLUMN conversation_entry_id uuid        REFERENCES conversation_entries (id) ON DELETE SET NULL,
  ADD CONSTRAINT attachments_file_has_object CHECK (kind <> 'file' OR store_key IS NOT NULL),
  ADD CONSTRAINT attachments_link_has_url CHECK (kind <> 'link' OR url_encrypted IS NOT NULL);
CREATE INDEX attachments_answer  ON attachments (answer_id) WHERE answer_id IS NOT NULL;
CREATE INDEX attachments_message ON attachments (message_id) WHERE message_id IS NOT NULL;
CREATE INDEX attachments_entry   ON attachments (conversation_entry_id) WHERE conversation_entry_id IS NOT NULL;
CREATE INDEX attachments_parent  ON attachments (parent_id) WHERE parent_id IS NOT NULL;

-- E-ENTITIES.inbox InboxItem; L-INBOX. Text is still rendered from templates at read time (BLD-088). `from` is
-- `from_user_id` (NULL = the system); the idea is `idea_uuid`.
ALTER TABLE notifications
  ADD COLUMN kind         text        CONSTRAINT notifications_kind_check CHECK (kind IN (
                                        'questions', 'teamup_request', 'teamup_answer', 'decision', 'decision_reversed',
                                        'desk_merge', 'worth_revised', 'stage_moved', 'build_ask', 'mention', 'crew_joined',
                                        'comment', 'draft_kept', 'sent_to_desk', 'answer_reminder')),
  ADD COLUMN from_user_id uuid        REFERENCES users (id) ON DELETE SET NULL,
  ADD COLUMN idea_uuid    uuid        REFERENCES ideas (id) ON DELETE CASCADE,
  ADD COLUMN needs_you    boolean     NOT NULL DEFAULT false,
  ADD COLUMN resolved_at  timestamptz,                 -- when the outstanding action was done
  ADD COLUMN due_at       timestamptz,
  ADD COLUMN archived_at  timestamptz,
  ADD COLUMN actions      jsonb       NOT NULL DEFAULT '[]',   -- [{label, to?, op?, style}]
  ADD CONSTRAINT notifications_archive_not_open CHECK (archived_at IS NULL OR NOT needs_you);
CREATE INDEX notifications_inbox     ON notifications (user_id, created_at DESC) WHERE kind IS NOT NULL AND archived_at IS NULL;
CREATE INDEX notifications_needs_you ON notifications (user_id, due_at) WHERE needs_you;
CREATE INDEX notifications_unread    ON notifications (user_id) WHERE kind IS NOT NULL AND read_at IS NULL;
CREATE INDEX notifications_idea      ON notifications (idea_uuid) WHERE idea_uuid IS NOT NULL;

-- L-IMPACT: measurements per idea, 30 and 90 days after shipping. New code links the idea directly; old code keeps
-- going through deliveries (every old query joins on delivery_id, so idea-only rows stay out of its way).
ALTER TABLE delivery_measurements
  ALTER COLUMN delivery_id DROP NOT NULL,
  ADD COLUMN idea_uuid uuid REFERENCES ideas (id) ON DELETE CASCADE,
  ADD CONSTRAINT delivery_measurements_owner CHECK (num_nonnulls(delivery_id, idea_uuid) >= 1);
CREATE UNIQUE INDEX delivery_measurements_idea_mark ON delivery_measurements (idea_uuid, mark) WHERE idea_uuid IS NOT NULL;

-- Clocks reuse sla_timers (no new table). Its `stage` column has no CHECK, so the new kinds need no change here:
-- edit_window, question_due, question_reminder, decide_by, committee_window, not_now_return, team_by,
-- merge_request_wait, impact_30, impact_90, draft_archive (contracts/1pc/enums.json "clock_kind").

-- ---------------------------------------------------------------------------------------------------------------
-- 6. The Ones' posts (E-ENTITIES.wall OnePost; L-ONES.rules/7)
-- ---------------------------------------------------------------------------------------------------------------
CREATE TABLE one_posts (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  one_id         bigint      NOT NULL REFERENCES ones (id) ON DELETE CASCADE,
  idea_uuid      uuid        REFERENCES ideas (id) ON DELETE SET NULL,   -- comments are that idea's conversation
  text_encrypted bytea       NOT NULL,                                   -- checked text
  figure_value   text,                                                   -- "620"
  figure_line    text,                                                   -- "hours a month saved"
  shipped        boolean     NOT NULL DEFAULT true,
  adopted_by     integer     CHECK (adopted_by >= 0),
  posted_at      timestamptz NOT NULL DEFAULT now(),
  removed_at     timestamptz
);
CREATE INDEX one_posts_recent ON one_posts (posted_at DESC) WHERE removed_at IS NULL;

CREATE TABLE one_post_likes (
  post_id  uuid        NOT NULL REFERENCES one_posts (id) ON DELETE CASCADE,
  user_id  uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  liked_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (post_id, user_id)
);

-- ---------------------------------------------------------------------------------------------------------------
-- 7. Sign-in, flags, idempotency (L-AUTH, L-AUDIT.flags, A-API.conventions/3)
-- ---------------------------------------------------------------------------------------------------------------
-- Email-code sign-in (BLD-E002: built, switched off). Hashes only. Tries and lifetimes are promises: the app sets
-- them. A used or replaced code is superseded.
CREATE TABLE sign_in_codes (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email_hash    text        NOT NULL,
  code_hash     text        NOT NULL,
  expires_at    timestamptz NOT NULL,
  tries_left    smallint    NOT NULL CHECK (tries_left >= 0),
  sent_at       timestamptz NOT NULL DEFAULT now(),
  superseded_at timestamptz
);
CREATE INDEX sign_in_codes_live ON sign_in_codes (email_hash, sent_at DESC) WHERE superseded_at IS NULL;

-- Intent kept on the server against the sign-in attempt (L-AUTH.rules/4).
CREATE TABLE sign_in_intents (
  attempt_key text        PRIMARY KEY,
  destination text        NOT NULL,
  draft_id    uuid        REFERENCES ideas (id) ON DELETE SET NULL,
  step        text        CONSTRAINT sign_in_intents_step_check CHECK (step IN (
                            'tell', 'check:1', 'check:2', 'check:3', 'check:4', 'check:5', 'check:6', 'check:7', 'send')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  used_at     timestamptz
);
CREATE INDEX sign_in_intents_created ON sign_in_intents (created_at);

-- The S1–S3 experiments (P-DECISIONS.experiments), per person or by percentage, with exposure logged. Kill switches
-- stay in kill_switches.
CREATE TABLE flags (
  key                 text        PRIMARY KEY CHECK (key ~ '^[a-z0-9_.-]+$'),
  description         text        NOT NULL,
  state               text        NOT NULL DEFAULT 'on' CHECK (state IN ('on', 'off')),
  alternative_percent smallint    NOT NULL DEFAULT 0 CHECK (alternative_percent BETWEEN 0 AND 100),
  changed_by          text,
  changed_at          timestamptz NOT NULL DEFAULT now()
);
INSERT INTO flags (key, description) VALUES
  ('s1', 'S1: how the draft is built. Default: live draft beside the text. Alternative: interview first'),
  ('s2', 'S2: when similar ideas are decided. Default: quiet nudge. Alternative: check first on a close match'),
  ('s3', 'S3: phone starts with typing or voice. Default: type first. Alternative: voice first');

CREATE TABLE flag_assignments (
  flag_key    text        NOT NULL REFERENCES flags (key) ON DELETE CASCADE,
  user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  variant     text        NOT NULL CHECK (variant IN ('default', 'alternative')),
  assigned_by text        NOT NULL DEFAULT 'rule',     -- 'rule' (percentage) or an admin's staff ref
  assigned_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (flag_key, user_id)
);

-- Append-only for the web role.
CREATE TABLE flag_exposures (
  id       bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  flag_key text        NOT NULL REFERENCES flags (key) ON DELETE CASCADE,
  user_id  uuid        REFERENCES users (id) ON DELETE SET NULL,
  variant  text        NOT NULL CHECK (variant IN ('default', 'alternative')),
  screen   text        NOT NULL,                        -- a screen ID, e.g. S-04
  at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX flag_exposures_flag ON flag_exposures (flag_key, at);

-- Repeating a create with the same Idempotency-Key returns the first result (A-API.conventions/3). IDs only.
CREATE TABLE idempotency_keys (
  key           text        NOT NULL CHECK (char_length(key) BETWEEN 8 AND 200),
  user_id       uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  route         text        NOT NULL,
  request_hash  text        NOT NULL,
  status        smallint,
  response_json jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL DEFAULT now() + interval '24 hours',
  PRIMARY KEY (user_id, key)
);
CREATE INDEX idempotency_keys_expiry ON idempotency_keys (expires_at);

-- ---------------------------------------------------------------------------------------------------------------
-- 8. Grants. New tables reach both roles by the default privileges (20261110000300). Then:
-- ---------------------------------------------------------------------------------------------------------------
-- Worker only (non-negotiable 6): the unmasked words.
REVOKE ALL ON idea_words_sealed FROM ideas_web_svc;
-- Final or audit-like records: the web role inserts and reads, never changes or removes.
REVOKE UPDATE, DELETE ON idea_decisions, decision_reversals, idea_versions, flag_exposures, idea_opens,
  idea_status_history FROM ideas_web_svc;

-- migrate:down
DROP TABLE IF EXISTS idempotency_keys;
DROP TABLE IF EXISTS flag_exposures;
DROP TABLE IF EXISTS flag_assignments;
DROP TABLE IF EXISTS flags;
DROP TABLE IF EXISTS sign_in_intents;
DROP TABLE IF EXISTS sign_in_codes;
DROP TABLE IF EXISTS one_post_likes;
DROP TABLE IF EXISTS one_posts;

DROP INDEX IF EXISTS delivery_measurements_idea_mark;
DELETE FROM delivery_measurements WHERE delivery_id IS NULL;
ALTER TABLE delivery_measurements
  DROP CONSTRAINT IF EXISTS delivery_measurements_owner,
  DROP COLUMN IF EXISTS idea_uuid,
  ALTER COLUMN delivery_id SET NOT NULL;

DROP INDEX IF EXISTS notifications_inbox, notifications_needs_you, notifications_unread, notifications_idea;
ALTER TABLE notifications
  DROP CONSTRAINT IF EXISTS notifications_archive_not_open,
  DROP COLUMN IF EXISTS actions,
  DROP COLUMN IF EXISTS archived_at,
  DROP COLUMN IF EXISTS due_at,
  DROP COLUMN IF EXISTS resolved_at,
  DROP COLUMN IF EXISTS needs_you,
  DROP COLUMN IF EXISTS idea_uuid,
  DROP COLUMN IF EXISTS from_user_id,
  DROP COLUMN IF EXISTS kind;

DROP INDEX IF EXISTS attachments_answer, attachments_message, attachments_entry, attachments_parent;
DELETE FROM attachments WHERE kind <> 'file';
ALTER TABLE attachments
  DROP CONSTRAINT IF EXISTS attachments_link_has_url,
  DROP CONSTRAINT IF EXISTS attachments_file_has_object,
  DROP COLUMN IF EXISTS conversation_entry_id,
  DROP COLUMN IF EXISTS answer_id,
  DROP COLUMN IF EXISTS message_id,
  DROP COLUMN IF EXISTS hidden_note,
  DROP COLUMN IF EXISTS masked_store_key,
  DROP COLUMN IF EXISTS pages,
  DROP COLUMN IF EXISTS item_count,
  DROP COLUMN IF EXISTS parent_id,
  DROP COLUMN IF EXISTS url_encrypted,
  DROP COLUMN IF EXISTS link_scope,
  DROP COLUMN IF EXISTS file_state,
  DROP COLUMN IF EXISTS kind,
  ALTER COLUMN store_key SET NOT NULL;

DROP TABLE IF EXISTS build_teams;
DROP TABLE IF EXISTS conversation_entries;
DROP TABLE IF EXISTS crew_passes;
DROP TABLE IF EXISTS crew_members;
ALTER TABLE merges DROP COLUMN IF EXISTS merge_request_id, DROP COLUMN IF EXISTS teamup_request_id;
DROP TABLE IF EXISTS merge_requests;
DROP TABLE IF EXISTS teamup_brought;
DROP TABLE IF EXISTS teamup_requests;
DROP TABLE IF EXISTS decision_reversals;
DROP TABLE IF EXISTS decision_windows;
DROP TABLE IF EXISTS merges;
DROP TABLE IF EXISTS idea_decisions;
DROP TABLE IF EXISTS answers;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS question_sets;
DROP TABLE IF EXISTS idea_opens;
DROP TABLE IF EXISTS similar_links;
DROP TABLE IF EXISTS idea_versions;
DROP TABLE IF EXISTS idea_worth;
DROP TABLE IF EXISTS idea_fix;
DROP TABLE IF EXISTS hidden_details;
DROP TABLE IF EXISTS idea_words_sealed;
DROP TABLE IF EXISTS idea_parts;
ALTER TABLE draft_runs DROP CONSTRAINT IF EXISTS draft_runs_message_fk;
DROP TABLE IF EXISTS idea_messages;
DROP TABLE IF EXISTS draft_runs;

DROP TRIGGER IF EXISTS ideas_status_stamp ON ideas;
DROP FUNCTION IF EXISTS stamp_idea_status();
DROP TRIGGER IF EXISTS ideas_status_history ON ideas;
DROP FUNCTION IF EXISTS record_idea_status();
DROP TABLE IF EXISTS idea_status_history;
DROP FUNCTION IF EXISTS next_idea_ref(timestamptz);

DROP INDEX IF EXISTS ideas_status, ideas_owner_status, ideas_desk_due, ideas_edit_window, ideas_draft_saved,
  ideas_draft_untouched, ideas_merged_into, ideas_area, ideas_reviewer;
ALTER TABLE ideas
  DROP CONSTRAINT IF EXISTS ideas_merged_into_not_self,
  DROP COLUMN IF EXISTS merged_into,
  DROP COLUMN IF EXISTS opened_by,
  DROP COLUMN IF EXISTS opened_at,
  DROP COLUMN IF EXISTS reviewer_id,
  DROP COLUMN IF EXISTS decide_by,
  DROP COLUMN IF EXISTS kept_separate,
  DROP COLUMN IF EXISTS restored_at,
  DROP COLUMN IF EXISTS withdraw_reason_encrypted,
  DROP COLUMN IF EXISTS withdrawn_at,
  DROP COLUMN IF EXISTS edit_closes_at,
  DROP COLUMN IF EXISTS declared_at,
  DROP COLUMN IF EXISTS declaration_version,
  DROP COLUMN IF EXISTS share_seconds,
  DROP COLUMN IF EXISTS shared_at,
  DROP COLUMN IF EXISTS archived_at,
  DROP COLUMN IF EXISTS char_count,
  DROP COLUMN IF EXISTS saved_device_id,
  DROP COLUMN IF EXISTS saved_device,
  DROP COLUMN IF EXISTS saved_at,
  DROP COLUMN IF EXISTS step,
  DROP COLUMN IF EXISTS origin_encrypted,
  DROP COLUMN IF EXISTS channel,
  DROP COLUMN IF EXISTS helper_text,
  DROP COLUMN IF EXISTS helper_picks,
  DROP COLUMN IF EXISTS sorting_confirmed_at,
  DROP COLUMN IF EXISTS sorting_sources,
  DROP COLUMN IF EXISTS brings,
  DROP COLUMN IF EXISTS area,
  DROP COLUMN IF EXISTS affects,
  DROP COLUMN IF EXISTS city,
  DROP COLUMN IF EXISTS often,
  DROP COLUMN IF EXISTS summary,
  DROP COLUMN IF EXISTS title,
  DROP COLUMN IF EXISTS status_changed_at,
  DROP COLUMN IF EXISTS status;

-- Ideas given a reference by new code get the old SUB- twin back, so the old pairing rule holds again.
UPDATE ideas SET submission_id = 'SUB-' || substr(idea_id, 6) WHERE idea_id IS NOT NULL AND submission_id IS NULL;
ALTER TABLE ideas DROP CONSTRAINT IF EXISTS ideas_submission_pair;
ALTER TABLE ideas ADD CONSTRAINT ideas_check CHECK ((idea_id IS NULL) = (submission_id IS NULL));
ALTER TABLE ideas ADD CONSTRAINT ideas_check1 CHECK (idea_id IS NULL OR substr(idea_id, 6) = substr(submission_id, 5));

UPDATE ideas SET kind = 'problem_with_solution' WHERE kind = 'fix';
ALTER TABLE ideas DROP CONSTRAINT IF EXISTS ideas_kind_check;
ALTER TABLE ideas ADD CONSTRAINT ideas_kind_check CHECK (kind IN ('problem', 'problem_with_solution', 'business_idea'));

DELETE FROM role_grants WHERE role IN ('employee', 'committee', 'build_team', 'display');
ALTER TABLE role_grants DROP CONSTRAINT IF EXISTS role_grants_role_check;
ALTER TABLE role_grants ADD CONSTRAINT role_grants_role_check CHECK (role IN (
  'reviewer', 'lob_committee', 'core_committee', 'core_chair', 'appeal_panel',
  'working_group', 'sponsor', 'admin', 'infosec', 'hr', 'ceo'));

DROP TABLE IF EXISTS person_settings;
ALTER TABLE comms_prefs DROP COLUMN IF EXISTS reminders, DROP COLUMN IF EXISTS email, DROP COLUMN IF EXISTS teams;
ALTER TABLE users DROP COLUMN IF EXISTS tier, DROP COLUMN IF EXISTS area, DROP COLUMN IF EXISTS first_name;
