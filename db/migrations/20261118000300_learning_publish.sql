-- migrate:up
-- Approved glossary terms and area tags written into the company repo (BLD-136). After a proposal is approved, an
-- admin writes the definition (or the tag's title and description), checked like any text everyone reads; it is
-- stored sealed and queued for the repo writer as `taxonomy.glossary_added` or `taxonomy.area_added` (IDs only).
-- The writer reads it from here, writes `taxonomy/glossary/GL-<slug>.md` or `taxonomy/areas/AREA-<slug>.md`, and
-- records where. It never overwrites a file the product team wrote by hand.
ALTER TABLE learning_proposals
  ADD COLUMN publish_encrypted bytea,
  ADD COLUMN doc_id            text UNIQUE CHECK (doc_id ~ '^(GL|AREA)-[a-z0-9-]{2,60}$'),
  ADD COLUMN published_by      uuid REFERENCES users (id) ON DELETE RESTRICT,
  ADD COLUMN published_at      timestamptz,
  ADD COLUMN repo_path         text,
  ADD COLUMN repo_commit       text;

-- migrate:down
ALTER TABLE learning_proposals
  DROP COLUMN IF EXISTS repo_commit,
  DROP COLUMN IF EXISTS repo_path,
  DROP COLUMN IF EXISTS published_at,
  DROP COLUMN IF EXISTS published_by,
  DROP COLUMN IF EXISTS doc_id,
  DROP COLUMN IF EXISTS publish_encrypted;
