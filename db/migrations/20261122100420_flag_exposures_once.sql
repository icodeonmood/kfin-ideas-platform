-- migrate:up
-- L-AUDIT.flags: an exposure is logged once per person, screen and variant shown (lane A, BLD-A216). The unique
-- index lets `flag_variant` insert with ON CONFLICT DO NOTHING, so two tabs opening a screen at once still log one.
-- The web role keeps insert only (APPEND_ONLY_FOR_WEB); duplicates already there are kept, the oldest first.
DELETE FROM flag_exposures e USING flag_exposures f
  WHERE e.flag_key = f.flag_key AND e.user_id = f.user_id AND e.screen = f.screen AND e.variant = f.variant
    AND e.id > f.id;
CREATE UNIQUE INDEX flag_exposures_once ON flag_exposures (flag_key, user_id, screen, variant);

-- migrate:down
DROP INDEX IF EXISTS flag_exposures_once;
