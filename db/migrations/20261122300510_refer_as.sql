-- migrate:up
-- DEC-108 (3), BLD-E010 (lane C, BLD-C111): how the person wants to be referred to, asked once in Profile (S-H6, "How
-- should we refer to you?", with "Prefer not to say"). NULL is unset: copy uses their first name or "they", and the
-- translation of their voice notes is sent without a gender (neutral wording). 'they' is a choice and is also sent
-- without a gender, since mayura:v1 takes only Male or Female. The person reads and changes it at /api/me/refer-as;
-- the worker reads it for the translation. It is never shown to anyone else and never logged.
ALTER TABLE person_settings
  ADD COLUMN refer_as text CONSTRAINT person_settings_refer_as_check CHECK (refer_as IN ('she', 'he', 'they'));

-- migrate:down
ALTER TABLE person_settings DROP COLUMN IF EXISTS refer_as;
