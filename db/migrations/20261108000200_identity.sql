-- migrate:up
-- People, coded contributor IDs and role grants (§2.5, §3.1). Refreshed from the HR directory (B2).

CREATE TABLE users (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  emp_id_hash      text        NOT NULL UNIQUE,          -- HMAC of the HR employee ID; the raw ID is never stored
  entra_oid        text        UNIQUE,
  name             text        NOT NULL,
  email            text        NOT NULL,
  lob_id           text        CHECK (lob_id ~ '^LOB-[a-z0-9-]+$'),
  role_title       text,
  role_family      text        CHECK (role_family ~ '^ROLE-[a-z0-9-]+$'),
  location         text,
  manager_user_id  uuid        REFERENCES users (id) ON DELETE SET NULL,
  staff_code       text        UNIQUE CHECK (staff_code ~ '^REV-[0-9]{4}$'),
  active           boolean     NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_lower ON users (lower(email));
CREATE TRIGGER users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Restricted: the only link from a coded ID to a person. Deleting a row anonymises that person everywhere.
CREATE TABLE contributor_map (
  contributor_code text        PRIMARY KEY CHECK (contributor_code ~ '^CTR-[0-9a-f]{6,8}$'),
  user_id          uuid        NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE role_grants (
  id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     uuid        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  role        text        NOT NULL CHECK (role IN (
                'reviewer', 'lob_committee', 'core_committee', 'core_chair', 'appeal_panel',
                'working_group', 'sponsor', 'admin', 'infosec', 'hr')),
  scope_id    text,                                     -- LOB-…, CL-…, WG-… or NULL for org-wide
  granted_by  uuid        REFERENCES users (id) ON DELETE SET NULL,
  valid_from  timestamptz NOT NULL DEFAULT now(),       -- "from" in §2.5
  valid_to    timestamptz,                              -- "to" in §2.5; NULL = open-ended
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX role_grants_user ON role_grants (user_id);
CREATE INDEX role_grants_role ON role_grants (role, scope_id);

CREATE TABLE comms_prefs (
  user_id             uuid        PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  routine             text        NOT NULL DEFAULT 'immediate' CHECK (routine IN ('immediate', 'digest')),
  manager_notes       boolean     NOT NULL DEFAULT true,
  public_name_consent boolean     NOT NULL DEFAULT false,
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER comms_prefs_updated_at BEFORE UPDATE ON comms_prefs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- migrate:down
DROP TABLE IF EXISTS comms_prefs;
DROP TABLE IF EXISTS role_grants;
DROP TABLE IF EXISTS contributor_map;
DROP TABLE IF EXISTS users;
