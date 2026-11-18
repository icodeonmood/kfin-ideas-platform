-- migrate:up
-- "Ask to join the build team" (L-DECIDE.rules/6, A-API POST /ideas/:id/join-build; DEC-111, BLD-B256). After a Pick,
-- the sharer or a member of the idea's crew can ask once, until the build team is chosen. The ask is kept once per
-- person and idea; a repeat changes nothing. The programme admin reads the asks when choosing the team (S-ADMIN).
-- The worker writes it, with one audit_log row per new ask (IDs only); it holds no text.
CREATE TABLE join_build_asks (
  id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_uuid uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  user_id   uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  asked_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (idea_uuid, user_id)
);
CREATE INDEX join_build_asks_idea ON join_build_asks (idea_uuid, asked_at);
-- Both service roles read and write it, as for crew_members and teamup_requests (the default privileges of
-- 20261110000300; stated here so the grant does not depend on which role runs the migration).
GRANT SELECT, INSERT, UPDATE, DELETE ON join_build_asks TO ideas_web_svc, ideas_worker_svc;

-- migrate:down
DROP TABLE IF EXISTS join_build_asks;
