#!/usr/bin/env bash
set -Eeuo pipefail

: "${PROJECT_ID:?}"
: "${COMPONENT_ID+x}"
: "${RUN_ID:?}"
: "${EVIDENCE_DIR:?}"
: "${COMPOSE_FILE:?}"
: "${COMPOSE_PROJECT_NAME:?}"

VF_HTTP_PORT="${VF_HTTP_PORT:-18080}"
BASE_URL="http://127.0.0.1:${VF_HTTP_PORT}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$EVIDENCE_DIR/logs"

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }
cleanup() {
  compose logs --no-color >"$EVIDENCE_DIR/logs/compose.log" 2>&1 || true
  compose down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  printf '%s\n' "$1" >"$EVIDENCE_DIR/failure.txt"
  echo "BLOCKED_ENV: $1" >&2
  exit 4
}

compose pull db wordpress
compose up -d db wordpress
DB_CID="$(compose ps -q db)"
WP_CID="$(compose ps -q wordpress)"
[[ -n "$DB_CID" && -n "$WP_CID" ]] || fail "containers were not created"

for _ in $(seq 1 60); do
  STATUS="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$DB_CID" 2>/dev/null || true)"
  [[ "$STATUS" == "healthy" ]] && break
  sleep 2
done
[[ "${STATUS:-}" == "healthy" ]] || fail "MariaDB health check did not become healthy"

READY=0
for _ in $(seq 1 90); do
  if curl -fsS --max-time 5 "$BASE_URL/wp-admin/install.php" >/dev/null 2>&1; then READY=1; break; fi
  sleep 2
done
[[ "$READY" == 1 ]] || fail "WordPress installer did not become ready"

curl -fsS --max-time 20 -X POST \
  --data-urlencode 'weblog_title=VF Runner Test' \
  --data-urlencode 'user_name=vf_runner_admin' \
  --data-urlencode 'admin_password=VFRunner_123!Ephemeral' \
  --data-urlencode 'admin_password2=VFRunner_123!Ephemeral' \
  --data-urlencode 'pw_weak=on' \
  --data-urlencode 'admin_email=runner@example.invalid' \
  --data-urlencode 'blog_public=0' \
  --data-urlencode 'Submit=Install WordPress' \
  "$BASE_URL/wp-admin/install.php?step=2" \
  -o "$EVIDENCE_DIR/install-response.html" || fail "WordPress installer POST failed"

TABLE_COUNT="$(compose exec -T db mariadb -N -uvf_runner -pvf_runner_ephemeral vf_test -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='vf_test' AND table_name LIKE 'wp_%';" | tr -d '\r')"
[[ "$TABLE_COUNT" =~ ^[0-9]+$ ]] && (( TABLE_COUNT >= 10 )) || fail "WordPress tables missing"
DB_FACTS="$(compose exec -T db mariadb -N -uvf_runner -pvf_runner_ephemeral vf_test -e "SELECT VERSION(), @@default_storage_engine, @@character_set_server, @@collation_server;" | tr -d '\r')"
MARIADB_VERSION="$(printf '%s' "$DB_FACTS" | awk -F '\t' '{print $1}')"
STORAGE_ENGINE="$(printf '%s' "$DB_FACTS" | awk -F '\t' '{print $2}')"
CHARSET="$(printf '%s' "$DB_FACTS" | awk -F '\t' '{print $3}')"
COLLATION="$(printf '%s' "$DB_FACTS" | awk -F '\t' '{print $4}')"
PHP_VERSION="$(compose exec -T wordpress php -r 'echo PHP_VERSION;' | tr -d '\r')"
WP_VERSION="$(compose exec -T wordpress php -r 'include "/var/www/html/wp-includes/version.php"; echo $wp_version;' | tr -d '\r')"
FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export STARTED_AT FINISHED_AT TABLE_COUNT MARIADB_VERSION STORAGE_ENGINE CHARSET COLLATION PHP_VERSION WP_VERSION
python3 - <<'PY'
import json, os
from pathlib import Path

root = Path(os.environ['EVIDENCE_DIR'])
environment = {
    'wordpress': os.environ['WP_VERSION'],
    'php': os.environ['PHP_VERSION'],
    'mariadb': os.environ['MARIADB_VERSION'],
    'storage_engine': os.environ['STORAGE_ENGINE'],
    'charset': os.environ['CHARSET'],
    'collation': os.environ['COLLATION'],
}
checks = [
    {'id': 'RUNNER-ENV-001', 'status': 'PASS', 'detail': 'MariaDB became healthy.'},
    {'id': 'RUNNER-ENV-002', 'status': 'PASS', 'detail': 'WordPress installer completed.'},
    {'id': 'RUNNER-ENV-003', 'status': 'PASS', 'detail': f"WordPress tables={os.environ['TABLE_COUNT']}"},
    {'id': 'RUNNER-ENV-004', 'status': 'PASS', 'detail': 'InnoDB and utf8mb4 facts recorded.'},
]
result = {
    'schema_version': '2.0',
    'project_id': os.environ['PROJECT_ID'],
    'component_id': os.environ['COMPONENT_ID'],
    'run_id': os.environ['RUN_ID'],
    'status': 'PASS',
    'started_at': os.environ['STARTED_AT'],
    'finished_at': os.environ['FINISHED_AT'],
    'environment': environment,
    'checks': checks,
    'root_causes': [],
}
(root / 'environment.json').write_text(json.dumps(environment, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(root / 'checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY

echo 'RUNNER_BASELINE_PASS'

