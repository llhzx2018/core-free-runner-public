#!/usr/bin/env bash
set -Eeuo pipefail
cd product

PRODUCT_REF="${PRODUCT_REF:?}"
VER=2.5.10
SRCVER=2.5.9
SCHEMA=2401
UPDATE_NAME="VF_Library_V2.5.10_UPDATE.zip"

test "$(git rev-parse HEAD)" = "$PRODUCT_REF"
test "$(tr -d '\r\n' < VERSION)" = "$VER"
test "$(jq -r .version SOURCE_MANIFEST.json)" = "$VER"
test "$(jq -r .schema SOURCE_MANIFEST.json)" = "$SCHEMA"
test "$(jq -r .runtime_source_file_count SOURCE_MANIFEST.json)" = 72
node --check public/assets/scratch-tabs.js
node --check public/assets/v254-common-branding.js
python3 scripts/repository-gates.py
git diff --check
echo EXACT_FORMAL_SOURCE_AND_PRIVACY_GATES=PASS

cp scripts/build-release-v2.5.4.py "$RUNNER_TEMP/build-v2510.py"
python3 - "$RUNNER_TEMP/build-v2510.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(encoding='utf-8')
old="ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.2'; VER='2.5.4'; SCHEMA=2401; DT=(2026,8,19,2,0,0)"
new="ROOT=Path.cwd(); SRCVER='2.5.9'; VER='2.5.10'; SCHEMA=2401; DT=(2026,8,19,7,0,0)"
assert old in s;s=s.replace(old,new,1)
s=s.replace("default='build/release-v2.5.4'","default='build/release-v2.5.10'").replace("default='release/v2.5.4'","default='release/v2.5.10'")
start="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''";end="''')\n arts=[sz,fz,uz,az,rf,notes]"
i=s.index(start);j=s.index(end,i)
notes="""notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''# VF Library V{VER}\n\nV2.5.10 refines Scratch Tabs UX/UI after the V2.5.9 Notepad-replacement layer entered real personal use.\n\n- Scratch workspace uses an immersive low-noise header while active.\n- The launcher is simplified from “临时 + count” to “临时 count”.\n- Tabs are denser and more Notepad-like; inactive close controls stay visually quiet.\n- The tab strip hides the horizontal scrollbar and supports wheel-based horizontal navigation.\n- Actions are condensed to 最近关闭 / 整理 / 返回 and autosave status to 已保存.\n- Typing updates only the active tab title instead of rebuilding the entire tab strip on every keystroke.\n- Candidate real-browser Run 32225789953 passed desktop/mobile UX/UI, multi-tab, autosave and Fresh Install gates.\n- Schema remains {SCHEMA}; no migration. Existing {SRCVER} sites use UPDATE.\n''')\n arts=[sz,fz,uz,az,rf,notes]"""
s=s[:i]+notes+s[j+len(end):]
s=s.replace("'candidate_browser':'PASS_RUN_32206056733_PLUS_32146866564'","'candidate_browser':'PASS_RUN_32225789953'")
s=s.replace("'main_readback':'PRODUCTION_2.5.2_CURRENT_EXPECTED_NOT_PROMOTED'","'main_readback':'PRODUCTION_2.5.9_OWNER_VISUAL_EVIDENCE'")
p.write_text(s,encoding='utf-8')
PY
python3 -m py_compile "$RUNNER_TEMP/build-v2510.py"
TREE=$(git show -s --format=%T "$PRODUCT_REF")
python3 "$RUNNER_TEMP/build-v2510.py" --out build/formal-a --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.10 >/tmp/p02-v2510-a.json
python3 "$RUNNER_TEMP/build-v2510.py" --out build/formal-b --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.10 >/tmp/p02-v2510-b.json
python3 - <<'PY'
from pathlib import Path
import hashlib
a=Path('build/formal-a');b=Path('build/formal-b')
ha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.iterdir() if p.is_file()};hb={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.is_file()}
assert ha==hb,(ha,hb)
req={'VF_Library_V2.5.10_UPDATE.zip','VF_Library_V2.5.10_FULL.zip','VF_Library_V2.5.10_ATOMIC.zip','VF_Library_V2.5.10_SOURCE.zip','repair-v2.5.10.php','VF_Library_V2.5.10_RELEASE_NOTES.md','VF_Library_V2.5.10_RELEASE_MANIFEST.json','SHA256SUMS.txt'}
assert req<=set(ha),set(ha)
print('DETERMINISTIC_FORMAL_BUILD=PASS')
for n,h in sorted(ha.items()):print(n,h)
PY
for z in "$UPDATE_NAME" "VF_Library_V2.5.10_FULL.zip" "VF_Library_V2.5.10_ATOMIC.zip";do unzip -t "build/formal-a/$z" >/dev/null;done
unzip -p "build/formal-a/$UPDATE_NAME" atomic-manifest.json | jq -e '.source_version=="2.5.9" and .target_version=="2.5.10" and .source_schema==2401 and .target_schema==2401' >/dev/null
echo FORMAL_ARCHIVE_AND_SOURCE_IDENTITY=PASS

