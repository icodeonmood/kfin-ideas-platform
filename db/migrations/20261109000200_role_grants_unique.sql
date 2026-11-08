-- migrate:up
-- One live grant per person, role and scope (B2 review): the "already granted" check is now backed by the
-- database, so two admins clicking at once cannot create duplicates.
CREATE UNIQUE INDEX role_grants_live ON role_grants (user_id, role, coalesce(scope_id, '')) WHERE valid_to IS NULL;

-- migrate:down
DROP INDEX IF EXISTS role_grants_live;
