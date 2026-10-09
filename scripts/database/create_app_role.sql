-- Run after migrations as the deployment database owner.
-- Supply app_password privately through psql; never commit/print a real value.
CREATE ROLE onesa_app LOGIN PASSWORD :'app_password';
GRANT CONNECT ON DATABASE onesa TO onesa_app;
GRANT USAGE ON SCHEMA public TO onesa_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO onesa_app;
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM onesa_app;
ALTER DEFAULT PRIVILEGES FOR ROLE onesa IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO onesa_app;
