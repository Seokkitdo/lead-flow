#!/usr/bin/env bash
# Run on the production host. The registry token is read from stdin, never argv.
set -euo pipefail
umask 077

if [ "$#" -ne 3 ]; then
  echo 'Usage: deploy.sh API_IMAGE@sha256:DIGEST GATEWAY_IMAGE@sha256:DIGEST GITHUB_USER < registry-token' >&2
  exit 2
fi
for image in "$1" "$2"; do
  if ! [[ "$image" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]]; then
    echo 'Deployment requires immutable GHCR image digests.' >&2
    exit 2
  fi
done
if ! [[ "$3" =~ ^[a-zA-Z0-9_-]+(\[bot\])?$ ]]; then
  echo 'Invalid registry username.' >&2
  exit 2
fi

release_dir=$(cd -- "$(dirname -- "$0")" && pwd)
deploy_root=${LEADFLOW_DEPLOY_ROOT:-/opt/leadflow}
test -s "$deploy_root/.env"
test -f "$release_dir/compose.production.yaml"
exec 9>"$deploy_root/.deploy.lock"
flock -w 900 9

export API_IMAGE="$1" GATEWAY_IMAGE="$2"
compose=(docker compose --project-name leadflow --env-file "$deploy_root/.env" -f "$release_dir/compose.production.yaml")
"${compose[@]}" config --quiet

registry_config=$(mktemp -d "$deploy_root/.registry.XXXXXX")
export DOCKER_CONFIG="$registry_config"
restore_db=''
cleanup() {
  if [ -n "$restore_db" ]; then
    "${compose[@]}" exec -T db dropdb -U leadflow --if-exists "$restore_db" || true
  fi
  rm -rf -- "$registry_config"
}
trap cleanup EXIT

docker login ghcr.io --username "$3" --password-stdin
"${compose[@]}" pull api gateway
"${compose[@]}" up -d --wait --wait-timeout 120 db

mkdir -p "$deploy_root/backups"
chmod 700 "$deploy_root/backups"
backup="$deploy_root/backups/$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}.dump"
"${compose[@]}" exec -T db pg_dump -U leadflow -d leadflow -Fc > "$backup.partial"
mv -- "$backup.partial" "$backup"

# Restore into a new, isolated database before changing the production schema.
restore_db="leadflow_restore_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
"${compose[@]}" exec -T db createdb -U leadflow -T template0 "$restore_db"
"${compose[@]}" exec -T db pg_restore -U leadflow -d "$restore_db" --no-owner --exit-on-error < "$backup"
"${compose[@]}" exec -T db psql -U leadflow -d "$restore_db" -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS restored_tables FROM information_schema.tables WHERE table_schema = '\''public'\'';'
"${compose[@]}" exec -T db dropdb -U leadflow "$restore_db"
restore_db=''

# A fresh, single migration container must succeed before application replacement.
"${compose[@]}" run --rm --no-deps migrate
"${compose[@]}" up -d --no-deps --wait --wait-timeout 180 api gateway

mapfile -t domains < <("${compose[@]}" config --format json | python3 -c 'import json,sys; e=json.load(sys.stdin)["services"]["gateway"]["environment"]; print(e["WEB_DOMAIN"]); print(e["ADMIN_DOMAIN"])')
test "${#domains[@]}" -eq 2
for domain in "${domains[@]}"; do
  curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-connrefused --max-time 15 "https://$domain/api/health"
  curl --fail --silent --show-error --max-time 15 --output /dev/null "https://$domain/"
done

if [ -f "$deploy_root/current-images.env" ]; then
  cp "$deploy_root/current-images.env" "$deploy_root/previous-images.env"
fi
printf 'API_IMAGE=%s\nGATEWAY_IMAGE=%s\n' "$API_IMAGE" "$GATEWAY_IMAGE" > "$deploy_root/current-images.env.tmp"
mv "$deploy_root/current-images.env.tmp" "$deploy_root/current-images.env"
ln -sfn "$release_dir" "$deploy_root/current"
echo 'Deployment completed; both HTTPS endpoints passed health checks.'
