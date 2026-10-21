#!/bin/sh
set -eu
umask 077
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
mkdir -p /backup-snapshot
pg_dump --host=postgres --username="$POSTGRES_USER" --dbname=portfolio --format=custom --file=/backup-snapshot/portfolio.dump
pg_dump --host=postgres --username="$POSTGRES_USER" --dbname=umami --format=custom --file=/backup-snapshot/umami.dump
restic snapshots >/dev/null 2>&1 || restic init
restic backup /backup-snapshot/portfolio.dump /backup-snapshot/umami.dump /uploads --tag portfolio-cms
restic forget --tag portfolio-cms --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
restic check
