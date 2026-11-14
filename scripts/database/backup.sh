#!/bin/sh
set -eu
umask 077
output=${1:?Usage: backup.sh NEW_BACKUP_FILE}
if [ -e "$output" ]; then echo "Backup target already exists" >&2; exit 1; fi
mkdir -p "$(dirname "$output")"
temporary=$(mktemp "${output}.XXXXXX")
trap 'rm -f "$temporary"' EXIT HUP INT TERM
docker compose -p "${ONESA_PROJECT_NAME:-onesa-platform}" exec -T db pg_dump -U onesa -d onesa --format=custom > "$temporary"
mv "$temporary" "$output"
echo "Backup created: $output"