# Fresh install + Scratch API smoke.
ROOT="$RUNNER_TEMP/fresh2510";SITE="$ROOT/site";mkdir -p "$SITE";unzip -q build/formal-a/VF_Library_V2.5.10_FULL.zip -d "$SITE"
test "$(cat "$SITE/VERSION.txt")" = 2.5.10
PW="P02-V2510-FRESH-${GITHUB_RUN_ID}!";PORT=18320
php -S 127.0.0.1:$PORT -t "$SITE" >/dev/null 2>&1 & PID=$!
for _ in $(seq 1 80);do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$ROOT/c" "http://127.0.0.1:$PORT/setup.php" > "$ROOT/setup"
TOKEN=$(python3 - "$ROOT/setup" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$ROOT/c" -c "$ROOT/c" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PW" --data-urlencode "password_confirm=$PW" "http://127.0.0.1:$PORT/setup.php")" = 303
SESSION=$(curl -fsS -b "$ROOT/c" "http://127.0.0.1:$PORT/api.php?action=session");CSRF=$(jq -r .csrf<<<"$SESSION")
NEW=$(curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d '{}' "http://127.0.0.1:$PORT/scratch-action.php?action=create");SID=$(jq -r .tab.id<<<"$NEW");test "$SID" -gt 0
curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d "$(jq -nc --argjson id "$SID" --arg c 'V2510 Fresh Scratch' '{id:$id,content:$c,cursor_pos:19,scroll_top:0}')" "http://127.0.0.1:$PORT/scratch-action.php?action=save" | jq -e '.tab.content=="V2510 Fresh Scratch"' >/dev/null
php "$SITE/cli/verify.php" | jq -e '.ok==true and .version=="2.5.10" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$PID";wait "$PID" 2>/dev/null||true
echo FULL_FRESH_INSTALL_AND_SCRATCH=PASS

