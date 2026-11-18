-- migrate:up
-- S-03 Home, first visit (BLD-C148): the first time Home is shown to a person it asks "What gets in your way at work,
-- {me}?" and shows "Start here" in place of Needs you, Your ideas and Find your crew (S-03.sections, A-API.home
-- `first_visit`). The web app sets this when it first renders Home for them; NULL means Home has not been shown yet.
-- The person's own setting, like refer_as: never shown to anyone else.
ALTER TABLE person_settings ADD COLUMN home_seen_at timestamptz;

-- migrate:down
ALTER TABLE person_settings DROP COLUMN IF EXISTS home_seen_at;
