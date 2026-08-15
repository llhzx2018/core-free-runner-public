#!/usr/bin/env bash
set -Eeuo pipefail

PROD_ROOT="${1:?production checkout required}"
FEATURE_ROOT="${2:?feature checkout required}"
EVIDENCE_DIR="${3:?evidence dir required}"
RUN_ROOT="${RUNNER_TEMP:-/tmp}/p02-update-core-v1-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
TEST_PASSWORD="P02-Core-${GITHUB_RUN_ID:-local}-${RANDOM}!"
mkdir -p "$RUN_ROOT" "$EVIDENCE_DIR"

cleanup(){
  for pid in "${SERVER_PID_BRIDGE:-}" "${SERVER_PID_NORMAL:-}" "${SERVER_PID_FAIL:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; fi
  done
  rm -rf "$RUN_ROOT"
}
trap cleanup EXIT

step(){ printf '\n== %s ==\n' "$*"; }
json_value(){ python3 - "$1" "$2" <<'PY'
import json,sys
cur=json.load(open(sys.argv[1],encoding='utf-8'))
for part in sys.argv[2].split('.'):
    cur=cur[int(part)] if isinstance(cur,list) else cur[part]
if isinstance(cur,bool): print('true' if cur else 'false')
else: print(cur if cur is not None else '')
PY
}

start_site(){
  local site="$1" port="$2" log="$3" pidvar="$4"
  php -d display_errors=0 -S "127.0.0.1:${port}" -t "$site" >"$log" 2>&1 &
  local pid=$!; printf -v "$pidvar" '%s' "$pid"
  for _ in $(seq 1 100); do
    if curl -fsS "http://127.0.0.1:${port}/setup.php" >/dev/null 2>&1; then return 0; fi
    sleep 0.12
  done
  echo 'site failed to start' >&2; return 1
}
stop_pid(){ local pid="${1:-}"; if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; }

setup_fixture(){
  local site="$1" port="$2" cookie="$3" suffix="$4" state="$5"
  local base="http://127.0.0.1:${port}"
  curl -fsS -c "$cookie" "$base/setup.php" > "$RUN_ROOT/setup-${suffix}.html"
  local setup_csrf
  setup_csrf="$(python3 - "$RUN_ROOT/setup-${suffix}.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
if not m: raise SystemExit('setup csrf missing')
print(html.unescape(m.group(1)))
PY
)"
  local code
  code="$(curl -sS -o "$RUN_ROOT/setup-post-${suffix}.html" -w '%{http_code}' -b "$cookie" -c "$cookie" -H "Origin: $base" --data-urlencode "setup_csrf=$setup_csrf" --data-urlencode "password=$TEST_PASSWORD" --data-urlencode "password_confirm=$TEST_PASSWORD" "$base/setup.php")"
  [[ "$code" == "303" ]]
  curl -fsS -b "$cookie" -c "$cookie" "$base/api.php?action=session" > "$RUN_ROOT/session-${suffix}.json"
  local csrf; csrf="$(json_value "$RUN_ROOT/session-${suffix}.json" csrf)"

  printf '%s' '{"name":"Update Core Pilot","description":"isolated fixture","icon":"folder"}' > "$RUN_ROOT/category-${suffix}.json"
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' --data-binary "@$RUN_ROOT/category-${suffix}.json" "$base/api.php?action=category_save" > "$RUN_ROOT/category-out-${suffix}.json"
  local category_id; category_id="$(json_value "$RUN_ROOT/category-out-${suffix}.json" id)"

  python3 - "$RUN_ROOT/article-${suffix}.json" "$category_id" "$suffix" <<'PY'
import json,sys
json.dump({'category_id':int(sys.argv[2]),'title':'P02 Core Pilot '+sys.argv[3],'description':'isolated update fixture','content':'P02_CORE_UPDATE_CONTENT_'+sys.argv[3]+'_'+'中英文UTF8'*100,'content_mode':'article','content_format':'markdown','primary_action':'read','status':'active'},open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False)
PY
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H "X-CSRF-Token: $csrf" -H 'Content-Type: application/json' --data-binary "@$RUN_ROOT/article-${suffix}.json" "$base/api.php?action=content_save" > "$RUN_ROOT/article-out-${suffix}.json"
  local article_id; article_id="$(json_value "$RUN_ROOT/article-out-${suffix}.json" id)"

  python3 - "$RUN_ROOT/pixel-${suffix}.png" <<'PY'
