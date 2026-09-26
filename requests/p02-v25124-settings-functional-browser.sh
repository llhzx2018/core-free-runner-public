#!/usr/bin/env bash
# V2.5.124 browser gate trigger
set -Eeuo pipefail

ROOT="$PWD"
PRODUCT="$ROOT/product"
SITE="$RUNNER_TEMP/p02-v25124-settings-site"
COOKIE="$RUNNER_TEMP/p02-v25124-settings-cookie.txt"
PORT=18224
BASE="http://127.0.0.1:$PORT"
PASSWORD="P02-V25124-SETTINGS-${GITHUB_RUN_ID}!"

cleanup(){
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

rm -rf "$SITE" "$COOKIE"
bash "$PRODUCT/scripts/build-deploy-tree.sh" "$SITE"
test "$(cat "$SITE/VERSION.txt")" = "2.5.124"

php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUNNER_TEMP/p02-v25124-settings-server.log" 2>&1 &
PID=$!
for _ in $(seq 1 80); do
  curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break
  sleep .25
done
kill -0 "$PID"

curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/p02-v25124-settings-setup.html"
TOKEN="$(python3 - "$RUNNER_TEMP/p02-v25124-settings-setup.html" <<'PY'
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
node tests/e2e/p02_v25121_settings_ia_functional_closure.mjs
node tests/e2e/p02_v25122_settings_production_closure.mjs
node tests/e2e/p02_v25123_runtime_health_worker_closure.mjs
node tests/e2e/p02_v25124_settings_functional_content_closure.mjs

echo P02_V25124_SETTINGS_BROWSER_MATRIX=PASS
