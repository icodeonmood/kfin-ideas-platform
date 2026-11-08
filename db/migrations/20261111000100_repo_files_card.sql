-- migrate:up
-- What a match card may show about a repo file (§4.2 step 7), kept with the file so matching never opens the
-- file: the summary (an idea's `neutral_summary`; a cluster's, solution's or decision's description), its
-- area tags and LOBs. Only files whose summaries are written for everyone carry one (BLD-079).
ALTER TABLE repo_files ADD COLUMN summary  text;
ALTER TABLE repo_files ADD COLUMN area_ids text[] NOT NULL DEFAULT '{}';
ALTER TABLE repo_files ADD COLUMN lobs     text[] NOT NULL DEFAULT '{}';

-- migrate:down
ALTER TABLE repo_files DROP COLUMN IF EXISTS lobs;
ALTER TABLE repo_files DROP COLUMN IF EXISTS area_ids;
ALTER TABLE repo_files DROP COLUMN IF EXISTS summary;