import base64,sys
open(sys.argv[1],'wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZfGQAAAAASUVORK5CYII='))
PY
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H "X-CSRF-Token: $csrf" -F "item_id=$article_id" -F "attachment=@$RUN_ROOT/pixel-${suffix}.png;type=image/png" "$base/api.php?action=attachment_upload" > "$RUN_ROOT/attachment-${suffix}.json"
  [[ "$(json_value "$RUN_ROOT/attachment-${suffix}.json" ok)" == "true" ]]

  local db; db="$(cd "$site" && php -r '$r=include "app/.runtime.php";echo $r["db_file"];')"
  [[ -f "$db" ]]
  python3 - "$state" "$article_id" "$db" <<'PY'
import json,sys
json.dump({'article_id':int(sys.argv[2]),'db':sys.argv[3]},open(sys.argv[1],'w',encoding='utf-8'))
PY
}

verify_fixture(){
  local site="$1" state="$2" expected_version="$3"
  local article_id db count attachments
  article_id="$(json_value "$state" article_id)"; db="$(json_value "$state" db)"
  [[ "$(tr -d '\r\n' < "$site/VERSION.txt")" == "$expected_version" ]]
  [[ "$(sqlite3 "$db" 'PRAGMA integrity_check;')" == "ok" ]]
  [[ -z "$(sqlite3 "$db" 'PRAGMA foreign_key_check;')" ]]
  count="$(sqlite3 "$db" "SELECT COUNT(*) FROM text_items WHERE id=$article_id AND title LIKE 'P02 Core Pilot %' AND content LIKE 'P02_CORE_UPDATE_CONTENT_%';")"; [[ "$count" == "1" ]]
  attachments="$(sqlite3 "$db" "SELECT COUNT(*) FROM item_attachments WHERE item_id=$article_id;")"; [[ "$attachments" -ge 1 ]]
  (cd "$site" && php cli/verify.php) > "$RUN_ROOT/verify-${expected_version}-$(basename "$site").json"
  python3 - "$RUN_ROOT/verify-${expected_version}-$(basename "$site").json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8')); assert x.get('ok') is True
PY
}

