-- migrate:up
-- Weekly clustering (§4.4 B): batch runs, the proposals they put in the review queue, cannot-link pairs, and the
-- cluster read model's text. Proposal and cluster text is the cluster-summary agent's tagged output, restored on
-- view like an idea's canvas; tags are scoped to the proposal (`tag_scope`), never to a member idea.

ALTER TABLE clusters
  ADD COLUMN title              text,          -- tagged; ≤ 8 words
  ADD COLUMN summary            jsonb,         -- tagged: problem, variations, solution, open_questions, roles
  ADD COLUMN tag_scope          text,          -- pseudonym-vault scope of the text above
  ADD COLUMN generated_by       text,          -- cluster-summary/<version>
  ADD COLUMN state              text NOT NULL DEFAULT 'approved' CHECK (state IN ('approved', 'retired')),
  ADD COLUMN merged_into        text CHECK (merged_into ~ '^CL-[0-9]{4}$'),
  ADD COLUMN approved_by        text CHECK (approved_by ~ '^REV-[0-9]{4}$'),
  ADD COLUMN approved_at        timestamptz,
  ADD COLUMN members_changed_at timestamptz;

CREATE TABLE cluster_runs (
  id          text        PRIMARY KEY CHECK (id ~ '^RUN-[0-9]{4}-W[0-9]{2}(-[0-9]+)?$'),  -- a second run in one week gets -2, -3 …
  state       text        NOT NULL DEFAULT 'running' CHECK (state IN ('running', 'done', 'failed')),
  params      jsonb       NOT NULL DEFAULT '{}',   -- thresholds and method, from rules/thresholds.md
  pool_size   integer,
  anchors     integer,
  counts      jsonb       NOT NULL DEFAULT '{}',   -- proposals by kind, outliers dropped, skipped ideas
  error_code  text,
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

CREATE TABLE cluster_proposals (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id          text        NOT NULL REFERENCES cluster_runs (id),
  review_item_id  bigint      UNIQUE REFERENCES review_items (id) ON DELETE CASCADE,
  kind            text        NOT NULL CHECK (kind IN ('new', 'grow', 'merge', 'split')),
  targets         text[]      NOT NULL DEFAULT '{}',  -- approved clusters this proposal changes
  members         text[]      NOT NULL,               -- IDEA- IDs proposed (grow: the ones it adds)
  dropped         jsonb       NOT NULL DEFAULT '[]',  -- [{idea_id, reason}] removed by the outlier check (tagged)
  split_groups    jsonb,                              -- split: [[IDEA-…], …]
  metrics         jsonb       NOT NULL DEFAULT '{}',
  summary         jsonb,                              -- tagged cluster-summary output (null: agent unavailable)
  generated_by    text,
  tag_scope       text        NOT NULL,
  state           text        NOT NULL DEFAULT 'open'
                    CHECK (state IN ('open', 'approved', 'rejected', 'superseded')),
  decided_by      text        CHECK (decided_by ~ '^REV-[0-9]{4}$'),
  decided_at      timestamptz,
  cluster_id      text        CHECK (cluster_id ~ '^CL-[0-9]{4}$'),   -- set on approval
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX cluster_proposals_open ON cluster_proposals (state) WHERE state = 'open';

-- Pairs the batch must keep apart (§4.4 A and step 8): a reviewer's "these are different", a rejected proposal
-- or a member removed from one. Must-link pairs come from `idea_links` (joins and a reviewer's attach-to-idea).
CREATE TABLE cluster_pairs (
  idea_a     text        NOT NULL CHECK (idea_a ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  idea_b     text        NOT NULL CHECK (idea_b ~ '^IDEA-[0-9]{4}-[0-9]{6}$'),
  kind       text        NOT NULL DEFAULT 'cannot_link' CHECK (kind IN ('cannot_link')),
  source     text        NOT NULL CHECK (source IN ('proposal_rejected', 'member_removed', 'reviewer')),
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (idea_a, idea_b, kind),
  CHECK (idea_a < idea_b)
);

-- New features start switched off (§7.6, DEC-057) until their gates pass.
INSERT INTO kill_switches (name, state, reason, changed_by) VALUES
  ('clusters.batch', 'off', 'New feature: off until its gates pass', 'migration'),
  ('agent.cluster-summary', 'on', NULL, NULL)
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name IN ('clusters.batch', 'agent.cluster-summary');
DROP TABLE IF EXISTS cluster_pairs;
DROP TABLE IF EXISTS cluster_proposals;
DROP TABLE IF EXISTS cluster_runs;
ALTER TABLE clusters
  DROP COLUMN IF EXISTS title, DROP COLUMN IF EXISTS summary, DROP COLUMN IF EXISTS tag_scope,
  DROP COLUMN IF EXISTS generated_by, DROP COLUMN IF EXISTS state, DROP COLUMN IF EXISTS merged_into,
  DROP COLUMN IF EXISTS approved_by, DROP COLUMN IF EXISTS approved_at, DROP COLUMN IF EXISTS members_changed_at;
