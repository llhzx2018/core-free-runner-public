#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$PWD"
PRODUCT="$ROOT/product"
: "${TEST_PASSWORD:?TEST_PASSWORD is required}"

cleanup_pids=()
cleanup(){
  for pid in "${cleanup_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

run_upgrade(){
  local SRC="$1"
  local FROM="$2"
  local PORT="$3"
  local SITE="${RUNNER_TEMP}/p02-v25115-from-${FROM}"
  local COOKIE="${RUNNER_TEMP}/p02-v25115-${FROM}-cookie.txt"
  local BASE="http://127.0.0.1:${PORT}"
  local LOG="${RUNNER_TEMP}/p02-v25115-${FROM}-server.log"

  rm -rf "$SITE" "$COOKIE"
  bash "$SRC/scripts/build-deploy-tree.sh" "$SITE"
  test "$(cat "$SITE/VERSION.txt")" = "$FROM"

  php -d display_errors=0 -S "127.0.0.1:${PORT}" -t "$SITE" >"$LOG" 2>&1 &
  local PID=$!
  cleanup_pids+=("$PID")
  for _ in $(seq 1 80); do
    curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break
    sleep .25
  done
  kill -0 "$PID"

  curl -fsS -c "$COOKIE" "$BASE/setup.php" > "${RUNNER_TEMP}/setup-${FROM}.html"
  SETUP_CSRF="$(python3 - "${RUNNER_TEMP}/setup-${FROM}.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)"
  STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE"     --data-urlencode "setup_csrf=$SETUP_CSRF"     --data-urlencode "password=$TEST_PASSWORD"     --data-urlencode "password_confirm=$TEST_PASSWORD" "$BASE/setup.php")"
  test "$STATUS" = "303"

  curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" "$BASE/api.php?action=session" > "${RUNNER_TEMP}/session-${FROM}.json"
  CSRF="$(python3 - "${RUNNER_TEMP}/session-${FROM}.json" "$FROM" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['ok'] and x['site']['auth'] and x['version']==sys.argv[2]
print(x['csrf'])
PY
)"

  cat > "${RUNNER_TEMP}/cat-${FROM}.json" <<JSON
{"name":"V25112 Upgrade ${FROM}","description":"real-data direct upgrade fixture","icon":"folder"}
JSON
  curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json'     --data-binary @"${RUNNER_TEMP}/cat-${FROM}.json" "$BASE/api.php?action=category_save" > "${RUNNER_TEMP}/cat-${FROM}-response.json"
  CATEGORY_ID="$(python3 - "${RUNNER_TEMP}/cat-${FROM}-response.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['ok']
print(x['id'])
PY
)"

  python3 - "${RUNNER_TEMP}/article-${FROM}.json" "$CATEGORY_ID" "$FROM" <<'PY'
import json,sys
marker='P02_V25115_UPGRADE_MARKER_'+sys.argv[3].replace('.','_')
json.dump({
  'category_id':int(sys.argv[2]),
  'title':'V2.5.115 Upgrade Fixture '+sys.argv[3],
  'description':'must survive direct upgrade',
  'content':marker+'\n中文资料完整性\n'+('DATA-LINE\n'*120),
  'content_mode':'article',
  'content_format':'markdown',
  'primary_action':'read',
  'status':'active'
},open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False)
PY
  curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json'     --data-binary @"${RUNNER_TEMP}/article-${FROM}.json" "$BASE/api.php?action=content_save" > "${RUNNER_TEMP}/article-${FROM}-response.json"
  ARTICLE_ID="$(python3 - "${RUNNER_TEMP}/article-${FROM}-response.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['ok']
print(x['id'])
PY
)"

  python3 - "${RUNNER_TEMP}/fixture-${FROM}.png" <<'PY'