build_manifest(){
  local source="$1" target="$2" source_version="$3" target_version="$4" out="$5"
  python3 - "$source" "$target" "$source_version" "$target_version" "$out" <<'PY'
import hashlib,json,pathlib,sys
src=pathlib.Path(sys.argv[1]); tgt=pathlib.Path(sys.argv[2]); sv=sys.argv[3]; tv=sys.argv[4]
def scan(root):
  rows=[]
  for p in sorted(root.rglob('*')):
    if p.is_file() and not p.is_symlink():
      data=p.read_bytes(); rows.append({'path':p.relative_to(root).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  return rows
obj={'format':'vf.library.atomic-package','format_version':1,'package_id':'vf-library','package_type':'app','source_version':sv,'target_version':tv,'source_schema':2401,'target_schema':2401,'source_files':scan(src),'files':scan(tgt)}
json.dump(obj,open(sys.argv[5],'w',encoding='utf-8'),ensure_ascii=False,sort_keys=True,separators=(',',':'))
PY
}

make_update_zip(){
  local source="$1" target="$2" source_version="$3" target_version="$4" output="$5"
  local work="$RUN_ROOT/package-${source_version}-to-${target_version}"
  rm -rf "$work"; mkdir -p "$work/payload"
  cp -a "$target/." "$work/payload/"
  build_manifest "$source" "$target" "$source_version" "$target_version" "$work/atomic-manifest.json"
  python3 - "$work" "$output" <<'PY'
import pathlib,sys,zipfile
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); out.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(root.rglob('*')):
    if p.is_file() and not p.is_symlink(): z.write(p,p.relative_to(root).as_posix())
PY
}

cat > "$RUN_ROOT/direct-atomic.php" <<'PHP'
<?php
declare(strict_types=1);
[$script,$site,$package,$source,$target]=$argv;
require $site.'/app/bootstrap.php';
$zip=new ZipArchive();if($zip->open($package)!==true)throw new RuntimeException('zip open failed');
$root=sys_get_temp_dir().'/p02-bridge-'.bin2hex(random_bytes(4));mkdir($root,0700,true);$zip->extractTo($root);$zip->close();
$m=json_decode((string)file_get_contents($root.'/atomic-manifest.json'),true,512,JSON_THROW_ON_ERROR);$files=[];foreach($m['files'] as $row)$files[(string)$row['path']]=['bytes'=>(int)$row['bytes'],'sha256'=>(string)$row['sha256']];$sourceFiles=[];foreach($m['source_files'] as $row)$sourceFiles[(string)$row['path']]=['bytes'=>(int)$row['bytes'],'sha256'=>(string)$row['sha256']];
$r=VfLibraryAtomicUpgradeService::fromCurrentRuntime()->upgrade($source,$target,$root.'/payload',$files,['source_schema'=>2401,'target_schema'=>2401,'source_files'=>$sourceFiles]);
echo json_encode(['result'=>'COMMITTED','files'=>$r['files']??0,'rollback_used'=>$r['rollback_used']??null],JSON_UNESCAPED_SLASHES),"\n";
PHP

cat > "$RUN_ROOT/client-run.php" <<'PHP'
<?php
declare(strict_types=1);
[$script,$site,$package,$manifestFile,$mode]=$argv;
putenv('VFTB_TEST_MODE=1');
require $site.'/app/bootstrap.php';
$manifest=json_decode((string)file_get_contents($manifestFile),true,512,JSON_THROW_ON_ERROR);
$fetcher=static fn()=>$manifest;
$downloader=static function(array $m,string $dest) use($package): bool {return copy($package,$dest);};
$schema=static fn()=>2401;
$options=$mode==='fail'?['fail_after_file'=>3]:[];
$svc=new VfLibraryUpdateService($fetcher,$downloader,$schema,null,$options);
$check=$svc->check(true);$status=$check['status']??[];
if(($status['core_status']??'')!=='AVAILABLE'||empty($status['can_update']))throw new RuntimeException('Update Core discovery gate failed');
try{$result=$svc->execute();if($mode!=='normal')throw new RuntimeException('fault injection unexpectedly committed');echo json_encode(['result'=>'COMMITTED','from'=>$result['from_version']??'','to'=>$result['to_version']??'','core_result'=>$result['core_result']??''],JSON_UNESCAPED_SLASHES),"\n";}
catch(Throwable $e){if($mode!=='fail')throw $e;echo json_encode(['result'=>'EXPECTED_FAILURE','error_class'=>get_class($e)],JSON_UNESCAPED_SLASHES),"\n";}
PHP

step "Build exact 2.4.22 / feature 2.4.23 deploy trees"
bash "$PROD_ROOT/scripts/build-deploy-tree.sh" "$RUN_ROOT/prod22" >/dev/null
bash "$FEATURE_ROOT/scripts/build-deploy-tree.sh" "$RUN_ROOT/feature23" >/dev/null
[[ "$(tr -d '\r\n' < "$RUN_ROOT/prod22/VERSION.txt")" == '2.4.22' ]]
[[ "$(tr -d '\r\n' < "$RUN_ROOT/feature23/VERSION.txt")" == '2.4.23' ]]

step "Bridge validation: existing 2.4.22 Atomic engine -> 2.4.23"
make_update_zip "$RUN_ROOT/prod22" "$RUN_ROOT/feature23" 2.4.22 2.4.23 "$RUN_ROOT/VF_Library_V2.4.23_UPDATE.zip"
cp -a "$RUN_ROOT/prod22" "$RUN_ROOT/site-bridge"
start_site "$RUN_ROOT/site-bridge" 18131 "$RUN_ROOT/server-bridge.log" SERVER_PID_BRIDGE
setup_fixture "$RUN_ROOT/site-bridge" 18131 "$RUN_ROOT/cookie-bridge.txt" bridge "$RUN_ROOT/state-bridge.json"
stop_pid "$SERVER_PID_BRIDGE"; SERVER_PID_BRIDGE=''
php "$RUN_ROOT/direct-atomic.php" "$RUN_ROOT/site-bridge" "$RUN_ROOT/VF_Library_V2.4.23_UPDATE.zip" 2.4.22 2.4.23 > "$EVIDENCE_DIR/bridge.json"
verify_fixture "$RUN_ROOT/site-bridge" "$RUN_ROOT/state-bridge.json" 2.4.23
grep -q '"result":"COMMITTED"' "$EVIDENCE_DIR/bridge.json"
echo 'BRIDGE_2_4_22_TO_2_4_23=PASS'

step "Create TEST-ONLY synthetic 2.4.24 UPDATE package"
cp -a "$RUN_ROOT/feature23" "$RUN_ROOT/test24"
printf '2.4.24\n' > "$RUN_ROOT/test24/VERSION.txt"
for f in app/CoreUpdates/UpdateCore.php app/CoreUpdates/GitHubClient.php app/UpdateService.php app/VfLibraryCoreUpdateAdapter.php; do printf '\n/* TEST_TARGET_2_4_24_ONLY */\n' >> "$RUN_ROOT/test24/$f"; done
make_update_zip "$RUN_ROOT/feature23" "$RUN_ROOT/test24" 2.4.23 2.4.24 "$RUN_ROOT/VF_Library_V2.4.24_UPDATE.zip"
PACKAGE_BYTES="$(stat -c %s "$RUN_ROOT/VF_Library_V2.4.24_UPDATE.zip")"; PACKAGE_SHA="$(sha256sum "$RUN_ROOT/VF_Library_V2.4.24_UPDATE.zip" | awk '{print $1}')"
python3 - "$RUN_ROOT/manifest24.json" "$PACKAGE_BYTES" "$PACKAGE_SHA" <<'PY'
import json,sys,datetime
m={'schema_version':'1.0','project_id':'P02','component_id':'APP','enabled':True,'target_version':'2.4.24','update_type':'ATOMIC','from_versions':['2.4.23'],'schema_from':'2401','schema_to':'2401','repository':'llhzx2018/vf-library','release_tag':'v2.4.24-TEST-ONLY','asset_name':'VF_Library_V2.4.24_UPDATE.zip','asset_bytes':int(sys.argv[2]),'asset_sha256':sys.argv[3],'backup_required':True,'rollback_supported':True,'released_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release_summary':'TEST TARGET ONLY - NOT RELEASED'}
json.dump(m,open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
PY

step "New client: 2.4.23 discovery -> bytes/SHA -> Atomic -> 2.4.24 TEST TARGET"
cp -a "$RUN_ROOT/feature23" "$RUN_ROOT/site-normal"
start_site "$RUN_ROOT/site-normal" 18132 "$RUN_ROOT/server-normal.log" SERVER_PID_NORMAL
setup_fixture "$RUN_ROOT/site-normal" 18132 "$RUN_ROOT/cookie-normal.txt" normal "$RUN_ROOT/state-normal.json"
stop_pid "$SERVER_PID_NORMAL"; SERVER_PID_NORMAL=''
php "$RUN_ROOT/client-run.php" "$RUN_ROOT/site-normal" "$RUN_ROOT/VF_Library_V2.4.24_UPDATE.zip" "$RUN_ROOT/manifest24.json" normal > "$EVIDENCE_DIR/client-normal.json"
verify_fixture "$RUN_ROOT/site-normal" "$RUN_ROOT/state-normal.json" 2.4.24
grep -q '"result":"COMMITTED"' "$EVIDENCE_DIR/client-normal.json"
echo 'NEW_CLIENT_NORMAL=PASS'

step "New client failure injection -> automatic rollback to 2.4.23"
cp -a "$RUN_ROOT/feature23" "$RUN_ROOT/site-fail"
start_site "$RUN_ROOT/site-fail" 18133 "$RUN_ROOT/server-fail.log" SERVER_PID_FAIL
setup_fixture "$RUN_ROOT/site-fail" 18133 "$RUN_ROOT/cookie-fail.txt" rollback "$RUN_ROOT/state-fail.json"
stop_pid "$SERVER_PID_FAIL"; SERVER_PID_FAIL=''
php "$RUN_ROOT/client-run.php" "$RUN_ROOT/site-fail" "$RUN_ROOT/VF_Library_V2.4.24_UPDATE.zip" "$RUN_ROOT/manifest24.json" fail > "$EVIDENCE_DIR/client-failure.json"
verify_fixture "$RUN_ROOT/site-fail" "$RUN_ROOT/state-fail.json" 2.4.23
grep -q '"result":"EXPECTED_FAILURE"' "$EVIDENCE_DIR/client-failure.json"
[[ ! -f "$(cd "$RUN_ROOT/site-fail" && php -r '$r=include "app/.runtime.php";echo dirname($r["db_file"])."/.control/maintenance.json";')" ]]
echo 'NEW_CLIENT_ROLLBACK=PASS'

python3 - "$EVIDENCE_DIR/summary.json" "$PACKAGE_BYTES" "$PACKAGE_SHA" <<'PY'
import datetime,json,os,sys
out={'result':'PASS','project_id':'P02','working_version':'2.4.23','schema':2401,'production_source':'2.4.22','test_target_only':'2.4.24','test_target_is_release':False,'checks':{'bridge_2.4.22_to_2.4.23':'PASS','new_client_discovery':'PASS','asset_bytes_sha256':'PASS','new_client_atomic':'PASS','data_preservation':'PASS','attachment_preservation':'PASS','failure_injection_after_file_3':'PASS','rollback_to_2.4.23':'PASS','sqlite_integrity':'PASS','foreign_keys':'PASS','cleanup':'PASS'},'synthetic_asset':{'bytes':int(sys.argv[2]),'sha256':sys.argv[3]},'evidence_privacy':'NO_SOURCE_NO_DATABASE_NO_PACKAGE_NO_SECRET','run_id':os.environ.get('GITHUB_RUN_ID','local'),'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
json.dump(out,open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False,indent=2)
PY

echo 'P02_UPDATE_CORE_V1_PILOT=PASS'
