-- Run after migrations as the actual deployment database owner; do not use this role for migrations.
\set ON_ERROR_STOP on
\if :{?app_password}
\else
\getenv app_password ONESA_APP_DB_PASSWORD
\endif
-- Preserve an existing credential; refuse to repurpose an elevated role.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='onesa_app' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
  RAISE EXCEPTION 'Existing onesa_app has elevated privileges; review separately';
 END IF;
END $$;
SELECT format('CREATE ROLE onesa_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', :'app_password')
WHERE NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='onesa_app') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO onesa_app', current_database()) \gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO onesa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO onesa_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO onesa_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, TRIGGER ON alembic_version FROM onesa_app;
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO onesa_app', current_user) \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO onesa_app', current_user) \gexec
