-- migrate:up
-- Ones review fixes (BLD-112, BLD-113).
-- At most one legend number a year (DEC-041), enforced by the database as well as by a lock in the service.
ALTER TABLE one_legend_numbers
  ADD COLUMN retired_year integer GENERATED ALWAYS AS (EXTRACT(YEAR FROM retired_on)::integer) STORED;
CREATE UNIQUE INDEX one_legend_numbers_year ON one_legend_numbers (retired_year);

-- The manager team view reads direct reports by manager (DEC-079).
CREATE INDEX IF NOT EXISTS users_manager ON users (manager_user_id) WHERE manager_user_id IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS users_manager;
DROP INDEX IF EXISTS one_legend_numbers_year;
ALTER TABLE one_legend_numbers DROP COLUMN IF EXISTS retired_year;
