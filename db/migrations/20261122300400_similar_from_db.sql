-- migrate:up
-- Similar ideas from the database (L-SIMILAR, BLD-C091, DEC-106). Since nothing writes ideas to the company repo,
-- the repo's idea files in the index are stale copies (they made last week's ghost match cards). Matching now reads
-- one chunk per shared idea, built from its row (masked title and short summary) and kept fresh by the worker;
-- repo-sourced chunks stay for the old pipeline until the cleanup migration, and the new matcher never reads them.

ALTER TABLE chunks
  ADD COLUMN idea_uuid uuid REFERENCES ideas (id) ON DELETE CASCADE,  -- a shared idea's row
  ADD COLUMN text_hash text;                                          -- sha256 of `text`: re-embed only on change

-- The one-source rule gains the idea row (the constraint was created unnamed).
DO $$
DECLARE c text;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'chunks'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%num_nonnulls%'
  LOOP
    EXECUTE format('ALTER TABLE chunks DROP CONSTRAINT %I', c);
  END LOOP;
END $$;
ALTER TABLE chunks ADD CONSTRAINT chunks_one_source CHECK (num_nonnulls(repo_path, attachment_id, idea_uuid) = 1);
CREATE UNIQUE INDEX chunks_idea ON chunks (idea_uuid) WHERE idea_uuid IS NOT NULL;

-- The last matching run per draft or idea (L-SIMILAR.rules/4, /5, /9): Check it reads the stored result instead of
-- waiting, a failure is shown and retried after sharing, and a re-run happens only on a material change. The words
-- matched on are kept only as keyed hashes of distinct words, never as text (non-negotiable 3).
CREATE TABLE similar_runs (
  idea_uuid    uuid        PRIMARY KEY REFERENCES ideas (id) ON DELETE CASCADE,
  state        text        NOT NULL CHECK (state IN ('done', 'failed')),
  found_while  text        NOT NULL CHECK (found_while IN ('drafting', 'checking', 'later')),
  labelled_by  text        CHECK (labelled_by IN ('judge', 'code')),
  word_hashes  text[]      NOT NULL DEFAULT '{}',
  found        smallint    NOT NULL DEFAULT 0 CHECK (found >= 0),
  error_code   text,
  ran_at       timestamptz NOT NULL DEFAULT now()
);

-- migrate:down
DROP TABLE IF EXISTS similar_runs;
DROP INDEX IF EXISTS chunks_idea;
DELETE FROM chunks WHERE idea_uuid IS NOT NULL;
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_one_source;
ALTER TABLE chunks ADD CONSTRAINT chunks_check CHECK (num_nonnulls(repo_path, attachment_id) = 1);
ALTER TABLE chunks DROP COLUMN IF EXISTS text_hash, DROP COLUMN IF EXISTS idea_uuid;
