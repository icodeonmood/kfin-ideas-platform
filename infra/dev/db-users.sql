-- Dev only (`make db-users`): login users for the web and worker containers. UAT and prod create these
-- from the vault; never reuse these passwords anywhere.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ideas_web') THEN
    CREATE ROLE ideas_web LOGIN PASSWORD 'dev-web-only' IN ROLE ideas_web_svc;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ideas_worker') THEN
    CREATE ROLE ideas_worker LOGIN PASSWORD 'dev-worker-only' IN ROLE ideas_worker_svc;
  END IF;
END $$;
