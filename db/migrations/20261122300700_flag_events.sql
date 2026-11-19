-- migrate:up
-- The S1 to S3 experiments (P-DECISIONS.experiments, BLD-C170 to C179). `flags`, `flag_assignments` and
-- `flag_exposures` are the cut-over's (20261121500100). This adds only what those tables and the drafts do not
-- already hold: the deciding events, as codes. Never a word anyone typed or said, never a value.
--   s1  `s1.start` (started), `s1.often` / `s1.who` / `s1.size` (answered or skipped), `s1.end` (finished, or left
--       when the person moved on before the last question). One row per draft and event, so the interview's place
--       is kept with the draft and a retry never counts twice.
--   s2  `s2.check` (opened: the draft reached Check it) and `s2.compare` (the check-first comparison shown, and what
--       the person did with it). Always for a draft, at most one row per draft, event and outcome.
--   s3  `s3.listen`: on the phone, whether listening started at once (started) or the screen began with typing
--       (no_permission, voice_off, failed), and `typed_instead`; `s3.note`: a draft sent with a voice note as_heard or
--       corrected, at most one row per draft and outcome.
-- Exposures stay in lane A's flag_exposures (L-AUDIT.flags, BLD-A216). Append-only for the web role, like it.
CREATE TABLE flag_events (
  id       bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  flag_key text        NOT NULL REFERENCES flags (key) ON DELETE CASCADE,
  user_id  uuid        REFERENCES users (id) ON DELETE SET NULL,
  variant  text        NOT NULL CHECK (variant IN ('default', 'alternative')),
  draft_id uuid        REFERENCES ideas (id) ON DELETE CASCADE,
  screen   text        NOT NULL CHECK (screen ~ '^S-[0-9]{2}[A-Z]?$'),
  event    text        NOT NULL CHECK (event ~ '^s[1-3]\.[a-z_]{2,20}$'),
  outcome  text        NOT NULL CHECK (outcome ~ '^[a-z_]{2,30}$'),
  at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT flag_events_event_of_flag CHECK (split_part(event, '.', 1) = flag_key),
  CONSTRAINT flag_events_draft_needed CHECK (draft_id IS NOT NULL OR (flag_key <> 's2' AND event <> 's3.note'))
);
CREATE INDEX flag_events_flag ON flag_events (flag_key, event, at);
CREATE INDEX flag_events_draft ON flag_events (draft_id) WHERE draft_id IS NOT NULL;
CREATE UNIQUE INDEX flag_events_s1_once ON flag_events (draft_id, event) WHERE flag_key = 's1';
CREATE UNIQUE INDEX flag_events_draft_once ON flag_events (draft_id, event, outcome)
  WHERE flag_key = 's2' OR event = 's3.note';
REVOKE UPDATE, DELETE ON flag_events FROM ideas_web_svc;

-- The deciding metrics, one view per flag: counts and rates per variant, never a person, an idea or a word. A person
-- counts from their first exposure to the flag; their drafts are the web drafts they started after it. Read them as
-- the database owner or the worker role (RUNBOOK §2c); the web app never reads them.
--
-- S1: draft completeness against time to submit and drop-off.
CREATE VIEW flag_s1_metrics AS
WITH seen AS (
  SELECT user_id, variant, min(at) AS first_at
  FROM flag_exposures
  WHERE flag_key = 's1' AND user_id IS NOT NULL
  GROUP BY user_id, variant
), drafts AS (
  SELECT s.variant, i.id, i.created_at, i.shared_at,
         (SELECT count(*) FROM idea_parts p
           WHERE p.idea_uuid = i.id AND p.key IN ('title', 'often', 'who', 'value', 'area')
             AND p.state IN ('filled', 'pinned')) AS parts_filled
  FROM seen s
  JOIN contributor_map cm ON cm.user_id = s.user_id
  JOIN ideas i ON i.contributor_code = cm.contributor_code AND i.created_at >= s.first_at AND i.channel = 'web'
  WHERE EXISTS (SELECT 1 FROM idea_messages m WHERE m.idea_uuid = i.id)
), asked AS (
  SELECT variant,
         count(DISTINCT draft_id) FILTER (WHERE event = 's1.start') AS interviews_started,
         count(DISTINCT draft_id) FILTER (WHERE event = 's1.end' AND outcome = 'finished') AS interviews_finished,
         count(DISTINCT draft_id) FILTER (WHERE event = 's1.end' AND outcome = 'left') AS interviews_left,
         count(DISTINCT (draft_id, event)) FILTER (WHERE event IN ('s1.often', 's1.who', 's1.size') AND outcome = 'answered') AS questions_answered,
         count(DISTINCT (draft_id, event)) FILTER (WHERE event IN ('s1.often', 's1.who', 's1.size') AND outcome = 'skipped') AS questions_skipped
  FROM flag_events
  WHERE flag_key = 's1'
  GROUP BY variant
)
SELECT v.variant,
       (SELECT count(DISTINCT s.user_id) FROM seen s WHERE s.variant = v.variant) AS people,
       count(DISTINCT d.id) AS drafts_started,
       count(DISTINCT d.id) FILTER (WHERE d.shared_at IS NOT NULL) AS drafts_shared,
       round(1 - (count(DISTINCT d.id) FILTER (WHERE d.shared_at IS NOT NULL))::numeric
             / nullif(count(DISTINCT d.id), 0), 3) AS drop_off_rate,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM d.shared_at - d.created_at))
              FILTER (WHERE d.shared_at IS NOT NULL))::numeric, 0) AS median_seconds_to_share,
       round(avg(d.parts_filled) FILTER (WHERE d.shared_at IS NOT NULL) / 5, 3) AS completeness_when_shared,
       round(avg(d.parts_filled) / 5, 3) AS completeness_all_drafts,
       coalesce(max(a.interviews_started), 0) AS interviews_started,
       coalesce(max(a.interviews_finished), 0) AS interviews_finished,
       coalesce(max(a.interviews_left), 0) AS interviews_left,
       coalesce(max(a.questions_answered), 0) AS questions_answered,
       coalesce(max(a.questions_skipped), 0) AS questions_skipped
