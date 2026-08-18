#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN missing}"
: "${VF_PRIVATE_READ_TOKEN:?VF_PRIVATE_READ_TOKEN missing}"

SOURCE_REPO="llhzx2018/vf-forge"
SOURCE_BRANCH="maintenance/v1.36.2-settings-performance"
BASE_TAG="v1.36.1"
FROM_VERSION="1.36.1"
TARGET_VERSION="1.36.2"
SCHEMA="30"
RELEASE_TAG="v1.36.2"
ASSET_NAME="VF_Forge_V1.36.2_UPDATE.zip"
FIXTURE_PASS="Vf1362-Settings-Perf!"
PHP_IMAGE="vf-forge-php84-v1362"
WORK="${RUNNER_TEMP:-/tmp}/p03-v1362-settings-perf"
SOURCE="$WORK/source"
RELEASE="$WORK/release"
EVIDENCE="${GITHUB_WORKSPACE:-$PWD}/p03-v1362-release-evidence"

rm -rf "$WORK" "$EVIDENCE"
mkdir -p "$WORK" "$EVIDENCE"
cleanup(){ docker rm -f p03-v1362-ui p03-v1362-up p03-v1362-discovery >/dev/null 2>&1 || true; }
trap cleanup EXIT
log(){ printf '\n== %s ==\n' "$*"; }

log "Clone V1.36.1 baseline branch"
git clone -q "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/${SOURCE_REPO}.git" "$SOURCE"
cd "$SOURCE"
git checkout -q "$SOURCE_BRANCH"
git fetch -q origin main --tags
CURRENT="$(tr -d '\r\n' < VERSION)"
case "$CURRENT" in 1.36.1|1.36.2) ;; *) echo "UNEXPECTED_VERSION=$CURRENT" >&2; exit 1;; esac
test "$(git show "$BASE_TAG":VERSION | tr -d '\r\n')" = "$FROM_VERSION"
test "$(git show "$BASE_TAG":database/schema/SCHEMA_VERSION | tr -d '\r\n')" = "$SCHEMA"

log "Apply V1.36.2 settings performance patch"
python3 - <<'PY'
from pathlib import Path
import json
root=Path('.')

def once(text,old,new,label):
    if new in text:return text
    if old not in text:raise SystemExit('PATCH_ANCHOR_MISSING:'+label)
    return text.replace(old,new,1)

(root/'VERSION').write_text('1.36.2\n',encoding='utf-8')
p=root/'src/app/bootstrap.php';s=p.read_text(encoding='utf-8')
s=once(s,"define('VFAB_VERSION', '1.36.1');","define('VFAB_VERSION', '1.36.2');",'bootstrap-version')
p.write_text(s,encoding='utf-8')

p=root/'public/assets/experience.js';js=p.read_text(encoding='utf-8')
js=once(js,
"const S={csrf:'',projects:[],projectId:0,projectTab:'overview',settingsTab:'general',settings:null,timezone:'Asia/Shanghai',dateFormat:'ymd_hm',currency:'CNY',defaultDensity:'comfortable'};",
"const S={csrf:'',projects:[],projectId:0,projectTab:'overview',settingsTab:'general',settings:null,settingsLoadedAt:0,settingsLoading:null,timezone:'Asia/Shanghai',dateFormat:'ymd_hm',currency:'CNY',defaultDensity:'comfortable'};",
'js-settings-state')
old="const settingsTabs=[['general','基础'],['security','账户与安全'],['backup','备份与恢复'],['update','更新与维护'],['system','系统信息']];\nasync function renderSettings(){active('settings');crumb('设置');const d=await api('settings');S.settings=d;"
new="const settingsTabs=[['general','基础'],['security','账户与安全'],['backup','备份与恢复'],['update','更新与维护'],['system','系统信息']];\nasync function loadSettings(force=false){if(!force&&S.settings)return S.settings;if(S.settingsLoading)return S.settingsLoading;S.settingsLoading=api('settings').then(d=>{S.settings=d;S.settingsLoadedAt=Date.now();return d}).finally(()=>{S.settingsLoading=null});return S.settingsLoading}\nasync function renderSettings(force=false){active('settings');crumb('设置');const d=await loadSettings(force);"
js=once(js,old,new,'js-settings-cache')
js=once(js,
"await api('settings_save',{method:'POST',body:{settings:Object.fromEntries(new FormData(e.target))}});toast('设置已保存');await renderSettings();return}",
"await api('settings_save',{method:'POST',body:{settings:Object.fromEntries(new FormData(e.target))}});toast('设置已保存');await renderSettings(true);return}",
'js-settings-save-refresh')
for old,new,label in [
("toast('其他会话已注销');await renderSettings()","toast('其他会话已注销');await renderSettings(true)",'session-refresh'),
("toast('SQLite 元数据备份已创建');await renderSettings()","toast('SQLite 元数据备份已创建');await renderSettings(true)",'backup-create-refresh'),
("toast('保留策略已执行');await renderSettings()","toast('保留策略已执行');await renderSettings(true)",'retention-refresh'),
("toast('更新检查完成');await renderSettings()","toast('更新检查完成');await renderSettings(true)",'update-refresh'),
("else if(x==='refresh-system')await renderSettings()","else if(x==='refresh-system')await renderSettings(true)",'system-refresh'),
("if(a.dataset.action==='update-check'){try{await renderSettings()}catch{}}","if(a.dataset.action==='update-check'){try{await renderSettings(true)}catch{}}",'update-error-refresh'),
("S.csrf='';loginView()","S.csrf='';S.settings=null;S.settingsLoadedAt=0;loginView()",'logout-cache-clear')]:
    js=once(js,old,new,label)
