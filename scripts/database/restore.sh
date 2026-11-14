#!/bin/sh
set -eu
backup=${1:?Usage: restore.sh BACKUP_FILE NEW_DATABASE_restore}
target=${2:?Use a new database name ending in _restore}
[ -r "$backup" ] || { echo "Backup file is not readable" >&2; exit 1; }
[ "${#target}" -le 63 ] || { echo "Database name exceeds 63 characters" >&2; exit 1; }
case "$target" in *[!a-z0-9_]*|onesa|"" ) echo "Unsafe target name" >&2; exit 1;; esac
case "$target" in *_restore) ;; *) echo "Target must end in _restore" >&2; exit 1;; esac
# createdb fails for existing databases: never clean or overwrite existing user data.
docker compose -p "${ONESA_PROJECT_NAME:-onesa-platform}" exec -T db createdb -U onesa "$target"
docker compose -p "${ONESA_PROJECT_NAME:-onesa-platform}" exec -T db pg_restore -U onesa -d "$target" --no-owner --no-acl --exit-on-error < "$backup"
echo "Restored into new database: $target. Verify it before any promotion."
