-- migrate:up
-- L-SIMILAR.failure (BLD-C087): "Checked and matched" records whether similar ideas could be checked, so a failed
-- or missing matcher reads "Couldn't check for similar ideas. The review desk will." and never "no similar ideas
-- found". 'done' after a matching run, 'failed' when it failed or matching was not there; empty before the check.
-- Lane C's submit writes it (services/worker/submit/check.py, edit.py). Once c/similar's `similar_runs` is on main,
-- its latest outcome for the idea is read first, since its retries after sharing update that table only.
ALTER TABLE ideas
  ADD COLUMN similar_check text CONSTRAINT ideas_similar_check_check CHECK (similar_check IN ('done', 'failed'));

-- migrate:down
ALTER TABLE ideas DROP COLUMN IF EXISTS similar_check;
