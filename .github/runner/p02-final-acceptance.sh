#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT="${GITHUB_WORKSPACE:?}/product"
RUN_ROOT="${RUNNER_TEMP:?}/p02-final-acceptance"
EVIDENCE="$RUN_ROOT/evidence"
SOURCE31="$RUN_ROOT/source31"
SITE31="$RUN_ROOT/site31"
PORT=18160
BASE="http://127.0.0.1:$PORT"
PASSWORD="VF-FINAL-${GITHUB_RUN_ID:-local}!"
mkdir -p "$RUN_ROOT" "$EVIDENCE"

cleanup(){
  if [[ -n "${PHP_PID:-}" ]] && kill -0 "$PHP_PID" 2>/dev/null; then kill "$PHP_PID" 2>/dev/null || true; fi
  if [[ -d "$SOURCE31/.git" || -f "$SOURCE31/.git" ]]; then git -C "$PRODUCT" worktree remove --force "$SOURCE31" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

step(){ printf '\n===== %s =====\n' "$*" | tee -a "$EVIDENCE/final-acceptance.log"; }
json_value(){ python3 - "$1" "$2" <<'PY'
import json,sys
cur=json.load(open(sys.argv[1],encoding='utf-8'))
for part in sys.argv[2].split('.'): cur=cur[int(part)] if isinstance(cur,list) else cur[part]
print(cur if cur is not None else '')
PY
}
assert_json_true(){ python3 - "$1" "$2" <<'PY'
import json,sys
cur=json.load(open(sys.argv[1],encoding='utf-8'))
for part in sys.argv[2].split('.'): cur=cur[int(part)] if isinstance(cur,list) else cur[part]
assert cur is True,(sys.argv[2],cur)
PY
}
api_post(){
  local action="$1" payload="$2" out="$3" status
  status="$(curl -sS -o "$out" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' --data-binary "@$payload" "$BASE/api.php?action=$action")"
  [[ "$status" -ge 200 && "$status" -lt 300 ]] || { echo "API $action failed HTTP $status" >&2; cat "$out" >&2; return 1; }
  assert_json_true "$out" ok
}

step "Exact candidate authority"
cd "$PRODUCT"
[[ "$(git rev-parse HEAD)" == "e0bac8f6ec30df94e626e07821ae3c39cbcd7f59" ]]
[[ "$(tr -d '\r\n' < VERSION)" == "2.5.32" ]]
[[ "$(git status --porcelain)" == "" ]]
python3 scripts/verify-source-manifest.py
bash scripts/verify-repository.sh
node - <<'JS'
const fs=require('fs');const c=JSON.parse(fs.readFileSync('docs/authority/P02_DEVELOP_CANDIDATE_IDENTITY.json','utf8'));
if(c.next_gate!=='FINAL_PRODUCT_ACCEPTANCE'||c.runtime_source_file_count!==67)process.exit(41);
if(!c.convergence.favicon_domain_semantic_module||!c.convergence.library_model_core_native||!c.convergence.scratch_runtime_static_entry)process.exit(42);
JS
echo P02_FINAL_AUTHORITY=PASS

step "All unit contracts"
for t in tests/unit/*.mjs; do echo "UNIT $t"; node "$t"; done
echo P02_FINAL_ALL_UNIT=PASS

step "All integration contracts"
for t in tests/integration/*.php; do echo "INTEGRATION PHP $t"; php "$t"; done
for t in tests/integration/*.sh; do echo "INTEGRATION SH $t"; bash "$t"; done
echo P02_FINAL_ALL_INTEGRATION=PASS

step "Full maintenance / fresh install / browser / SQLite"
EVIDENCE_DIR="$EVIDENCE/maintenance" VF_TEST_PORT=18161 bash scripts/maintenance-reverify.sh
python3 - "$EVIDENCE/maintenance/summary.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'));assert x.get('ok') is True
PY
echo P02_FINAL_MAINTENANCE=PASS

step "Deterministic 2.5.31 -> 2.5.32 candidate packaging"
rm -rf build/final-accept-a build/final-accept-b
python3 scripts/build-candidate.py --out build/final-accept-a --source-version 2.5.31 --source-commit "$(git rev-parse HEAD)" --source-tree "$(git show -s --format=%T HEAD)" --source-ref develop > "$EVIDENCE/candidate-a.json"
python3 scripts/build-candidate.py --out build/final-accept-b --source-version 2.5.31 --source-commit "$(git rev-parse HEAD)" --source-tree "$(git show -s --format=%T HEAD)" --source-ref develop > "$EVIDENCE/candidate-b.json"
python3 - <<'PY'
from pathlib import Path
import hashlib
A=Path('build/final-accept-a');B=Path('build/final-accept-b')
a=sorted(p.name for p in A.iterdir() if p.is_file());b=sorted(p.name for p in B.iterdir() if p.is_file());assert a==b,(a,b)
for name in a:
    x=hashlib.sha256((A/name).read_bytes()).hexdigest();y=hashlib.sha256((B/name).read_bytes()).hexdigest();assert x==y,(name,x,y)
print('P02_FINAL_DETERMINISTIC_PACKAGING=PASS')
PY
cp build/final-accept-a/SHA256SUMS.txt "$EVIDENCE/SHA256SUMS.txt"

step "Assemble real V2.5.31 carrier"
git worktree add --detach "$SOURCE31" v2.5.31-rc.1
[[ "$(tr -d '\r\n' < "$SOURCE31/VERSION")" == "2.5.31" ]]
bash "$SOURCE31/scripts/build-deploy-tree.sh" "$SITE31"
[[ "$(tr -d '\r\n' < "$SITE31/VERSION.txt")" == "2.5.31" ]]
for old in navigation-refresh-policy.js update-core-ui.js v2520-draft-retirement.js v2521-context-ux.js v254-common-branding.js v255-hotfix.js; do [[ -f "$SITE31/assets/$old" ]] || { echo "Expected carrier legacy asset missing: $old" >&2; exit 51; }; done
echo P02_FINAL_251_CARRIER=PASS

step "Install and seed V2.5.31 with private data"
php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE31" > "$EVIDENCE/upgrade-php.log" 2>&1 & PHP_PID=$!
for _ in $(seq 1 80); do curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break; sleep .25; done
kill -0 "$PHP_PID"
COOKIE="$RUN_ROOT/cookie.txt"
curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUN_ROOT/setup.html"
SETUP_CSRF="$(python3 - "$RUN_ROOT/setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)"
STATUS="$(curl -sS -o "$RUN_ROOT/setup-post.html" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" --data-urlencode "setup_csrf=$SETUP_CSRF" --data-urlencode "password=$PASSWORD" --data-urlencode "password_confirm=$PASSWORD" "$BASE/setup.php")"
[[ "$STATUS" == 303 ]]
curl -fsS -b "$COOKIE" -c "$COOKIE" "$BASE/api.php?action=session" > "$RUN_ROOT/session31.json"
assert_json_true "$RUN_ROOT/session31.json" ok
assert_json_true "$RUN_ROOT/session31.json" site.auth
[[ "$(json_value "$RUN_ROOT/session31.json" version)" == "2.5.31" ]]
CSRF="$(json_value "$RUN_ROOT/session31.json" csrf)"

printf '%s' '{"name":"Final Acceptance","description":"2.5.31 to 2.5.32 preservation fixture","icon":"folder"}' > "$RUN_ROOT/category.json"
api_post category_save "$RUN_ROOT/category.json" "$RUN_ROOT/category-out.json"
CATEGORY_ID="$(json_value "$RUN_ROOT/category-out.json" id)"
python3 - "$RUN_ROOT/article.json" "$CATEGORY_ID" <<'PY'
import json,sys
body='# Final Acceptance Preservation\n\n'+('Private preservation marker 中文 English 2.5.31→2.5.32.\n'*240)
json.dump({'category_id':int(sys.argv[2]),'title':'Upgrade Preservation Article','description':'must survive atomic upgrade','content':body,'content_mode':'article','content_format':'markdown','primary_action':'read','status':'active','tags':['upgrade','preserve']},open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False)
PY
api_post content_save "$RUN_ROOT/article.json" "$RUN_ROOT/article-out.json"
ARTICLE_ID="$(json_value "$RUN_ROOT/article-out.json" id)"
printf '%s' '{"note":"final acceptance preservation backup"}' > "$RUN_ROOT/backup.json"
api_post backup "$RUN_ROOT/backup.json" "$RUN_ROOT/backup-out.json"
BACKUP_NAME="$(json_value "$RUN_ROOT/backup-out.json" filename)"
python3 - "$RUN_ROOT/fixture.png" <<'PY'
import base64,sys
open(sys.argv[1],'wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZfGQAAAAASUVORK5CYII='))
PY
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $CSRF" -F "item_id=$ARTICLE_ID" -F "attachment=@$RUN_ROOT/fixture.png;type=image/png" "$BASE/api.php?action=attachment_upload" > "$RUN_ROOT/attachment-out.json"
assert_json_true "$RUN_ROOT/attachment-out.json" ok
curl -fsS -b "$COOKIE" "$BASE/api.php?action=content_get&id=$ARTICLE_ID" > "$RUN_ROOT/before-content.json"
python3 - "$RUN_ROOT/before-content.json" "$RUN_ROOT/before-content.sha" <<'PY'
import json,hashlib,sys
x=json.load(open(sys.argv[1],encoding='utf-8'));assert x['ok'];s=json.dumps(x['item'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();open(sys.argv[2],'w').write(hashlib.sha256(s).hexdigest())
PY
DB_FILE="$(cd "$SITE31" && php -r '$r=include "app/.runtime.php";echo $r["db_file"];')"
ATT_DIR="$(cd "$SITE31" && php -r '$r=include "app/.runtime.php";echo $r["attachment_dir"];')"
BACKUP_DIR="$(cd "$SITE31" && php -r '$r=include "app/.runtime.php";echo $r["backup_dir"];')"
[[ "$(sqlite3 "$DB_FILE" 'PRAGMA integrity_check;')" == ok ]]
[[ -z "$(sqlite3 "$DB_FILE" 'PRAGMA foreign_key_check;')" ]]
find "$ATT_DIR" -type f -print0 | sort -z | xargs -0 sha256sum > "$RUN_ROOT/attachments.before"
BACKUP_SHA="$(sha256sum "$BACKUP_DIR/$BACKUP_NAME" | awk '{print $1}')"
echo P02_FINAL_251_PRIVATE_FIXTURE=PASS

step "Execute generated Atomic repair candidate against real V2.5.31"
REPAIR="$(find "$PRODUCT/build/final-accept-a" -maxdepth 1 -type f -name 'repair-v2.5.31-to-v2.5.32-candidate.php' -print -quit)"
[[ -f "$REPAIR" ]]
REPAIR_NAME="$(basename "$REPAIR")"
cp "$REPAIR" "$SITE31/$REPAIR_NAME"
curl -fsS -b "$COOKIE" -c "$COOKIE" "$BASE/$REPAIR_NAME?vf_same_site_bridge=1" > "$RUN_ROOT/repair-form.html"
REPAIR_CSRF="$(python3 - "$RUN_ROOT/repair-form.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m,s[:500];print(html.unescape(m.group(1)))
PY
)"
UPGRADE_STATUS="$(curl -sS -o "$RUN_ROOT/repair-result.html" -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" --data-urlencode 'action=upgrade' --data-urlencode "csrf=$REPAIR_CSRF" "$BASE/$REPAIR_NAME")"
[[ "$UPGRADE_STATUS" == 200 ]]
grep -q '升级完成' "$RUN_ROOT/repair-result.html"
[[ ! -e "$SITE31/$REPAIR_NAME" ]]
[[ "$(tr -d '\r\n' < "$SITE31/VERSION.txt")" == "2.5.32" ]]
echo P02_FINAL_REAL_ATOMIC_UPGRADE_EXECUTED=PASS

step "Verify private data, SQLite, and target behavior after upgrade"
curl -fsS -b "$COOKIE" -c "$COOKIE" "$BASE/api.php?action=session" > "$RUN_ROOT/session32.json"
assert_json_true "$RUN_ROOT/session32.json" ok
assert_json_true "$RUN_ROOT/session32.json" site.auth
[[ "$(json_value "$RUN_ROOT/session32.json" version)" == "2.5.32" ]]
curl -fsS -b "$COOKIE" "$BASE/api.php?action=content_get&id=$ARTICLE_ID" > "$RUN_ROOT/after-content.json"
python3 - "$RUN_ROOT/after-content.json" "$RUN_ROOT/after-content.sha" <<'PY'
import json,hashlib,sys
x=json.load(open(sys.argv[1],encoding='utf-8'));assert x['ok'];s=json.dumps(x['item'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();open(sys.argv[2],'w').write(hashlib.sha256(s).hexdigest())
PY
cmp -s "$RUN_ROOT/before-content.sha" "$RUN_ROOT/after-content.sha"
[[ "$(sqlite3 "$DB_FILE" 'PRAGMA integrity_check;')" == ok ]]
[[ -z "$(sqlite3 "$DB_FILE" 'PRAGMA foreign_key_check;')" ]]
find "$ATT_DIR" -type f -print0 | sort -z | xargs -0 sha256sum > "$RUN_ROOT/attachments.after"
cmp -s "$RUN_ROOT/attachments.before" "$RUN_ROOT/attachments.after"
[[ "$(sha256sum "$BACKUP_DIR/$BACKUP_NAME" | awk '{print $1}')" == "$BACKUP_SHA" ]]
( cd "$SITE31" && php cli/verify.php ) > "$EVIDENCE/upgrade-cli-verify.json"
assert_json_true "$EVIDENCE/upgrade-cli-verify.json" ok
echo P02_FINAL_DATA_PRESERVATION=PASS

after_assets=(navigation-refresh-policy.js update-core-ui.js v2520-draft-retirement.js v2521-context-ux.js v254-common-branding.js v255-hotfix.js editor-enhancements.css scratch-tabs.css v250-uaui.css v250-reader-scale.css v251-hotfix.css v252-hotfix.css v253-hotfix.css v254-common-branding.css v2514-writing-typography.css v2521-context-ux.css)
for old in "${after_assets[@]}"; do
  if [[ -e "$SITE31/assets/$old" ]]; then echo "P02_FINAL_UPGRADE_GARBAGE_PRESENT=$old" >&2; exit 61; fi
done
[[ -f "$SITE31/assets/favicon-settings.js" ]]
[[ ! -e "$SITE31/assets/v254-common-branding.js" ]]
echo P02_FINAL_UPGRADE_SOURCE_CLEANLINESS=PASS

step "Post-upgrade standard Chromium task flow"
CSRF="$(json_value "$RUN_ROOT/session32.json" csrf)"
VF_UX_E2E_BASE_URL="$BASE" VF_UX_E2E_PASSWORD="$PASSWORD" VF_UX_E2E_VERSION=2.5.32 node "$PRODUCT/tests/e2e/p02_ux_task_flow.mjs"
echo P02_FINAL_POST_UPGRADE_CHROMIUM=PASS

step "Canonical publication boundaries"
DEV="$(git ls-remote https://github.com/llhzx2018/vf-library.git refs/heads/develop | awk '{print $1}')"
MAIN="$(git ls-remote https://github.com/llhzx2018/vf-library.git refs/heads/main | awk '{print $1}')"
[[ "$DEV" == "e0bac8f6ec30df94e626e07821ae3c39cbcd7f59" ]]
[[ "$MAIN" == "6a43f76308f6ba3e4fd675d121ba9fe7be7f3ddd" ]]
[[ -z "$(git ls-remote --tags https://github.com/llhzx2018/vf-library.git refs/tags/v2.5.32)" ]]
curl -fsSL https://raw.githubusercontent.com/llhzx2018/core-updates/main/projects/P02.json > "$RUN_ROOT/P02.json"
python3 - "$RUN_ROOT/P02.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'));assert x['target_version']=='2.5.31';assert x['release_tag']=='v2.5.31-rc.1'
PY
echo P02_FINAL_BOUNDARY_MAIN_WRITE=NO
echo P02_FINAL_BOUNDARY_RELEASE_WRITE=NO
echo P02_FINAL_BOUNDARY_TAG_WRITE=NO
echo P02_FINAL_BOUNDARY_UPDATE_CHANNEL_WRITE=NO
echo P02_FINAL_BOUNDARY_PRODUCTION_WRITE=NO
echo P02_FINAL_CORE_ACCEPTANCE=PASS
