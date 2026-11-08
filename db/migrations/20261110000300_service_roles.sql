-- migrate:up
-- Per-service database roles (BLD-032, BLD-077). Group roles only (NOLOGIN); each environment creates login
-- users that are members (dev: `make db-users`; UAT and prod: ops, with passwords from the vault).
--   ideas_worker_svc: the worker (gateway and its restore service, repo writer, indexer, jobs). Everything.
--   ideas_web_svc:    the web app. Never the pseudonym vault or the model cache; the call log read-only;
--                     contributor codes read and created, never changed or removed.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ideas_worker_svc') THEN
    CREATE ROLE ideas_worker_svc NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ideas_web_svc') THEN
    CREATE ROLE ideas_web_svc NOLOGIN;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO ideas_worker_svc, ideas_web_svc;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ideas_worker_svc, ideas_web_svc;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ideas_worker_svc, ideas_web_svc;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO ideas_worker_svc, ideas_web_svc;

REVOKE ALL ON pseudonym_vault, llm_cache FROM ideas_web_svc;
REVOKE INSERT, UPDATE, DELETE ON llm_calls FROM ideas_web_svc;
REVOKE UPDATE, DELETE ON contributor_map FROM ideas_web_svc;
REVOKE ALL ON schema_migrations FROM ideas_worker_svc, ideas_web_svc;

-- Tables added by later migrations get the same default; a migration adding a sensitive table revokes
-- the web role explicitly (and a test checks the list in BLD-077).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ideas_worker_svc, ideas_web_svc;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ideas_worker_svc, ideas_web_svc;

-- migrate:down
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM ideas_worker_svc, ideas_web_svc;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM ideas_worker_svc, ideas_web_svc;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ideas_worker_svc, ideas_web_svc;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM ideas_worker_svc, ideas_web_svc;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM ideas_worker_svc, ideas_web_svc;
REVOKE USAGE ON SCHEMA public FROM ideas_worker_svc, ideas_web_svc;
