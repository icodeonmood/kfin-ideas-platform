-- migrate:up
-- One queued set per reviewer per idea (BLD-B272's fix round; L-QUESTIONS.states "queued (reviewer only)",
-- S-R2.panel Asking). A reviewer's queue is theirs alone, so another reviewer's save never replaces it: each save
-- replaces only its own reviewer's set, and only when its `base` is the revision stored for that reviewer
-- (`desk.asking.save_queue`). Send, a decision and a merge still drop every queued set on the idea
-- (`desk.asking.drop_queued`).
DROP INDEX IF EXISTS question_sets_one_queued;
CREATE UNIQUE INDEX question_sets_one_queued ON question_sets (idea_uuid, by_user_id) WHERE state = 'queued';

-- migrate:down
-- Back to one queued set per idea: each idea keeps its newest queued set and the others go with their questions,
-- the `hidden_details` rows keyed by those questions first, so none outlives its question (as `drop_queued` does).
WITH gone AS (
  SELECT s.id FROM question_sets s
  WHERE s.state = 'queued' AND EXISTS (
    SELECT 1 FROM question_sets n
    WHERE n.idea_uuid = s.idea_uuid AND n.state = 'queued' AND (n.created_at, n.id) > (s.created_at, s.id)
  )
), details AS (
  DELETE FROM hidden_details h USING questions q
  WHERE q.set_id IN (SELECT id FROM gone) AND h.source = 'desk' AND h.source_id = q.id::text
)
DELETE FROM question_sets WHERE id IN (SELECT id FROM gone);
DROP INDEX IF EXISTS question_sets_one_queued;
CREATE UNIQUE INDEX question_sets_one_queued ON question_sets (idea_uuid) WHERE state = 'queued';
