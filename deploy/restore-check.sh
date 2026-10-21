#!/bin/sh
set -eu
umask 077
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
work=/backup-snapshot/restore-check
rm -rf "$work"
mkdir -p "$work"
restic restore latest --tag portfolio-cms --target "$work"
dump=$(find "$work" -name portfolio.dump -type f -print -quit)
umami_dump=$(find "$work" -name umami.dump -type f -print -quit)
test -n "$dump"
test -n "$umami_dump"
pg_restore --list "$dump" >/dev/null
pg_restore --list "$umami_dump" >/dev/null
test -d "$work/uploads"
dropdb --host=postgres --username="$POSTGRES_USER" --if-exists portfolio_restore_check
createdb --host=postgres --username="$POSTGRES_USER" portfolio_restore_check
pg_restore --host=postgres --username="$POSTGRES_USER" --dbname=portfolio_restore_check --exit-on-error "$dump"
psql --host=postgres --username="$POSTGRES_USER" --dbname=portfolio_restore_check --command='SELECT count(*) AS restored_posts FROM posts;'
dropdb --host=postgres --username="$POSTGRES_USER" portfolio_restore_check
dropdb --host=postgres --username="$POSTGRES_USER" --if-exists umami_restore_check
createdb --host=postgres --username="$POSTGRES_USER" umami_restore_check
pg_restore --host=postgres --username="$POSTGRES_USER" --dbname=umami_restore_check --exit-on-error "$umami_dump"
psql --host=postgres --username="$POSTGRES_USER" --dbname=umami_restore_check --command="SELECT count(*) AS restored_public_tables FROM information_schema.tables WHERE table_schema = 'public';"
dropdb --host=postgres --username="$POSTGRES_USER" umami_restore_check
echo "Database and upload restore check completed."