FROM (VALUES ('default'), ('alternative')) AS v (variant)
LEFT JOIN drafts d ON d.variant = v.variant
LEFT JOIN asked a ON a.variant = v.variant
GROUP BY v.variant;

-- S3: phone completion, and how often people correct the transcript. Exposures are logged only on a phone's new S-04
-- (BLD-C173); drafts are those whose first message came from a phone. Notes count drafts sent with a voice note, and
-- those with a note's words changed first; listening counts people.
CREATE VIEW flag_s3_metrics AS
WITH seen AS (
  SELECT user_id, variant, min(at) AS first_at
  FROM flag_exposures
  WHERE flag_key = 's3' AND user_id IS NOT NULL
  GROUP BY user_id, variant
), drafts AS (
  SELECT s.variant, i.id, i.shared_at
  FROM seen s
  JOIN contributor_map cm ON cm.user_id = s.user_id
  JOIN ideas i ON i.contributor_code = cm.contributor_code AND i.created_at >= s.first_at AND i.channel = 'web'
  JOIN idea_messages m ON m.idea_uuid = i.id AND m.seq = 1 AND m.device = 'phone'
), ev AS (
  SELECT variant,
         count(DISTINCT user_id) FILTER (WHERE event = 's3.listen' AND outcome = 'started') AS listened_at_once,
         count(DISTINCT user_id) FILTER (WHERE event = 's3.listen' AND outcome = 'typed_instead') AS typed_instead,
         count(DISTINCT user_id) FILTER (WHERE event = 's3.listen' AND outcome IN ('no_permission', 'voice_off', 'failed'))
           AS began_with_typing,
         count(DISTINCT draft_id) FILTER (WHERE event = 's3.note') AS drafts_with_notes,
         count(DISTINCT draft_id) FILTER (WHERE event = 's3.note' AND outcome = 'corrected') AS drafts_corrected
  FROM flag_events
  WHERE flag_key = 's3'
  GROUP BY variant
)
SELECT v.variant,
       (SELECT count(DISTINCT s.user_id) FROM seen s WHERE s.variant = v.variant) AS people,
       count(DISTINCT d.id) AS phone_drafts_started,
       count(DISTINCT d.id) FILTER (WHERE d.shared_at IS NOT NULL) AS phone_drafts_shared,
       round((count(DISTINCT d.id) FILTER (WHERE d.shared_at IS NOT NULL))::numeric
             / nullif(count(DISTINCT d.id), 0), 3) AS phone_completion_rate,
       coalesce(max(e.drafts_with_notes), 0) AS drafts_with_notes,
       coalesce(max(e.drafts_corrected), 0) AS drafts_corrected,
       round(max(e.drafts_corrected)::numeric / nullif(max(e.drafts_with_notes), 0), 3) AS correction_rate,
       coalesce(max(e.listened_at_once), 0) AS people_listened_at_once,
       coalesce(max(e.typed_instead), 0) AS people_typed_instead,
       coalesce(max(e.began_with_typing), 0) AS people_began_with_typing
