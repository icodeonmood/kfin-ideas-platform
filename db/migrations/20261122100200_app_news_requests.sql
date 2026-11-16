-- migrate:up
-- "Tell me when it's out" for the 1% Club app (S-H3, L-NOTIFY/7, BLD-A192): one row per person, the latest choice.
-- A toggle upserts it, so a person can withdraw. When the app is out, the notice goes to everyone with wants = true.
-- A person's own choice, not a privileged action, so it does not go in audit_log (review of a/display-pages).
CREATE TABLE app_news_requests (
  user_id    uuid        PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  wants      boolean     NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER app_news_requests_updated_at BEFORE UPDATE ON app_news_requests
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
-- Both service roles read and write it, as for person_settings (the default privileges of 20261110000300; stated
-- here so the grant does not depend on which role runs the migration).
GRANT SELECT, INSERT, UPDATE, DELETE ON app_news_requests TO ideas_web_svc, ideas_worker_svc;

-- migrate:down
DROP TABLE IF EXISTS app_news_requests;
