#!/usr/bin/env bash
# This check writes synthetic data. Never point it at a production database.
set -euo pipefail
umask 077
: "${POSTGRES_CONTAINER:?Set an isolated PostgreSQL 17 test container}"
if [ "${LEADFLOW_DISPOSABLE_DATABASE:-}" != yes ]; then
  echo 'Set LEADFLOW_DISPOSABLE_DATABASE=yes only for an isolated test database.' >&2
  exit 1
fi

backup=$(mktemp)
restore_db="leadflow_restore_check_$$_${RANDOM}"
created_restore=no
cleanup() {
  if [ "$created_restore" = yes ]; then
    docker exec "$POSTGRES_CONTAINER" dropdb -U leadflow --if-exists "$restore_db"
  fi
  rm -f -- "$backup"
}
trap cleanup EXIT

docker exec "$POSTGRES_CONTAINER" psql -U leadflow -d leadflow -v ON_ERROR_STOP=1 -c "
  CREATE TABLE deployment_backup_probe (id integer PRIMARY KEY, value text NOT NULL);
  INSERT INTO deployment_backup_probe VALUES (1, 'synthetic-backup-fixture'), (2, 'synthetic-restore-fixture');
"
revision=$(docker exec "$POSTGRES_CONTAINER" psql -U leadflow -d leadflow -At -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version;')
test -n "$revision"
docker exec "$POSTGRES_CONTAINER" pg_dump -U leadflow -d leadflow -Fc > "$backup"
docker exec "$POSTGRES_CONTAINER" createdb -U leadflow -T template0 "$restore_db"
created_restore=yes
docker exec -i "$POSTGRES_CONTAINER" pg_restore -U leadflow -d "$restore_db" --no-owner --exit-on-error < "$backup"
restored_revision=$(docker exec "$POSTGRES_CONTAINER" psql -U leadflow -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version;')
test "$revision" = "$restored_revision"
restored=$(docker exec "$POSTGRES_CONTAINER" psql -U leadflow -d "$restore_db" -At -v ON_ERROR_STOP=1 -c 'SELECT string_agg(value, '\'', '\'' ORDER BY id) FROM deployment_backup_probe;')
test "$restored" = 'synthetic-backup-fixture, synthetic-restore-fixture'
docker exec "$POSTGRES_CONTAINER" psql -U leadflow -d leadflow -v ON_ERROR_STOP=1 -c 'DROP TABLE deployment_backup_probe;'
echo 'PostgreSQL backup restored successfully; migration revision and fixture data match.'
