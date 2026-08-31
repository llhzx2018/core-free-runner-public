#!/usr/bin/env bash
set -Eeuo pipefail
BASE_REF='4e179cca6fd8a83b527401bc65e8d78d8753a106'
EXPECTED_VERSION='2.5.32'
PORT=18154
ROOT="$GITHUB_WORKSPACE/product"
RUN_ROOT="$RUNNER_TEMP/p02-r54"
cd "$ROOT"
test "$(git rev-parse HEAD)" = "$BASE_REF"
test "$(tr -d '\r\n' < VERSION)" = "$EXPECTED_VERSION"
test -f public/assets/v254-common-branding.js
test ! -e public/assets/favicon-settings.js
echo P02_R54_READONLY_AUDIT=PASS

python3 - <<'PY'
from pathlib import Path
import json
old=Path('public/assets/v254-common-branding.js'); new=Path('public/assets/favicon-settings.js')
s=old.read_text(encoding='utf-8')
for a,b in [('favicon-setting-v254','favicon-setting'),('faviconSettingV254','faviconSetting'),('faviconFileV254','faviconFile'),('deleteFaviconV254','deleteFavicon'),('V254_FAVICON_DOMAIN','FAVICON_SETTINGS_DOMAIN')]: s=s.replace(a,b)
if 'favicon-action.php?action=status' not in s: raise SystemExit('favicon domain status seam missing')
for token in ['favicon-setting-v254','faviconSettingV254','faviconFileV254','deleteFaviconV254']:
    if token in s: raise SystemExit('versioned favicon marker remains: '+token)
new.write_text(s,encoding='utf-8'); old.unlink()

p=Path('public/index.php'); s=p.read_text(encoding='utf-8')
a='/assets/v254-common-branding.js?v=<?=rawurlencode(VFTB_VERSION)?>'; b='/assets/favicon-settings.js?v=<?=rawurlencode(VFTB_VERSION)?>'
if s.count(a)!=1: raise SystemExit('runtime entry drifted')
p.write_text(s.replace(a,b),encoding='utf-8')

p=Path('public/assets/app.css'); s=p.read_text(encoding='utf-8')
a='/* V2.5.32 R27 consolidated source: v254-common-branding.css */'; b='/* Favicon settings domain (consolidated) */'
if s.count(a)!=1: raise SystemExit('favicon css boundary drifted')
s=s.replace(a,b).replace('.favicon-setting-v254','.favicon-setting')
stale='\n/* V2.5.17_LIBRARY_MODEL_CONVERGENCE */\n.side-item[data-mode="quick"],.side-item[data-mode="article"]{display:none!important}\n'
if s.count(stale)!=1: raise SystemExit('stale Library Model css residue drifted')
p.write_text(s.replace(stale,'\n'),encoding='utf-8')

p=Path('tests/unit/p02_library_model_native_ownership_contract.mjs'); s=p.read_text(encoding='utf-8')
a="common=read('public/assets/v254-common-branding.js')"; b="favicon=read('public/assets/favicon-settings.js')"
if a not in s: raise SystemExit('library-model contract seam drifted')
s=s.replace(a,b).replace("common.includes('V2.5.17_LIBRARY_MODEL_CONVERGENCE')","favicon.includes('V2.5.17_LIBRARY_MODEL_CONVERGENCE')").replace('common.includes(token)','favicon.includes(token)').replace("common.includes('favicon-action.php?action=status')","favicon.includes('favicon-action.php?action=status')")
p.write_text(s,encoding='utf-8')

p=Path('tests/unit/p02_runtime_style_single_entry.mjs'); s=p.read_text(encoding='utf-8')
a="const common=fs.readFileSync('public/assets/v254-common-branding.js','utf8');"; b="const favicon=fs.readFileSync('public/assets/favicon-settings.js','utf8');"
if a not in s: raise SystemExit('runtime-style contract seam drifted')
p.write_text(s.replace(a,b).replace('common.includes','favicon.includes'),encoding='utf-8')

