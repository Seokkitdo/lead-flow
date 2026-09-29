#!/usr/bin/env bash
set -euo pipefail
: "${LEADFLOW_DATABASE_URL:?Set a disposable PostgreSQL database URL}"
if [ "${LEADFLOW_DISPOSABLE_DATABASE:-}" != "yes" ]; then
  echo 'This check downgrades the schema. Set LEADFLOW_DISPOSABLE_DATABASE=yes only for an isolated test database.' >&2
  exit 1
fi
cd "$(dirname "$0")/../apps/api"
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/alembic downgrade base
.venv/bin/alembic upgrade head