import base64,sys
open(sys.argv[1],'wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZfGQAAAAASUVORK5CYII='))
PY
  curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $CSRF"     -F "item_id=$ARTICLE_ID" -F "attachment=@${RUNNER_TEMP}/fixture-${FROM}.png;type=image/png"     "$BASE/api.php?action=attachment_upload" > "${RUNNER_TEMP}/attachment-${FROM}.json"
  python3 - "${RUNNER_TEMP}/attachment-${FROM}.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['ok'] and x['attachments']
PY

  cp "$PRODUCT/build/release-preflight/repair-v2.5.115.php" "$SITE/repair-v2.5.115.php"
  curl -fsS -b "$COOKIE" -c "$COOKIE" "$BASE/repair-v2.5.115.php" > "${RUNNER_TEMP}/repair-${FROM}-form.html"
  REPAIR_CSRF="$(python3 - "${RUNNER_TEMP}/repair-${FROM}-form.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="csrf" value="([^"]+)"',s)
assert m,s[:500]
print(html.unescape(m.group(1)))
PY
)"
  curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE"     --data-urlencode "action=upgrade" --data-urlencode "csrf=$REPAIR_CSRF"     "$BASE/repair-v2.5.115.php" > "${RUNNER_TEMP}/repair-${FROM}-result.html"
  grep -q "升级完成" "${RUNNER_TEMP}/repair-${FROM}-result.html"
  test ! -e "$SITE/repair-v2.5.115.php"
  test "$(cat "$SITE/VERSION.txt")" = "2.5.115"

  curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" "$BASE/api.php?action=session" > "${RUNNER_TEMP}/session-${FROM}-105.json"
  python3 - "${RUNNER_TEMP}/session-${FROM}-105.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['ok'] and x['site']['auth'] and x['version']=='2.5.115'
PY
  curl -fsS -b "$COOKIE" -H "Origin: $BASE" "$BASE/api.php?action=content_get&id=$ARTICLE_ID" > "${RUNNER_TEMP}/article-${FROM}-105.json"
  python3 - "${RUNNER_TEMP}/article-${FROM}-105.json" "$FROM" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
marker='P02_V25115_UPGRADE_MARKER_'+sys.argv[2].replace('.','_')
assert x['ok'] and marker in x['item']['content']
PY
  curl -fsS -b "$COOKIE" -H "Origin: $BASE" "$BASE/api.php?action=attachment_list&item_id=$ARTICLE_ID" > "${RUNNER_TEMP}/attachments-${FROM}-105.json"
  python3 - "${RUNNER_TEMP}/attachments-${FROM}-105.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['ok'] and len((x.get('data') or {}).get('items',[]))>=1
PY
  ( cd "$SITE" && php cli/verify.php ) > "${RUNNER_TEMP}/verify-${FROM}-105.json"
  python3 - "${RUNNER_TEMP}/verify-${FROM}-105.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['ok'] is True
PY
  DB_FILE="$(cd "$SITE" && php -r '$r=include "app/.runtime.php"; echo $r["db_file"];')"
  test "$(sqlite3 "$DB_FILE" 'PRAGMA integrity_check;')" = "ok"
  test -z "$(sqlite3 "$DB_FILE" 'PRAGMA foreign_key_check;')"

  kill "$PID"
  wait "$PID" 2>/dev/null || true
  echo "P02_V25115_DIRECT_UPGRADE_${FROM}=PASS"
}

run_upgrade "$ROOT/old81-src" "2.5.81" "18101"
run_upgrade "$ROOT/old82-src" "2.5.82" "18102"
run_upgrade "$ROOT/old102-src" "2.5.102" "18103"
run_upgrade "$ROOT/old103-src" "2.5.103" "18104"
run_upgrade "$ROOT/old104-src" "2.5.104" "18105"
run_upgrade "$ROOT/old105-src" "2.5.105" "18106"
run_upgrade "$ROOT/old111-src" "2.5.111" "18107"
run_upgrade "$ROOT/old112-src" "2.5.112" "18108"
run_upgrade "$ROOT/old113-src" "2.5.113" "18109"
run_upgrade "$ROOT/old114-src" "2.5.114" "18110"
echo P02_V25115_SOURCE_SET_MATRIX=PASS