# Existing data V2.5.9 -> V2.5.10, including pre-existing Scratch continuity.
ROOT="$RUNNER_TEMP/up259";SRC="$ROOT/src";SITE="$ROOT/site";mkdir -p "$ROOT"
git worktree add --detach "$SRC" v2.5.9 >/dev/null
mkdir -p "$SITE";bash "$SRC/scripts/build-deploy-tree.sh" "$SITE" >/dev/null
test "$(cat "$SITE/VERSION.txt")" = 2.5.9
PW="P02-V2510-UP-${GITHUB_RUN_ID}!";PORT=18321
php -S 127.0.0.1:$PORT -t "$SITE" >/dev/null 2>&1 & PID=$!
for _ in $(seq 1 80);do curl -fsS "http://127.0.0.1:$PORT/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$ROOT/c" "http://127.0.0.1:$PORT/setup.php" > "$ROOT/setup"
TOKEN=$(python3 - "$ROOT/setup" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$ROOT/c" -c "$ROOT/c" -H "Origin: http://127.0.0.1:$PORT" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PW" --data-urlencode "password_confirm=$PW" "http://127.0.0.1:$PORT/setup.php")" = 303
SESSION=$(curl -fsS -b "$ROOT/c" "http://127.0.0.1:$PORT/api.php?action=session");CSRF=$(jq -r .csrf<<<"$SESSION")
CAT=$(curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d '{"name":"V2510 Preserve","icon":"folder"}' "http://127.0.0.1:$PORT/api.php?action=category_save");CID=$(jq -r .id<<<"$CAT");test "$CID" -gt 0
ITEM=$(jq -nc --argjson cid "$CID" '{category_id:$cid,title:"V2510 Existing",content:"keep",content_mode:"article",content_format:"markdown",primary_action:"read",status:"active"}')
SAVED=$(curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d "$ITEM" "http://127.0.0.1:$PORT/api.php?action=content_save");IID=$(jq -r .id<<<"$SAVED");test "$IID" -gt 0
curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d "{\"id\":$IID,\"favorite\":true}" "http://127.0.0.1:$PORT/api.php?action=content_favorite" | jq -e .ok >/dev/null
SNEW=$(curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d '{}' "http://127.0.0.1:$PORT/scratch-action.php?action=create");SID=$(jq -r .tab.id<<<"$SNEW")
curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" -d "$(jq -nc --argjson id "$SID" --arg c '升级前临时页签 V2510' '{id:$id,content:$c,cursor_pos:10,scroll_top:7}')" "http://127.0.0.1:$PORT/scratch-action.php?action=save" | jq -e '.tab.content|contains("升级前临时页签")' >/dev/null
PKG="$(pwd)/build/formal-a/$UPDATE_NAME";BYTES=$(stat -c%s "$PKG");SHA=$(sha256sum "$PKG"|awk '{print $1}')
cat > "$ROOT/up.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$bytes=(int)$argv[3];$sha=$argv[4];$out=$argv[5];
require $site.'/app/bootstrap.php';require_once $site.'/app/CoreUpdates/UpdateAdapter.php';require_once $site.'/app/CoreUpdates/UpdateCore.php';require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=['schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,'current_version'=>'2.5.9','target_version'=>'2.5.10','update_type'=>'ATOMIC','from_versions'=>['2.5.9'],'schema_from'=>'2401','schema_to'=>'2401','repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.10','asset_name'=>'VF_Library_V2.5.10_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-08-19T07:00:00Z'];
$c=new CoreUpdates\UpdateCore('P02','APP');if(($c->check('2.5.9','2401',$m)['status']??'')!=='AVAILABLE')exit(2);if(($c->verifyPackage($pkg,$m)['status']??'')!=='VERIFIED')exit(3);$r=$c->upgrade('2.5.9','2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);file_put_contents($out,json_encode($r));if(!in_array($r['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($r['backup_locator']))exit(4);
PHP
php "$ROOT/up.php" "$SITE" "$PKG" "$BYTES" "$SHA" "$ROOT/result"
test "$(cat "$SITE/VERSION.txt")" = 2.5.10
jq -e '.backup_locator|length>0' "$ROOT/result" >/dev/null
curl -fsS -b "$ROOT/c" "http://127.0.0.1:$PORT/api.php?action=content_get&id=$IID" | jq -e '(.item.is_favorite|tonumber)==1 and .item.content=="keep"' >/dev/null
SESSION2=$(curl -fsS -b "$ROOT/c" "http://127.0.0.1:$PORT/api.php?action=session");jq -e '.site.auth==true'<<<"$SESSION2" >/dev/null;CSRF2=$(jq -r .csrf<<<"$SESSION2")
LIST=$(curl -fsS -b "$ROOT/c" "http://127.0.0.1:$PORT/scratch-action.php?action=list");jq -e --argjson id "$SID" '.data.open[]|select(.id==$id)|.content|contains("升级前临时页签")'<<<"$LIST" >/dev/null
POST=$(curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF2" -d '{}' "http://127.0.0.1:$PORT/scratch-action.php?action=create");POSTSID=$(jq -r .tab.id<<<"$POST")
curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF2" -d "$(jq -nc --argjson id "$POSTSID" --arg c '升级后临时页签 V2510' '{id:$id,content:$c,cursor_pos:10,scroll_top:0}')" "http://127.0.0.1:$PORT/scratch-action.php?action=save" | jq -e '.tab.content|contains("升级后临时页签")' >/dev/null
ORG=$(curl -fsS -b "$ROOT/c" -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF2" -d "$(jq -nc --argjson id "$POSTSID" --argjson cid "$CID" '{id:$id,title:"V2510 Scratch Organized",category_id:$cid,content_mode:"quick"}')" "http://127.0.0.1:$PORT/scratch-action.php?action=organize");OID=$(jq -r .item_id<<<"$ORG");test "$OID" -gt 0
curl -fsS -b "$ROOT/c" "http://127.0.0.1:$PORT/api.php?action=content_get&id=$OID" | jq -e '.item.title=="V2510 Scratch Organized" and (.item.content|contains("升级后临时页签"))' >/dev/null
php "$SITE/cli/verify.php" | jq -e '.ok==true and .version=="2.5.10" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
kill "$PID";wait "$PID" 2>/dev/null||true
echo EXISTING_DATA_2.5.9_TO_2.5.10=PASS
echo AUTOMATIC_BACKUP_DATA_FAVORITE_SESSION=PASS
echo PREEXISTING_SCRATCH_PRESERVED=PASS
echo POST_UPGRADE_SCRATCH_WRITE_AND_ORGANIZE=PASS

# Publish private formal release and remote readback.
export GH_TOKEN="$RELEASE_TOKEN"
if ! gh release view v2.5.10 --repo llhzx2018/vf-library >/dev/null 2>&1;then
  gh release create v2.5.10 build/formal-a/* --repo llhzx2018/vf-library --target "$PRODUCT_REF" --title 'VF Library V2.5.10' --notes-file build/formal-a/VF_Library_V2.5.10_RELEASE_NOTES.md
else
  gh release upload v2.5.10 build/formal-a/* --repo llhzx2018/vf-library --clobber
fi
gh release view v2.5.10 --repo llhzx2018/vf-library --json databaseId,tagName,isDraft,isPrerelease,publishedAt > "$RUNNER_TEMP/release2510.json"
jq -e '.tagName=="v2.5.10" and .isDraft==false and .isPrerelease==false' "$RUNNER_TEMP/release2510.json" >/dev/null
mkdir -p "$RUNNER_TEMP/readback2510";gh release download v2.5.10 --repo llhzx2018/vf-library --pattern "$UPDATE_NAME" --dir "$RUNNER_TEMP/readback2510"
RBYTES=$(stat -c%s "$RUNNER_TEMP/readback2510/$UPDATE_NAME");RSHA=$(sha256sum "$RUNNER_TEMP/readback2510/$UPDATE_NAME"|awk '{print $1}')
test "$RBYTES" = "$(stat -c%s build/formal-a/$UPDATE_NAME)"
test "$RSHA" = "$(sha256sum build/formal-a/$UPDATE_NAME|awk '{print $1}')"
TAGSHA=$(gh api repos/llhzx2018/vf-library/git/ref/tags/v2.5.10 --jq .object.sha);test "$TAGSHA" = "$PRODUCT_REF"
echo "RELEASE_ID=$(jq -r .databaseId "$RUNNER_TEMP/release2510.json")"
echo "PUBLISHED_AT=$(jq -r .publishedAt "$RUNNER_TEMP/release2510.json")"
echo "UPDATE_BYTES=$RBYTES"
echo "UPDATE_SHA256=$RSHA"
echo FORMAL_RELEASE_REMOTE_READBACK=PASS
echo PRODUCTION_WRITE=NO
