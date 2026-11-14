"""Provision only the isolated staging CRUD and backup roles after Alembic."""

import os

import psycopg
from psycopg import sql

if os.environ.get("ONESA_ENVIRONMENT") != "staging":
    raise SystemExit("Role provisioning is limited to explicit staging")
with psycopg.connect(
    host="db", user="onesa", dbname="onesa", password=os.environ["ONESA_DB_PASSWORD"]
) as connection:
    for role, variable in [
        ("onesa_app", "ONESA_APP_DB_PASSWORD"),
        ("onesa_backup", "ONESA_BACKUP_DB_PASSWORD"),
    ]:
        if (
            connection.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)
            ).fetchone()
            is None
        ):
            connection.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(os.environ[variable])
                )
            )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE onesa TO {}").format(
                sql.Identifier(role)
            )
        )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role))
        )
        privileges = (
            sql.SQL("SELECT, INSERT, UPDATE, DELETE")
            if role == "onesa_app"
            else sql.SQL("SELECT")
        )
        connection.execute(
            sql.SQL("GRANT {} ON ALL TABLES IN SCHEMA public TO {}").format(
                privileges, sql.Identifier(role)
            )
        )
        connection.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES FOR ROLE onesa IN SCHEMA public GRANT {} ON TABLES TO {}"
            ).format(privileges, sql.Identifier(role))
        )
    connection.execute(
        "REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM onesa_app"
    )
print("Provisioned non-superuser staging CRUD and read-only backup roles")
