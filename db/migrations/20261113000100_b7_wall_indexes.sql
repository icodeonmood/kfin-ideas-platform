-- migrate:up
-- The wall and My ideas look up links by idea and by cluster (B7 review); the only index was on the coalesce.
CREATE INDEX IF NOT EXISTS idea_links_idea    ON idea_links (idea_id) WHERE idea_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idea_links_cluster ON idea_links (cluster_id) WHERE cluster_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idea_links_code    ON idea_links (contributor_code);
CREATE INDEX IF NOT EXISTS ideas_public       ON ideas (stage, updated_at DESC) WHERE visibility = 'org';

-- migrate:down
DROP INDEX IF EXISTS ideas_public;
DROP INDEX IF EXISTS idea_links_code;
DROP INDEX IF EXISTS idea_links_cluster;
DROP INDEX IF EXISTS idea_links_idea;
