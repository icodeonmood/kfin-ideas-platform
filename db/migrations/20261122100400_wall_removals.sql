-- migrate:up
-- "Take off the Wall" (DEC-106, SHIP_PLAN_1PC §6.3; lane A, BLD-A212): the one audit-logged action left from the
-- retired spam hold and committee-only visibility. The review desk or an admin takes a shared idea's summary off
-- the Wall with a reason, and can put it back. One live removal per idea; a restore closes it and keeps the row.
-- The reason is staff-written, checked against the shared hidden-detail patterns before it is stored, and copied
-- to audit_log.reason as role changes are. Nothing here is an idea's own text.
CREATE TABLE wall_removals (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idea_uuid      uuid        NOT NULL REFERENCES ideas (id) ON DELETE CASCADE,
  by             uuid        NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
  reason         text        NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 10 AND 500),
  at             timestamptz NOT NULL DEFAULT now(),
  restored_at    timestamptz,
  restored_by    uuid        REFERENCES users (id) ON DELETE RESTRICT,
  restore_reason text        CHECK (restore_reason IS NULL OR char_length(btrim(restore_reason)) BETWEEN 10 AND 500),
  CHECK ((restored_at IS NULL) = (restored_by IS NULL)),
  CHECK (restored_at IS NULL OR restore_reason IS NOT NULL)
);
CREATE UNIQUE INDEX wall_removals_live ON wall_removals (idea_uuid) WHERE restored_at IS NULL;
CREATE INDEX wall_removals_at ON wall_removals (at DESC);
-- An audit-like record: only the worker takes off and puts back (programme/wall.py); the web role may read and
-- insert, never change or remove a row (pinned in test_b4_service_roles.APPEND_ONLY_FOR_WEB).
REVOKE UPDATE, DELETE ON wall_removals FROM ideas_web_svc;

-- THE shared test every Wall reader adds (views/wall.py today; lane E's wall/common.py `on_wall_sql`, the office
-- screen and any other public reader): `AND NOT idea_off_wall(i.id)`. Callable from both service roles, so the
-- worker and the web app filter with one definition.
CREATE OR REPLACE FUNCTION idea_off_wall(p_idea uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT EXISTS (SELECT 1 FROM wall_removals r WHERE r.idea_uuid = p_idea AND r.restored_at IS NULL)
$$;

-- migrate:down
GRANT UPDATE, DELETE ON wall_removals TO ideas_web_svc;
DROP FUNCTION IF EXISTS idea_off_wall(uuid);
DROP TABLE IF EXISTS wall_removals;
