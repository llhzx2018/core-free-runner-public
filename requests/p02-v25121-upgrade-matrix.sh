#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$PWD"
PRODUCT="$ROOT/product"
TARGET="2.5.121"
SCHEMA="2401"
SOURCES=(2.5.81 2.5.82 2.5.102 2.5.103 2.5.104 2.5.105 2.5.111 2.5.112 2.5.113 2.5.114 2.5.115 2.5.116 2.5.117 2.5.118 2.5.119 2.5.120)
PKG="$PRODUCT/build/release-preflight/VF_Library_V${TARGET}_UPDATE.zip"

test -f "$PKG"
BYTES="$(stat -c%s "$PKG")"
SHA="$(sha256sum "$PKG" | awk '{print $1}')"
SOURCE_JSON="$(printf '%s\n' "${SOURCES[@]}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"

cleanup_pids=()
cleanup(){
  for pid in "${cleanup_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT

run_one(){
  local FROM="$1"
  local INDEX="$2"
  local SRC="$RUNNER_TEMP/p02-v25121-src-${FROM}"
  local SITE="$RUNNER_TEMP/p02-v25121-site-${FROM}"
  local COOKIE="$RUNNER_TEMP/p02-v25121-cookie-${FROM}.txt"
  local PORT="$((18400 + INDEX))"
  local BASE="http://127.0.0.1:${PORT}"
  local PASS="P02-V25121-UP-${FROM}-${GITHUB_RUN_ID}!"
  local LOG="$RUNNER_TEMP/p02-v25121-${FROM}.log"

  echo "=== DIRECT UPGRADE ${FROM} -> ${TARGET} ==="
  rm -rf "$SRC" "$SITE" "$COOKIE"
  git -C "$PRODUCT" tag -l "v${FROM}" | grep -qx "v${FROM}"
  git -C "$PRODUCT" worktree add --detach "$SRC" "v${FROM}" >/dev/null
  bash "$SRC/scripts/build-deploy-tree.sh" "$SITE" >/dev/null
  test "$(cat "$SITE/VERSION.txt")" = "$FROM"

  php -d display_errors=0 -S "127.0.0.1:${PORT}" -t "$SITE" >"$LOG" 2>&1 &
  local PID=$!
  cleanup_pids+=("$PID")
  for _ in $(seq 1 80); do
    curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break
    sleep .25
  done
  kill -0 "$PID"

  curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/setup-${FROM}.html"
  local SETUP_CSRF
  SETUP_CSRF="$(python3 - "$RUNNER_TEMP/setup-${FROM}.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
assert m
print(html.unescape(m.group(1)))
PY
)"
  local STATUS
  STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE"     --data-urlencode "setup_csrf=$SETUP_CSRF" --data-urlencode "password=$PASS"     --data-urlencode "password_confirm=$PASS" "$BASE/setup.php")"
  test "$STATUS" = "303"

  local SESSION CSRF
  SESSION="$(curl -fsS -b "$COOKIE" "$BASE/api.php?action=session")"
  CSRF="$(jq -r .csrf <<<"$SESSION")"
  jq -e --arg v "$FROM" '.ok==true and .site.auth==true and .version==$v' <<<"$SESSION" >/dev/null

  local CAT CID
  CAT="$(curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF"     -d '{"name":"V25121 Direct Upgrade","description":"release matrix fixture","icon":"folder"}'     "$BASE/api.php?action=category_save")"
  CID="$(jq -r .id <<<"$CAT")"
  test "$CID" -gt 0

  local ITEM SAVED IID
  ITEM="$(jq -nc --argjson cid "$CID" --arg f "$FROM" '{category_id:$cid,title:("V25121 Upgrade "+$f),description:"preserve",content:("P02_V25121_MARKER_"+($f|gsub("\\.";"_"))+"\n中文资料\n"+("DATA\n"*80)),content_mode:"article",content_format:"markdown",primary_action:"read",status:"active"}')"
  SAVED="$(curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF"     -d "$ITEM" "$BASE/api.php?action=content_save")"
  IID="$(jq -r .id <<<"$SAVED")"
  test "$IID" -gt 0

  curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF"     -d "$(jq -nc --argjson id "$IID" '{id:$id,favorite:true}')"     "$BASE/api.php?action=content_favorite" | jq -e '.ok==true' >/dev/null

  local SNEW SID
  SNEW="$(curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF"     -d '{}' "$BASE/scratch-action.php?action=create")"
  SID="$(jq -r .tab.id <<<"$SNEW")"
  test "$SID" -gt 0
  curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF"     -d "$(jq -nc --argjson id "$SID" --arg c "升级前临时页签 ${FROM}" '{id:$id,content:$c,cursor_pos:10,scroll_top:7}')"     "$BASE/scratch-action.php?action=save" | jq -e '.tab.content|contains("升级前临时页签")' >/dev/null

  python3 - "$RUNNER_TEMP/p02-v25121-${FROM}.png" <<'PY'
