#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$PWD"
PRODUCT="$ROOT/product"
SITE="$RUNNER_TEMP/p02-v25121-discovery-site"
COOKIE="$RUNNER_TEMP/p02-v25121-discovery-cookie.txt"
BASE="http://127.0.0.1:18291"
PASSWORD="P02-V25121-DISCOVERY-${GITHUB_RUN_ID}!"

cleanup(){
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

rm -rf "$SITE" "$COOKIE"
bash "$PRODUCT/scripts/build-deploy-tree.sh" "$SITE"
test "$(cat "$SITE/VERSION.txt")" = "2.5.120"

php -d display_errors=0 -S 127.0.0.1:18291 -t "$SITE" >"$RUNNER_TEMP/p02-v25121-discovery-server.log" 2>&1 &
PID=$!
for _ in $(seq 1 80); do
  curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break
  sleep .25
done
kill -0 "$PID"

curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/p02-v25121-discovery-setup.html"
TOKEN="$(python3 - "$RUNNER_TEMP/p02-v25121-discovery-setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)"
STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE"   --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PASSWORD"   --data-urlencode "password_confirm=$PASSWORD" "$BASE/setup.php")"
test "$STATUS" = "303"

SESSION="$(curl -fsS -b "$COOKIE" "$BASE/api.php?action=session")"
CSRF="$(jq -r .csrf <<<"$SESSION")"
jq -e '.ok==true and .site.auth==true and .version=="2.5.120"' <<<"$SESSION" >/dev/null

CHECK="$(curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF"   -d '{"manual":true}' "$BASE/api.php?action=update_check")"

jq -e '
  .ok==true and
  .checked==true and
  .core.status=="AVAILABLE" and
  .core.from_version=="2.5.120" and
  .core.target_version=="2.5.121" and
  .status.current_version=="2.5.120" and
  .status.latest_version=="2.5.121" and
  .status.update_available==true and
  .status.can_update==true and
  .status.core_status=="AVAILABLE" and
  .status.update_source=="public-stable-mirror"
' <<<"$CHECK" >/dev/null

NOTES="$(curl -fsS -b "$COOKIE" "$BASE/api.php?action=update_release_notes")"
jq -e '.ok==true and .notes.version=="2.5.121"' <<<"$NOTES" >/dev/null

echo P02_V25121_STABLE_DISCOVERY_2_5_120_TO_2_5_121=PASS