p=Path('tests/unit/p02_css_convergence_contract.mjs'); s=p.read_text(encoding='utf-8')
a="'v253-hotfix.css','v254-common-branding.css','v2514-writing-typography.css'"
if a not in s: raise SystemExit('css convergence list seam drifted')
s=s.replace(a,"'v253-hotfix.css','v2514-writing-typography.css'")
a="const oldPos=css.indexOf('V2.5.32 R27 consolidated source: v2514-writing-typography.css');"
b="assert.ok(!fs.existsSync('public/assets/v254-common-branding.css'),'historical v254 css must remain consolidated');\nassert.ok(css.includes('Favicon settings domain (consolidated)'),'semantic favicon css boundary missing');\nassert.ok(!css.includes('V2.5.17_LIBRARY_MODEL_CONVERGENCE'),'retired Library Model CSS marker remains');\n"+a
if s.count(a)!=1: raise SystemExit('css contract insertion seam drifted')
p.write_text(s.replace(a,b),encoding='utf-8')

Path('tests/unit/p02_favicon_domain_ownership_contract.mjs').write_text("""import fs from 'node:fs';
import assert from 'node:assert/strict';
const read=p=>fs.readFileSync(new URL('../../'+p,import.meta.url),'utf8');
const index=read('public/index.php'),favicon=read('public/assets/favicon-settings.js'),css=read('public/assets/app.css');
assert.equal(fs.existsSync('public/assets/v254-common-branding.js'),false);
assert.equal((index.match(/\/assets\/favicon-settings\.js/g)||[]).length,1);
assert.equal(index.includes('/assets/v254-common-branding.js'),false);
for(const token of ['favicon-action.php?action=status','favicon-action.php?action=upload','favicon-action.php?action=delete','faviconSetting','faviconFile','deleteFavicon'])assert.ok(favicon.includes(token),token);
for(const token of ['favicon-setting-v254','faviconSettingV254','faviconFileV254','deleteFaviconV254'])assert.equal(favicon.includes(token),false,token);
assert.ok(css.includes('.favicon-setting{'));
assert.equal(css.includes('.favicon-setting-v254'),false);
assert.equal(css.includes('V2.5.17_LIBRARY_MODEL_CONVERGENCE'),false);
const manifest=JSON.parse(read('SOURCE_MANIFEST.json'));assert.equal(manifest.runtime_source_file_count,67);assert.ok(manifest.entries.some(x=>x.repo_path==='public/assets/favicon-settings.js'));assert.equal(manifest.entries.some(x=>x.repo_path==='public/assets/v254-common-branding.js'),false);
const candidate=JSON.parse(read('docs/authority/P02_DEVELOP_CANDIDATE_IDENTITY.json'));for(const k of ['favicon_domain_semantic_module','v254_common_branding_filename_retired','favicon_versioned_dom_markers_retired','library_model_css_residue_retired'])assert.equal(candidate.convergence[k],true,k);
console.log('P02_FAVICON_DOMAIN_OWNERSHIP=PASS');
""",encoding='utf-8')

