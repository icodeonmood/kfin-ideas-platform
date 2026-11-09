-- migrate:up
-- Recurring friction themes for each role (BLD-139). A weekly learning loop asks the `role-themes` agent to group
-- the role's recent ideas (checked neutral summaries only) into up to four themes. Stored are the theme's checked
-- name and description and how many ideas share it: never idea IDs, idea text or anyone's name. The product team
-- approves or declines each role's set; only approved themes show on the lenses page.
CREATE TABLE role_themes (
  id                bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  role_id           text        NOT NULL CHECK (role_id ~ '^ROLE-[a-z0-9-]+$'),
  period            text        NOT NULL,
  themes            jsonb       NOT NULL,   -- [{name, description, ideas}]: checked words and counts only
  ideas_considered  integer     NOT NULL CHECK (ideas_considered >= 0),
  state             text        NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'approved', 'declined')),
  decided_by        uuid        REFERENCES users (id) ON DELETE RESTRICT,
  decided_at        timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (role_id, period)
);
CREATE INDEX role_themes_open ON role_themes (created_at DESC) WHERE state = 'proposed';

INSERT INTO kill_switches (name, state, reason, changed_by) VALUES ('agent.role-themes', 'on', NULL, NULL)
  ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'agent.role-themes';
DROP TABLE IF EXISTS role_themes;
