#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT="$PWD/product"
SITE="$RUNNER_TEMP/p02-v25124-whole-backend-site"
COOKIE="$RUNNER_TEMP/p02-v25124-whole-backend-cookie.txt"
PORT=18226
BASE="http://127.0.0.1:$PORT"
PASSWORD="P02-V25124-WHOLE-${GITHUB_RUN_ID}!"
cleanup(){ if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi; }
trap cleanup EXIT
rm -rf "$SITE" "$COOKIE"
bash "$PRODUCT/scripts/build-deploy-tree.sh" "$SITE"
test "$(cat "$SITE/VERSION.txt")" = "2.5.124"
php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUNNER_TEMP/p02-v25124-whole-server.log" 2>&1 &
PID=$!
for _ in $(seq 1 100); do curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/p02-v25124-whole-setup.html"
TOKEN="$(python3 - "$RUNNER_TEMP/p02-v25124-whole-setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)"
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PASSWORD" --data-urlencode "password_confirm=$PASSWORD" "$BASE/setup.php")" = "303"
export VF_UX_E2E_BASE_URL="$BASE"
export VF_UX_E2E_PASSWORD="$PASSWORD"
export VF_UX_E2E_VERSION="2.5.124"
cd "$PRODUCT"
node tests/e2e/p02_ux_task_flow.mjs
node tests/e2e/p02_v25102_whole_product_final_audit.mjs
node tests/e2e/p02_v2583_navigation_safety.mjs
node tests/e2e/p02_v2584_auth_boundary_continuity.mjs
node tests/e2e/p02_v2585_editor_adjacent_mutation_continuity.mjs
node tests/e2e/p02_v2586_history_restore_continuity.mjs
node tests/e2e/p02_v2587_global_search_reentry_continuity.mjs
node tests/e2e/p02_v2593_batch_workspace_entry_safety.mjs
node tests/e2e/p02_v2594_responsive_pane_continuity.mjs
node tests/e2e/p02_v2595_notebook_request_order.mjs
node tests/e2e/p02_v25124_settings_functional_content_closure.mjs
echo P02_V25124_WHOLE_BACKEND_UX_AUDIT=PASS