a=Path('docs/authority/P02_DEVELOP_CANDIDATE_IDENTITY.json'); d=json.loads(a.read_text(encoding='utf-8'))
if d.get('runtime_source_file_count')!=67: raise SystemExit('unexpected runtime source count')
d.setdefault('convergence',{}).update({'favicon_domain_semantic_module':True,'v254_common_branding_filename_retired':True,'favicon_versioned_dom_markers_retired':True,'library_model_css_residue_retired':True}); d['next_gate']='FINAL_PRODUCT_ACCEPTANCE'
a.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
Path('docs/evidence/P02_R54_FAVICON_DOMAIN_OWNERSHIP_20260831.md').write_text("""# P02 R54 · Favicon Domain Ownership · 2026-08-31

R54 is the final high-value ownership residue pass after R53 Library Model native convergence.

- `v254-common-branding.js` had become a single-purpose favicon module; it is renamed to `favicon-settings.js` without changing runtime source count.
- Version-coded favicon DOM markers are replaced by semantic identifiers.
- The consolidated favicon CSS boundary is semanticized.
- The retired `V2.5.17_LIBRARY_MODEL_CONVERGENCE` quick/article hiding rule is removed from `app.css`; legacy mode normalization is owned natively by `app.js`.
- `attachments.js`, `editor-enhancements.js`, `maintenance.js`, `scratch-tabs.js`, `v250-uaui.js`, and `v251-preboot.js` remain intentionally separate coherent modules. R54 does not merge files for cosmetic file-count reduction.

Boundary: VERSION 2.5.32, Schema 2401, runtime sources 67. No main/tag/release/update-channel/production write.
""",encoding='utf-8')
PY

node --check public/assets/favicon-settings.js
python3 scripts/generate-source-manifest.py
python3 scripts/verify-source-manifest.py
bash scripts/verify-repository.sh
for t in tests/unit/p02_*.mjs tests/unit/v2523_unified_content_workspace_contract.mjs; do node "$t"; done
git diff --check
test "$(node -e "console.log(JSON.parse(require('fs').readFileSync('SOURCE_MANIFEST.json','utf8')).runtime_source_file_count)")" = 67
grep -F '/assets/favicon-settings.js' public/index.php
! grep -F '/assets/v254-common-branding.js' public/index.php
! grep -F 'V2.5.17_LIBRARY_MODEL_CONVERGENCE' public/assets/app.css
cp SOURCE_MANIFEST.json "$RUNNER_TEMP/r54-manifest.json"; cp SOURCE_MANIFEST.txt "$RUNNER_TEMP/r54-manifest.txt"
python3 scripts/generate-source-manifest.py
cmp -s SOURCE_MANIFEST.json "$RUNNER_TEMP/r54-manifest.json"; cmp -s SOURCE_MANIFEST.txt "$RUNNER_TEMP/r54-manifest.txt"
python3 scripts/verify-source-manifest.py
echo P02_R54_STATIC_AND_MANIFEST=PASS

sudo apt-get update -qq
sudo apt-get install -y php-cli php-sqlite3 sqlite3 curl >/dev/null
npm install --no-save --package-lock=false playwright@1.55.0 >/dev/null
npx playwright install --with-deps chromium >/dev/null
mkdir -p "$RUN_ROOT/site-root"
bash scripts/build-deploy-tree.sh "$RUN_ROOT/site-root/site"
php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$RUN_ROOT/site-root/site" >"$RUN_ROOT/php.log" 2>&1 &
PHP_PID=$!; trap 'kill "$PHP_PID" 2>/dev/null || true' EXIT
BASE_URL="http://127.0.0.1:$PORT"
for _ in $(seq 1 80); do curl -fsS "$BASE_URL/setup.php" >/dev/null 2>&1 && break; sleep .25; done
PASSWORD="VF-R54-${GITHUB_RUN_ID}!"
curl -fsS -c "$RUN_ROOT/cookie" "$BASE_URL/setup.php" > "$RUN_ROOT/setup.html"
CSRF="$(python3 - "$RUN_ROOT/setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)"
STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -b "$RUN_ROOT/cookie" -c "$RUN_ROOT/cookie" -H "Origin: $BASE_URL" --data-urlencode "setup_csrf=$CSRF" --data-urlencode "password=$PASSWORD" --data-urlencode "password_confirm=$PASSWORD" "$BASE_URL/setup.php")"
test "$STATUS" = 303
VF_UX_E2E_BASE_URL="$BASE_URL" VF_UX_E2E_PASSWORD="$PASSWORD" VF_UX_E2E_VERSION="$EXPECTED_VERSION" node tests/e2e/p02_ux_task_flow.mjs
echo P02_R54_STANDARD_CHROMIUM=PASS

