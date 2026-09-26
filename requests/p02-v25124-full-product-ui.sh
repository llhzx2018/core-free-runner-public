#!/usr/bin/env bash
# V2.5.124 full-product gate exact-source trigger
set -Eeuo pipefail

ROOT="$PWD"
PRODUCT="$ROOT/product"
SITE="$RUNNER_TEMP/p02-v25124-full-ui-site"
COOKIE="$RUNNER_TEMP/p02-v25124-full-ui-cookie.txt"
PORT=18225
BASE="http://127.0.0.1:$PORT"
PASSWORD="P02-V25124-FULL-UI-${GITHUB_RUN_ID}!"

cleanup(){
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

rm -rf "$SITE" "$COOKIE"
bash "$PRODUCT/scripts/build-deploy-tree.sh" "$SITE"
test "$(cat "$SITE/VERSION.txt")" = "2.5.124"

php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUNNER_TEMP/p02-v25124-full-ui-server.log" 2>&1 &
PID=$!
for _ in $(seq 1 80); do
  curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break
  sleep .25
done
kill -0 "$PID"

curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/p02-v25124-full-ui-setup.html"
grep -q "创建管理员密码" "$RUNNER_TEMP/p02-v25124-full-ui-setup.html"
TOKEN="$(python3 - "$RUNNER_TEMP/p02-v25124-full-ui-setup.html" <<'PY'
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

# Compatibility / standalone UI reachability.
for route in system-info.php system-baseline.php diagnose.php; do
  curl -fsS -b "$COOKIE" "$BASE/$route" > "$RUNNER_TEMP/$route.html"
  grep -q "返回设置" "$RUNNER_TEMP/$route.html"
  grep -qi "noindex" "$RUNNER_TEMP/$route.html"
done
test "$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' -b "$COOKIE" "$BASE/scratch/index.php")" = "302 $BASE/?scratch=1"

export VF_UX_E2E_BASE_URL="$BASE"
export VF_UX_E2E_PASSWORD="$PASSWORD"
export VF_UX_E2E_VERSION="2.5.124"

cd "$PRODUCT"

# Existing family evidence: shell/list/notebook/reader/editor/search/Scratch/mobile.
node tests/e2e/p02_ux_task_flow.mjs
node tests/e2e/p02_v2537_inkstone_shell.mjs
node tests/e2e/p02_v25102_whole_product_final_audit.mjs
node tests/e2e/p02_v2587_global_search_reentry_continuity.mjs
node tests/e2e/p02_v2594_responsive_pane_continuity.mjs
node tests/e2e/p02_v2595_notebook_request_order.mjs

# Settings final family evidence.
node tests/e2e/p02_v25121_settings_ia_functional_closure.mjs
node tests/e2e/p02_v25122_settings_production_closure.mjs
node tests/e2e/p02_v25123_runtime_health_worker_closure.mjs
node tests/e2e/p02_v25124_settings_functional_content_closure.mjs

echo P02_V25124_FULL_PRODUCT_BROWSER_MATRIX=PASS
