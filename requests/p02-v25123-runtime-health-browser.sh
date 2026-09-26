#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$PWD"
PRODUCT="$ROOT/product"
SITE="$RUNNER_TEMP/p02-v25123-runtime-health-site"
COOKIE="$RUNNER_TEMP/p02-v25123-runtime-health-cookie.txt"
PORT=18223
BASE="http://127.0.0.1:$PORT"
PASSWORD="P02-V25123-RUNTIME-${GITHUB_RUN_ID}!"

cleanup(){
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

rm -rf "$SITE" "$COOKIE"
bash "$PRODUCT/scripts/build-deploy-tree.sh" "$SITE"
test "$(cat "$SITE/VERSION.txt")" = "2.5.123"

php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUNNER_TEMP/p02-v25123-runtime-health-server.log" 2>&1 &
PID=$!
for _ in $(seq 1 80); do
  curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break
  sleep .25
done
kill -0 "$PID"

curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/p02-v25123-runtime-health-setup.html"
TOKEN="$(python3 - "$RUNNER_TEMP/p02-v25123-runtime-health-setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)"
STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" \
  --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PASSWORD" \
  --data-urlencode "password_confirm=$PASSWORD" "$BASE/setup.php")"
test "$STATUS" = "303"

export VF_UX_E2E_BASE_URL="$BASE"
export VF_UX_E2E_PASSWORD="$PASSWORD"

cd "$PRODUCT"
node tests/e2e/p02_v25112_system_overview_inline_ux.mjs
node tests/e2e/p02_v25123_runtime_health_worker_closure.mjs

echo P02_V25123_RUNTIME_HEALTH_BROWSER_MATRIX=PASS