cat > "$RUN_ROOT/r54-proof.mjs" <<'JS'
import { chromium } from 'playwright';
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1280,height:820}});const base=process.env.BASE_URL,password=process.env.PASSWORD,ok=(v,m)=>{if(!v)throw new Error(m)};
await page.goto(base+'/',{waitUntil:'networkidle'});if(await page.locator('[data-open-login]').count()){await page.locator('[data-open-login]').click();await page.locator('#loginForm input[name="password"]').fill(password);await page.locator('#loginSubmit').click();await page.waitForFunction(async()=>Boolean((await(await fetch('/api.php?action=session')).json())?.site?.auth));}
const resources=await page.evaluate(()=>performance.getEntriesByType('resource').map(x=>x.name));ok(resources.filter(x=>x.includes('/assets/favicon-settings.js')).length===1,'semantic favicon script must load once');ok(resources.filter(x=>x.includes('/assets/v254-common-branding.js')).length===0,'retired v254 script requested');
const asset=await page.evaluate(async()=>await(await fetch('/assets/favicon-settings.js')).text());ok(asset.includes('favicon-action.php?action=status'),'favicon status seam missing');for(const token of ['faviconSettingV254','faviconFileV254','deleteFaviconV254'])ok(!asset.includes(token),'old marker remains '+token);ok(await page.evaluate(async()=>{const r=await fetch('/favicon-action.php?action=status');return r.ok;}),'favicon status endpoint failed');ok((await page.locator('[data-mode="quick"], [data-mode="article"]').count())===0,'retired Library modes re-exposed');
await page.locator('#settingsBtn').click();await page.waitForSelector('#settingsPanel');ok((await page.locator('#faviconSetting').count())===1,'semantic favicon setting control missing');ok((await page.locator('#faviconFile').count())===1,'semantic favicon input missing');ok((await page.locator('#deleteFavicon').count())===1,'semantic favicon delete control missing');ok((await page.locator('#faviconSettingV254,#faviconFileV254,#deleteFaviconV254').count())===0,'old favicon ids exposed');
await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);const mobile=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:document.documentElement.clientWidth,control:document.querySelector('#faviconSetting')?.getBoundingClientRect().width||0}));ok(mobile.scroll<=mobile.width+1,'390px horizontal overflow '+JSON.stringify(mobile));ok(mobile.control>0&&mobile.control<=390,'favicon control invalid at 390px '+JSON.stringify(mobile));await browser.close();console.log('P02_R54_SPECIALIZED_CHROMIUM=PASS');
JS
ln -s "$ROOT/node_modules" "$RUN_ROOT/node_modules"
BASE_URL="$BASE_URL" PASSWORD="$PASSWORD" node "$RUN_ROOT/r54-proof.mjs"
rm -rf browser-evidence
git diff --check
echo P02_R54_PREWRITE_GATE=PASS

git config user.name 'VictorForge'; git config user.email 'llhzx2018@gmail.com'; git add -A; git commit -m 'refactor(P02): semanticize favicon domain ownership'
NEW_SHA="$(git rev-parse HEAD)"
git remote set-url origin "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/llhzx2018/vf-library.git"
git fetch origin develop --depth=1
test "$(git rev-parse origin/develop)" = "$BASE_REF"
git push origin HEAD:refs/heads/develop
git remote set-url origin https://github.com/llhzx2018/vf-library.git
echo "P02_R54_NEW_SHA=$NEW_SHA"
echo P02_R54_DEVELOP_WRITE=PASS
echo P02_R54_BOUNDARY_MAIN_WRITE=NO
echo P02_R54_BOUNDARY_RELEASE_WRITE=NO
echo P02_R54_BOUNDARY_TAG_WRITE=NO
echo P02_R54_BOUNDARY_UPDATE_CHANNEL_WRITE=NO
echo P02_R54_BOUNDARY_PRODUCTION_WRITE=NO