if '/* V1.36.2 SETTINGS PERFORMANCE */' not in js:js='/* V1.36.2 SETTINGS PERFORMANCE */\n'+js
p.write_text(js,encoding='utf-8')

p=root/'VF_PROJECT.json';d=json.loads(p.read_text(encoding='utf-8'))
d['status']='V1.36.2 SETTINGS CENTER PERFORMANCE / FORMAL RELEASE GATE'
d['production_version']='1.36.1';d['working_version']='1.36.2';d['candidate_version']='1.36.2';d['schema_version']=30
d['working_branch']='maintenance/v1.36.2-settings-performance'
d['current_phase']='V1.36.2 SETTINGS CENTER PERFORMANCE / FORMAL RELEASE GATE'
d['current_verdict']='SETTINGS_CACHE_IMPLEMENTED / RELEASE_GATE_PENDING'
d['version_change']='1.36.2 WORKING';d['production_write']='NO'
d['next_action']='FORMAL GATE -> RELEASE -> core-updates PUBLISH -> OWNER BACKEND UPDATE'
d['v1_36_2_settings_performance']={'scope':['SETTINGS SINGLE-FETCH CACHE','INSTANT SETTINGS TAB SWITCH','FORCED REFRESH AFTER MUTATIONS','CACHE CLEAR ON LOGOUT','BROWSER REQUEST-COUNT GATE','RESPONSIVE REGRESSION'],'schema':30,'migration':'NONE','project_asset_storage':'NONE','production_write':'NO'}
if isinstance(d.get('release'),dict):
    d['release']['production_version']='1.36.1';d['release']['production_tag']='v1.36.1';d['release']['candidate_version']='1.36.2';d['release']['candidate_release']='FORMAL RELEASE GATE PENDING';d['release']['production_write']=False
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'docs/product/V1362_SETTINGS_CENTER_PERFORMANCE.md').write_text('''# P03 · VF Forge V1.36.2 Settings Center Performance\n\n- Baseline: V1.36.1 / Schema 30\n- Target: V1.36.2 / Schema 30\n- Migration: NONE\n\n## Root cause\n\nEach settings sub-tab previously called the full `settings` API and rebuilt the settings surface.\n\n## Fix\n\n1. Fetch the full settings payload once on first entry.\n2. Cache it in the current authenticated browser session.\n3. Switching 基础 / 账户与安全 / 备份与恢复 / 更新与维护 / 系统信息 is local-only and does not issue a repeated settings request.\n4. State-changing actions force one authoritative refresh after success.\n5. Logout clears the settings cache.\n6. Browser gate verifies one settings request across repeated tab switches on desktop and mobile.\n\nPROJECT-ASSET STORAGE = NONE remains unchanged.\n''',encoding='utf-8')
PY
node --check public/assets/experience.js
python3 scripts/repo_health.py .
git diff --exit-code "$BASE_TAG" -- database/schema database/migrations

