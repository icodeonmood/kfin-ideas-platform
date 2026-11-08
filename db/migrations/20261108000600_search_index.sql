-- migrate:up
-- Search index built from the company repo (§2.6). It is a copy: `python -m index --rebuild` recreates it.

-- One row per concept file in the repo: what the indexer last saw.
CREATE TABLE repo_files (
  repo_path  text        PRIMARY KEY,
  kfin_id    text,
  file_type  text        NOT NULL,
  trust      text        NOT NULL CHECK (trust IN ('unverified', 'machine', 'human')),
  stage      text,
  visibility text        NOT NULL DEFAULT 'org' CHECK (visibility IN ('org', 'committee')),
  commit_sha text        NOT NULL,
  indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX repo_files_kfin_id ON repo_files (kfin_id);

CREATE TABLE chunks (
  id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  repo_path     text,                                   -- a repo file …
  attachment_id text,                                   -- … or an attachment (week 3)
  file_type     text        NOT NULL,
  section       text        NOT NULL,
  ordinal       integer     NOT NULL DEFAULT 0,
  text          text        NOT NULL,
  embedding     vector(1024),
  tsv           tsvector    GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
  trust         text        NOT NULL CHECK (trust IN ('unverified', 'machine', 'human')),
  stage         text,
  lobs          text[]      NOT NULL DEFAULT '{}',
  category      text,
  area_ids      text[]      NOT NULL DEFAULT '{}',
  visibility    text        NOT NULL DEFAULT 'org' CHECK (visibility IN ('org', 'committee')),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  commit_sha    text,
  CHECK (num_nonnulls(repo_path, attachment_id) = 1)
);
CREATE INDEX chunks_path      ON chunks (repo_path);
CREATE INDEX chunks_type      ON chunks (file_type);
CREATE INDEX chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv       ON chunks USING gin (tsv);

-- The repo as a graph: Markdown links and frontmatter references (plan P3 step 1).
CREATE TABLE links (
  from_path text NOT NULL,
  to_path   text NOT NULL,                              -- a repo path, or "id:<ID>" while the target does not exist
  link_type text NOT NULL CHECK (link_type IN ('markdown', 'frontmatter')),
  PRIMARY KEY (from_path, to_path, link_type)
);
CREATE INDEX links_to ON links (to_path);

-- Glossary terms and aliases for exact and fuzzy lookup (plan P2).
CREATE TABLE terms (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  glossary_id text   NOT NULL CHECK (glossary_id ~ '^GL-[a-z0-9-]+$'),
  term        text   NOT NULL,
  alias       text   NOT NULL,
  repo_path   text   NOT NULL,
  UNIQUE (glossary_id, alias)
);
CREATE INDEX terms_alias_trgm ON terms USING gin (lower(alias) gin_trgm_ops);

-- Last commit the indexer finished (single row).
CREATE TABLE index_state (
  id          smallint    PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_commit text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO index_state (id) VALUES (1);

-- migrate:down
DROP TABLE IF EXISTS index_state;
DROP TABLE IF EXISTS terms;
DROP TABLE IF EXISTS links;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS repo_files;