import base64,sys
open(sys.argv[1],'wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZfGQAAAAASUVORK5CYII='))
PY
  curl -fsS -b "$COOKIE" -H "X-CSRF-Token: $CSRF"     -F "item_id=$IID" -F "attachment=@$RUNNER_TEMP/p02-v25121-${FROM}.png;type=image/png"     "$BASE/api.php?action=attachment_upload" | jq -e '.ok==true and (.attachments|length)>=1' >/dev/null

  cat > "$RUNNER_TEMP/p02-v25121-up-${FROM}.php" <<'PHP'
<?php
$site=$argv[1];
$pkg=$argv[2];
$bytes=(int)$argv[3];
$sha=$argv[4];
$from=$argv[5];
$target=$argv[6];
$sources=json_decode($argv[7],true,512,JSON_THROW_ON_ERROR);
$out=$argv[8];
require $site.'/app/bootstrap.php';
require_once $site.'/app/CoreUpdates/UpdateAdapter.php';
require_once $site.'/app/CoreUpdates/UpdateCore.php';
require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=[
 'schema_version'=>'1.0',
 'project_id'=>'P02',
 'component_id'=>'APP',
 'enabled'=>true,
 'current_version'=>$from,
 'target_version'=>$target,
 'update_type'=>'ATOMIC',
 'from_versions'=>$sources,
 'schema_from'=>'2401',
 'schema_to'=>'2401',
 'repository'=>'llhzx2018/vf-library',
 'release_tag'=>'v'.$target,
 'asset_name'=>'VF_Library_V'.$target.'_UPDATE.zip',
 'asset_bytes'=>$bytes,
 'asset_sha256'=>$sha,
 'backup_required'=>true,
 'rollback_supported'=>true,
 'released_at'=>'2026-09-25T00:00:00Z'
];
$c=new CoreUpdates\UpdateCore('P02','APP');
$check=$c->check($from,'2401',$m);
if(($check['status']??'')!=='AVAILABLE'){file_put_contents($out,json_encode(['check'=>$check]));exit(2);}
$verify=$c->verifyPackage($pkg,$m);
if(($verify['status']??'')!=='VERIFIED'){file_put_contents($out,json_encode(['verify'=>$verify]));exit(3);}
$r=$c->upgrade($from,'2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);
file_put_contents($out,json_encode($r));
if(!in_array($r['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($r['backup_locator']))exit(4);
PHP

  php "$RUNNER_TEMP/p02-v25121-up-${FROM}.php" "$SITE" "$PKG" "$BYTES" "$SHA" "$FROM" "$TARGET" "$SOURCE_JSON" "$RUNNER_TEMP/p02-v25121-result-${FROM}.json"
  test "$(cat "$SITE/VERSION.txt")" = "$TARGET"
  jq -e '.backup_locator|length>0' "$RUNNER_TEMP/p02-v25121-result-${FROM}.json" >/dev/null

  local AFTER CSRF2
  AFTER="$(curl -fsS -b "$COOKIE" "$BASE/api.php?action=session")"
  CSRF2="$(jq -r .csrf <<<"$AFTER")"
  jq -e --arg v "$TARGET" '.ok==true and .site.auth==true and .version==$v' <<<"$AFTER" >/dev/null

  curl -fsS -b "$COOKIE" "$BASE/api.php?action=content_get&id=$IID" |     jq -e --arg f "$FROM" '(.item.is_favorite|tonumber)==1 and (.item.content|contains("P02_V25121_MARKER_"+($f|gsub("\\.";"_"))))' >/dev/null

  curl -fsS -b "$COOKIE" "$BASE/scratch-action.php?action=list" |     jq -e --argjson id "$SID" '.data.open[]|select(.id==$id)|.content|contains("升级前临时页签")' >/dev/null

  curl -fsS -b "$COOKIE" "$BASE/api.php?action=attachment_list&item_id=$IID" |     jq -e '(.data.items|length)>=1' >/dev/null

  local POST POSTID
  POST="$(curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF2"     -d '{}' "$BASE/scratch-action.php?action=create")"
  POSTID="$(jq -r .tab.id <<<"$POST")"
  test "$POSTID" -gt 0
  curl -fsS -b "$COOKIE" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF2"     -d "$(jq -nc --argjson id "$POSTID" --arg c "升级后临时页签 ${FROM}" '{id:$id,content:$c,cursor_pos:10,scroll_top:0}')"     "$BASE/scratch-action.php?action=save" | jq -e '.tab.content|contains("升级后临时页签")' >/dev/null

  (cd "$SITE" && php cli/verify.php) | jq -e '.ok==true and .version=="2.5.121" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
  local DB_FILE
  DB_FILE="$(cd "$SITE" && php -r '$r=include "app/.runtime.php"; echo $r["db_file"];')"
  test "$(sqlite3 "$DB_FILE" 'PRAGMA integrity_check;')" = "ok"
  test -z "$(sqlite3 "$DB_FILE" 'PRAGMA foreign_key_check;')"

  kill "$PID"
  wait "$PID" 2>/dev/null || true
  cleanup_pids=("${cleanup_pids[@]/$PID}")
  git -C "$PRODUCT" worktree remove --force "$SRC" >/dev/null
  rm -rf "$SITE"

  echo "P02_V25121_DIRECT_UPGRADE_${FROM}=PASS"
}

index=1
for from in "${SOURCES[@]}"; do
  run_one "$from" "$index"
  index=$((index+1))
done

echo P02_V25121_SOURCE_SET_MATRIX=PASS