git config user.name 'VF Agent'
git config user.email 'vf-agent@users.noreply.github.com'
git add VERSION VF_PROJECT.json src/app/bootstrap.php public/assets/experience.js docs/product/V1362_SETTINGS_CENTER_PERFORMANCE.md
if ! git diff --cached --quiet; then
  git commit -m 'perf(settings): cache settings center tabs for v1.36.2'
  git push -q origin HEAD:"$SOURCE_BRANCH"
fi
SOURCE_SHA="$(git rev-parse HEAD)"
echo "SOURCE_SHA=$SOURCE_SHA"
test "$(tr -d '\r\n' < VERSION)" = "$TARGET_VERSION"
test "$(tr -d '\r\n' < database/schema/SCHEMA_VERSION)" = "$SCHEMA"
grep -Fq "define('VFAB_VERSION', '1.36.2');" src/app/bootstrap.php
grep -Fq 'V1.36.2 SETTINGS PERFORMANCE' public/assets/experience.js

log "Build PHP 8.4.24 runtime"
cat > "$WORK/Dockerfile" <<'EOF'
FROM php:8.4.24-cli-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libzip-dev sqlite3 curl git && docker-php-ext-install zip && rm -rf /var/lib/apt/lists/*
EOF
docker build -q -t "$PHP_IMAGE" -f "$WORK/Dockerfile" "$WORK" >/dev/null
docker run --rm -v "$SOURCE:/app:ro" -w /app "$PHP_IMAGE" sh -lc 'set -e; find src public -type f -name "*.php" -print0 | xargs -0 -n1 php -l >/dev/null; php -r '\''require "src/app/bootstrap.php";$x=vfab_php_security_baseline();if(empty($x["ok"]))exit(1);echo "PHP_SECURITY_PASS\n";'\'''

log "Browser performance regression: settings tabs"
ROOT="$WORK/ui-runtime";DATA="$WORK/ui-private";URL="http://127.0.0.1:18112";C="p03-v1362-ui"
python3 scripts/build_runtime.py "$ROOT" >/dev/null
mkdir -p "$DATA"
docker run -d --rm --name "$C" -e VF_PRIVATE_READ_TOKEN="$VF_PRIVATE_READ_TOKEN" -p 18112:18112 -v "$ROOT:/app" -v "$DATA:$DATA" -w /app "$PHP_IMAGE" php -S 0.0.0.0:18112 -t /app >/dev/null
for _ in $(seq 1 80);do curl -fsS "$URL/setup.php" >/dev/null 2>&1&&break;sleep .25;done
COOKIE="$WORK/ui-cookie";curl -fsS -c "$COOKIE" "$URL/setup.php" -o "$WORK/ui-setup.html"
CSRF=$(python3 - "$WORK/ui-setup.html" <<'PY'
import re,sys
print(re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge Perf Gate' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$URL/setup.php" >/dev/null
mkdir -p "$WORK/node";cd "$WORK/node";npm init -y >/dev/null 2>&1;npm install --no-save playwright@1.55.0 >/dev/null;npx playwright install --with-deps chromium >/dev/null
cat > gate.mjs <<'JS'
import{chromium}from'playwright';
const b=await chromium.launch({headless:true}),p=await b.newPage({viewport:{width:1440,height:900}}),errs=[];let settingsRequests=0;
p.on('pageerror',e=>errs.push('PAGE:'+e.message));p.on('console',m=>{if(m.type()==='error')errs.push('CONSOLE:'+m.text())});
p.on('request',r=>{const u=new URL(r.url());if(u.pathname.endsWith('/api.php')&&u.searchParams.get('action')==='settings')settingsRequests++});
await p.goto('http://127.0.0.1:18112/',{waitUntil:'domcontentloaded'});await p.fill('#loginPassword',process.env.FIXTURE_PASS);await p.click('#loginForm button[type=submit]');await p.waitForSelector('#app:not([hidden])');
await p.locator('[data-route="settings"]:visible').first().click();await p.waitForSelector('#generalSettingsForm');if(settingsRequests!==1)throw Error('initial settings requests='+settingsRequests);
for(let round=0;round<3;round++)for(const tab of ['security','backup','update','system','general']){const t=Date.now();await p.locator(`[data-settings-tab="${tab}"]`).click();if(Date.now()-t>250)throw Error('slow local tab '+tab);}
if(settingsRequests!==1)throw Error('repeated settings requests='+settingsRequests);
await p.setViewportSize({width:390,height:844});for(const tab of ['security','backup','update','system','general'])await p.locator(`[data-settings-tab="${tab}"]`).click();if(settingsRequests!==1)throw Error('mobile repeated settings requests='+settingsRequests);
const [sw,cw]=await p.evaluate(()=>[document.documentElement.scrollWidth,document.documentElement.clientWidth]);if(sw>cw+2)throw Error('mobile overflow');
if(errs.length)throw Error(errs.join('\n'));console.log('V1362_SETTINGS_PERF_PASS settings_requests=1 repeated_tabs=20 local_switch=PASS responsive=1440,390 errors=0');await b.close();
JS
FIXTURE_PASS="$FIXTURE_PASS" node gate.mjs
cd "$SOURCE";docker rm -f "$C" >/dev/null

log "Build exact V1.36.2 UPDATE Asset"
TARGET="$WORK/target";BASE="$WORK/base";WT="$WORK/base-wt"
python3 scripts/build_runtime.py "$TARGET" >/dev/null
git worktree add --detach "$WT" "$BASE_TAG" >/dev/null;python3 "$WT/scripts/build_runtime.py" "$BASE" >/dev/null;git worktree remove --force "$WT" >/dev/null
cp scripts/build_atomic.py "$WORK/builder.py"
python3 - "$WORK/builder.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(encoding='utf-8')
s=s.replace('1.35.3','1.36.2').replace('1.35.2','1.36.1')
s=s.replace('TARGET_SCHEMA=29','TARGET_SCHEMA=30').replace('VFF_ATOMIC_SCHEMA=29','VFF_ATOMIC_SCHEMA=30')
s=s.replace("'maintenance.php','robots.txt'","'maintenance.php','memory-api.php','robots.txt'")
p.write_text(s,encoding='utf-8')
PY
python3 "$WORK/builder.py" --base-runtime "$BASE" --target-runtime "$TARGET" --output "$RELEASE" >/dev/null
GENERATED=$(find "$RELEASE" -maxdepth 1 -type f -name 'VF_Forge_V1.36.2_*Upgrade.zip' -printf '%f\n'|head -1);test -n "$GENERATED";mv "$RELEASE/$GENERATED" "$RELEASE/$ASSET_NAME"
ZIP="$RELEASE/$ASSET_NAME";unzip -t "$ZIP" >/dev/null;test "$(unzip -Z1 "$ZIP")" = 'repair-v1.36.2.php'
unzip -p "$ZIP" repair-v1.36.2.php > "$WORK/repair.php"
grep -Fq "const VFF_ATOMIC_TARGET='1.36.2';" "$WORK/repair.php";grep -Fq 'const VFF_ATOMIC_SCHEMA=30;' "$WORK/repair.php";grep -Fq 'const VFF_ATOMIC_ALLOWED=["1.36.1"];' "$WORK/repair.php"
! unzip -Z1 "$ZIP" | grep -E '(^|/)(database|PRIVATE_DATA|uploads|backup|cache|session|logs|tmp)(/|$)|\.sqlite3?$|\.db$|(^|/)\.env$'
ASSET_SHA=$(sha256sum "$ZIP"|awk '{print $1}');ASSET_BYTES=$(stat -c '%s' "$ZIP")

log "Real Atomic upgrade V1.36.1 -> V1.36.2"
ROOT="$WORK/up-runtime";DATA="$WORK/up-private";COOKIE="$WORK/up-cookie";URL="http://127.0.0.1:18113";C="p03-v1362-up"
git worktree add --detach "$WORK/up-wt" "$BASE_TAG" >/dev/null;python3 "$WORK/up-wt/scripts/build_runtime.py" "$ROOT" >/dev/null;git worktree remove --force "$WORK/up-wt" >/dev/null
mkdir -p "$DATA";docker run -d --rm --name "$C" -p 18113:18113 -v "$ROOT:/app" -v "$DATA:$DATA" -w /app "$PHP_IMAGE" php -S 0.0.0.0:18113 -t /app >/dev/null
for _ in $(seq 1 80);do curl -fsS "$URL/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$COOKIE" "$URL/setup.php" -o "$WORK/up-setup.html";CSRF=$(python3 - "$WORK/up-setup.html" <<'PY'
import re,sys;print(re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge Upgrade Gate' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$URL/setup.php" >/dev/null
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" -H 'Content-Type: application/json' --data "{\"password\":\"$FIXTURE_PASS\"}" "$URL/api.php?action=login" -o "$WORK/up-login.json"
unzip -p "$ZIP" repair-v1.36.2.php > "$ROOT/repair-v1.36.2.php";curl -fsS -b "$COOKIE" "$URL/repair-v1.36.2.php" -o "$WORK/repair-form.html";RCSRF=$(python3 - "$WORK/repair-form.html" <<'PY'
import re,sys;print(re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -b "$COOKIE" -H "Origin: $URL" --data-urlencode "_csrf=$RCSRF" --data-urlencode confirmation=UPGRADE "$URL/repair-v1.36.2.php" -o "$WORK/result.html"
grep -q '升级完成' "$WORK/result.html";grep -Fq "define('VFAB_VERSION', '1.36.2');" "$ROOT/app/bootstrap.php";grep -Fq 'V1.36.2 SETTINGS PERFORMANCE' "$ROOT/assets/experience.js";test ! -e "$ROOT/repair-v1.36.2.php"
DB=$(docker exec "$C" sh -lc "find '$DATA/database' -maxdepth 1 -type f -name '*.sqlite' | head -1");test "$(docker exec "$C" sqlite3 "$DB" 'pragma integrity_check;')" = ok;test -z "$(docker exec "$C" sqlite3 "$DB" 'pragma foreign_key_check;')";docker rm -f "$C" >/dev/null
echo 'ATOMIC_1361_TO_1362_PASS'

log "Publish GitHub Release and core-updates"
export GH_TOKEN="$VF_RELEASE_WRITE_TOKEN"
printf '%s\n' 'P03 · VF Forge V1.36.2' 'Settings center performance fix: one settings fetch, instant local tab switching, forced authoritative refresh only after mutations. Schema 30 unchanged.' > "$WORK/notes.md"
if gh release view "$RELEASE_TAG" --repo "$SOURCE_REPO" >/dev/null 2>&1;then REF=$(gh api "repos/$SOURCE_REPO/git/ref/tags/$RELEASE_TAG" --jq '.object.sha');test "$REF" = "$SOURCE_SHA";gh release upload "$RELEASE_TAG" "$ZIP" --repo "$SOURCE_REPO" --clobber;else gh release create "$RELEASE_TAG" "$ZIP" --repo "$SOURCE_REPO" --target "$SOURCE_SHA" --title 'VF Forge V1.36.2' --notes-file "$WORK/notes.md";fi
REL=$(gh api "repos/$SOURCE_REPO/releases/tags/$RELEASE_TAG");RID=$(jq -r '.id'<<<"$REL");AID=$(jq -r --arg n "$ASSET_NAME" '.assets[]|select(.name==$n)|.id'<<<"$REL");RBYTES=$(jq -r --arg n "$ASSET_NAME" '.assets[]|select(.name==$n)|.size'<<<"$REL");test "$RBYTES" = "$ASSET_BYTES";test -n "$AID"
RELEASED=$(date -u +%Y-%m-%dT%H:%M:%SZ);MANIFEST="$WORK/P03.json"
cat > "$MANIFEST" <<JSON
{
  "schema_version":"1.0",
  "project_id":"P03",
  "component_id":"APP",
  "enabled":true,
  "target_version":"1.36.2",
  "update_type":"ATOMIC",
  "from_versions":["1.36.1"],
  "schema_from":"30",
  "schema_to":"30",
  "repository":"llhzx2018/vf-forge",
  "release_tag":"v1.36.2",
  "release_id":$RID,
  "product_identity":"$SOURCE_SHA",
  "asset_name":"$ASSET_NAME",
  "asset_bytes":$ASSET_BYTES,
  "asset_sha256":"$ASSET_SHA",
  "backup_required":true,
  "rollback_supported":true,
  "released_at":"$RELEASED",
  "release_notes":{"summary":"V1.36.2：设置中心性能修复；首次加载一次，内部 Tab 本地瞬时切换，状态变更后再强制刷新。"},
  "notes":"Schema 30 unchanged. Upgrade from V1.36.1. PROJECT-ASSET STORAGE = NONE."
}
JSON
CREF=$(gh api repos/llhzx2018/core-updates/contents/projects/P03.json?ref=main);CSHA=$(jq -r '.sha'<<<"$CREF");ENC=$(base64 -w0 "$MANIFEST");gh api --method PUT repos/llhzx2018/core-updates/contents/projects/P03.json -f message='release(P03): publish VF Forge V1.36.2' -f content="$ENC" -f sha="$CSHA" -f branch=main >/dev/null
REMOTE=$(gh api repos/llhzx2018/core-updates/contents/projects/P03.json?ref=main --jq .content|base64 -d)
jq -e --arg sha "$SOURCE_SHA" --arg an "$ASSET_NAME" --arg ah "$ASSET_SHA" --argjson b "$ASSET_BYTES" '.target_version=="1.36.2" and .from_versions==["1.36.1"] and .product_identity==$sha and .asset_name==$an and .asset_sha256==$ah and .asset_bytes==$b and .schema_to=="30"'<<<"$REMOTE" >/dev/null

log "Exact V1.36.1 backend discovery of V1.36.2"
ROOT="$WORK/discovery-runtime";DATA="$WORK/discovery-private";COOKIE="$WORK/discovery-cookie";URL="http://127.0.0.1:18114";C="p03-v1362-discovery"
git worktree add --detach "$WORK/discovery-wt" "$BASE_TAG" >/dev/null;python3 "$WORK/discovery-wt/scripts/build_runtime.py" "$ROOT" >/dev/null;git worktree remove --force "$WORK/discovery-wt" >/dev/null;mkdir -p "$DATA"
docker run -d --rm --name "$C" -e VF_PRIVATE_READ_TOKEN="$VF_PRIVATE_READ_TOKEN" -p 18114:18114 -v "$ROOT:/app" -v "$DATA:$DATA" -w /app "$PHP_IMAGE" php -S 0.0.0.0:18114 -t /app >/dev/null
for _ in $(seq 1 80);do curl -fsS "$URL/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$COOKIE" "$URL/setup.php" -o "$WORK/d-setup.html";CSRF=$(python3 - "$WORK/d-setup.html" <<'PY'
import re,sys;print(re.search(r'name="setup_csrf" value="([^"]+)"',open(sys.argv[1],encoding='utf-8').read()).group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge Discovery' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$URL/setup.php" >/dev/null
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $URL" -H 'Content-Type: application/json' --data "{\"password\":\"$FIXTURE_PASS\"}" "$URL/api.php?action=login" -o "$WORK/d-login.json";CSRF2=$(python3 - "$WORK/d-login.json" <<'PY'
import json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.36.1';print(d['csrf'])
PY
)
curl -fsS -b "$COOKIE" -H "Origin: $URL" -H "X-CSRF-Token: $CSRF2" -H 'Content-Type: application/json' --data '{}' "$URL/api.php?action=system_update_check" -o "$WORK/check.json"
python3 - "$WORK/check.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));u=d.get('update') or {};assert d.get('ok') is True;assert u.get('has_update') is True;assert u.get('latest_version')=='1.36.2';assert u.get('asset_name')=='VF_Forge_V1.36.2_UPDATE.zip';assert not u.get('last_error_message');print('BACKEND_DISCOVERY_1361_TO_1362_PASS')
PY
docker rm -f "$C" >/dev/null

cat > "$EVIDENCE/release-readback.json" <<JSON
{"project":"P03 · VF Forge","source_sha":"$SOURCE_SHA","from":"1.36.1","target":"1.36.2","schema":30,"release_id":$RID,"asset_id":$AID,"asset_name":"$ASSET_NAME","asset_bytes":$ASSET_BYTES,"asset_sha256":"$ASSET_SHA","settings_single_fetch":"PASS","settings_tab_switch_local":"PASS","atomic_1361_to_1362":"PASS","backend_discovery_1361_to_1362":"PASS","project_asset_storage":"NONE"}
JSON
printf '%s  %s\n' "$ASSET_SHA" "$ASSET_NAME" > "$EVIDENCE/SHA256SUMS.txt"
echo "P03_V1362_SETTINGS_PERF_RELEASE_PASS source=$SOURCE_SHA release=$RID asset=$AID bytes=$ASSET_BYTES sha=$ASSET_SHA"
