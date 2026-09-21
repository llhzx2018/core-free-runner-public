#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT_ROOT="${1:?product root required}"
PRODUCT_ROOT="$(cd "$PRODUCT_ROOT" && pwd)"
EXPECTED_SHA="2a6c4c4e8a3c78b4c68b1d033833192cf26740b4"
EXPECTED_VERSION="2.5.81"
RUN_ROOT="${RUNNER_TEMP:-/tmp}/p02-v2581-r2-${GITHUB_RUN_ID:-local}-$$"
SITE="$RUN_ROOT/site"
COOKIE="$RUN_ROOT/cookies.txt"
PORT=18282
BASE_URL="http://127.0.0.1:$PORT"
TEST_PASSWORD="P02-R2-${GITHUB_RUN_ID:-local}-Safe!"
mkdir -p "$RUN_ROOT"
cleanup(){ if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then kill "$SERVER_PID" 2>/dev/null || true; fi; rm -rf "$RUN_ROOT"; }
trap cleanup EXIT

cd "$PRODUCT_ROOT"
test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"
test "$(tr -d '\r\n' < VERSION)" = "$EXPECTED_VERSION"
bash scripts/verify-repository.sh
node tests/unit/p02_v2581_detail_bugfix_r1.mjs
node tests/unit/p02_v2581_detail_bugfix_r2.mjs

bash scripts/build-deploy-tree.sh "$SITE"
php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUN_ROOT/php-server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 80); do curl -fsS "$BASE_URL/setup.php" >/dev/null 2>&1 && break; sleep 0.25; done
kill -0 "$SERVER_PID"
curl -fsS -c "$COOKIE" "$BASE_URL/setup.php" > "$RUN_ROOT/setup.html"
SETUP_CSRF="$(python3 -c 'import html,re,sys;s=open(sys.argv[1],encoding="utf-8").read();m=re.search(r"name=\"setup_csrf\" value=\"([^\"]+)\"",s);assert m;print(html.unescape(m.group(1)))' "$RUN_ROOT/setup.html")"
STATUS="$(curl -sS -o "$RUN_ROOT/setup-post.html" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE_URL" --data-urlencode "setup_csrf=$SETUP_CSRF" --data-urlencode "password=$TEST_PASSWORD" --data-urlencode "password_confirm=$TEST_PASSWORD" "$BASE_URL/setup.php")"
test "$STATUS" = 303

cp "$GITHUB_WORKSPACE/runner/requests/p02-v2581-r2/browser.mjs" "$PRODUCT_ROOT/tests/e2e/p02_v2581_r2_temp.mjs"
export VF_R2_BASE_URL="$BASE_URL"
export VF_R2_PASSWORD="$TEST_PASSWORD"
node tests/e2e/p02_v2581_r2_temp.mjs