FROM (VALUES ('default'), ('alternative')) AS v (variant)
LEFT JOIN drafts d ON d.variant = v.variant
LEFT JOIN ev e ON e.variant = v.variant
GROUP BY v.variant;

-- S2: duplicates reaching the review desk against completion. S-05 logs `s2.check` opened for each draft it opens, and
-- close_match when a close similar idea is found on a Check it opened fresh: the drafts the flag changes (the exposure
-- is logged then too, BLD-C176). A duplicate reaching the desk is such a draft shared on its own: not merged in
-- (L-MERGE.request: asked, or merged). Every count is of distinct drafts or people.
CREATE VIEW flag_s2_metrics AS
WITH seen AS (
  SELECT DISTINCT user_id, variant
  FROM flag_exposures
  WHERE flag_key = 's2' AND user_id IS NOT NULL
), checked AS (
  SELECT variant, draft_id, bool_or(outcome = 'close_match') AS close_first
  FROM flag_events
  WHERE flag_key = 's2' AND event = 's2.check'
  GROUP BY variant, draft_id
), drafts AS (
  SELECT c.variant, i.id, i.shared_at, c.close_first,
         (i.status = 'merged' OR i.merged_into IS NOT NULL
          OR EXISTS (SELECT 1 FROM similar_links l WHERE l.idea_uuid = i.id AND l.outcome = 'merge_asked')) AS merged
  FROM checked c
  JOIN ideas i ON i.id = c.draft_id
), ev AS (
  SELECT variant,
         count(DISTINCT draft_id) FILTER (WHERE outcome = 'shown') AS compare_shown,
         count(DISTINCT draft_id) FILTER (WHERE outcome = 'moved_on') AS compare_moved_on,
         count(DISTINCT draft_id) FILTER (WHERE outcome = 'kept_separate') AS compare_kept_separate,
         count(DISTINCT draft_id) FILTER (WHERE outcome = 'merge_asked') AS compare_merge_asked,
         count(DISTINCT draft_id) FILTER (WHERE outcome = 'mine_is_different') AS compare_mine_is_different
  FROM flag_events
  WHERE flag_key = 's2' AND event = 's2.compare'
  GROUP BY variant
)
SELECT v.variant,
       (SELECT count(DISTINCT s.user_id) FROM seen s WHERE s.variant = v.variant) AS people,
       count(DISTINCT d.id) AS drafts_checked,
       count(DISTINCT d.id) FILTER (WHERE d.shared_at IS NOT NULL) AS drafts_shared,
       count(DISTINCT d.id) FILTER (WHERE d.close_first) AS drafts_with_close_match,
       count(DISTINCT d.id) FILTER (WHERE d.close_first AND d.shared_at IS NOT NULL) AS close_match_shared,
       round((count(DISTINCT d.id) FILTER (WHERE d.close_first AND d.shared_at IS NOT NULL))::numeric
             / nullif(count(DISTINCT d.id) FILTER (WHERE d.close_first), 0), 3) AS completion_rate,
       count(DISTINCT d.id) FILTER (WHERE d.close_first AND d.merged) AS close_match_merged,
       count(DISTINCT d.id) FILTER (WHERE d.close_first AND d.shared_at IS NOT NULL AND NOT d.merged)
         AS duplicates_to_desk,
       round((count(DISTINCT d.id) FILTER (WHERE d.close_first AND d.shared_at IS NOT NULL AND NOT d.merged))::numeric
             / nullif(count(DISTINCT d.id) FILTER (WHERE d.close_first), 0), 3) AS duplicate_rate,
       coalesce(max(e.compare_shown), 0) AS compare_shown,
       coalesce(max(e.compare_moved_on), 0) AS compare_moved_on,
       coalesce(max(e.compare_kept_separate), 0) AS compare_kept_separate,
       coalesce(max(e.compare_merge_asked), 0) AS compare_merge_asked,
       coalesce(max(e.compare_mine_is_different), 0) AS compare_mine_is_different
FROM (VALUES ('default'), ('alternative')) AS v (variant)
LEFT JOIN drafts d ON d.variant = v.variant
LEFT JOIN ev e ON e.variant = v.variant
GROUP BY v.variant;

REVOKE ALL ON flag_s1_metrics, flag_s2_metrics, flag_s3_metrics FROM ideas_web_svc;

-- migrate:down
DROP VIEW IF EXISTS flag_s3_metrics;
DROP VIEW IF EXISTS flag_s2_metrics;
DROP VIEW IF EXISTS flag_s1_metrics;
DROP TABLE IF EXISTS flag_events;
