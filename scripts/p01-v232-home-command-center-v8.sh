#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v4.sh"
TMP="$(mktemp /tmp/p01-v232-home-v8.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')

def replace_once(old: str, new: str, label: str) -> None:
    global src
    count = src.count(old)
    if count != 1:
        raise SystemExit(f'V8 {label} target count={count}')
    src = src.replace(old, new, 1)

# V7 authority transforms, applied directly to the V4 executable script.
replace_once(
    "printf '%s\\n' src/app/FunctionalHome.php src/app/FunctionalWorkspaceShell.php src/app/SurfaceRepository.php src/assets/workspace-home.css src/home.php | sort >\"$EVID/expected-diff.txt\"",
    "printf '%s\\n' src/app/FunctionalHome.php src/app/FunctionalWorkspaceShell.php src/app/SurfaceRepository.php src/assets/workspace-home.css src/home.php src/index.php | sort >\"$EVID/expected-diff.txt\"",
    'six-file baseline'
)
replace_once(
    "php -l \"$ROOT/app/SurfaceRepository.php\" >/dev/null",
    "php -l \"$ROOT/app/SurfaceRepository.php\" >/dev/null\nphp -l \"$ROOT/index.php\" >/dev/null",
    'index syntax'
)
replace_once(
    "P01_V232_FIVE_FILE_DELTA=PASS",
    "P01_V232_SIX_FILE_DELTA=PASS",
    'six-file verdict'
)
replace_once(
    "const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);",
    "const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const adminRoot=await d.request.get(base+'/',{maxRedirects:0});if(adminRoot.status()!==302||!(adminRoot.headers()['location']||'').includes('home.php'))throw new Error('admin root '+adminRoot.status()+' '+(adminRoot.headers()['location']||''));",
    'admin root authority'
)
replace_once(
    "const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const openedAsset=(state.assets||[]).find(x=>Number(x.id)===Number(a.id));if(!openedAsset)throw new Error('opened asset absent from Home payload');if(!String(openedAsset.last_surface_opened_at||''))throw new Error('navigation last_surface_opened_at missing');if(Number(openedAsset.click_count||0)<1)throw new Error('navigation click_count not incremented');",
    "const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const rawAssets=state.assets||[];const assets=Array.isArray(rawAssets)?rawAssets:Object.values(rawAssets);const openedAsset=assets.find(x=>Number(x.id)===Number(a.id));if(!openedAsset)throw new Error('opened asset absent from Home payload');",
    'payload shape authority'
)
replace_once(
    "P01_V232_ANONYMOUS_BOUNDARY=PASS\\n');console.log('HOME_BROWSER_PASS');",
    "P01_V232_ADMIN_ROOT_HOME=PASS\\nP01_V232_ANONYMOUS_BOUNDARY=PASS\\n');console.log('HOME_BROWSER_PASS');",
    'browser admin-root verdict'
)
replace_once(
    "P01_V232_ANONYMOUS_PUBLIC_ROOT_UNCHANGED=PASS\n",
    "P01_V232_ADMIN_ROOT_HOME=PASS\nP01_V232_ANONYMOUS_PUBLIC_ROOT_UNCHANGED=PASS\n",
    'shell admin-root verdict'
)

# V8 Home polish transforms.
replace_once(
    "await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(!p.url().endsWith('/home.php'))throw new Error('home route '+p.url());",
    "await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(!p.url().endsWith('/home.php'))throw new Error('home route '+p.url());if(await p.locator('.vf-home-command-head [data-open-add]:visible').count()!==0)throw new Error('duplicate Home head Add visible');if(await p.locator('.vf-app-topbar [data-open-add]:visible').count()!==1)throw new Error('desktop global Add authority');",
    'desktop single Add'
)
replace_once(
    "await post(common('V232 Home Channel','https://v232-home-channel.example.com','channels'));",
    "await post({...common('V232 Home Channel','https://v232-home-channel.example.com','channels'),is_favorite:'1'});",
    'second favorite fixture'
)
replace_once(
    "const totalText=await p.locator('.vf-home-status-grid a').filter({hasText:'全部资源'}).innerText();const totalNum=Number((totalText.match(/\\b(\\d+)\\b/)||[])[1]||0);if(totalNum<4)throw new Error('total '+totalText);const favText=await p.locator('.vf-home-status-grid a').filter({hasText:'我的收藏'}).innerText();const favNum=Number((favText.match(/\\b(\\d+)\\b/)||[])[1]||0);if(favNum<1)throw new Error('favorite '+favText);",
    "const totalText=await p.locator('.vf-home-status-grid a').filter({hasText:'全部资源'}).innerText();const totalNum=Number((totalText.match(/\\b(\\d+)\\b/)||[])[1]||0);if(totalNum<4)throw new Error('total '+totalText);const favText=await p.locator('.vf-home-status-grid a').filter({hasText:'我的收藏'}).innerText();const favNum=Number((favText.match(/\\b(\\d+)\\b/)||[])[1]||0);if(favNum!==2)throw new Error('favorite '+favText);const favSection=p.locator('.vf-home-main-column .vf-home-section').filter({has:p.locator('h2',{hasText:'我的收藏'})});if(await favSection.count()!==1)throw new Error('favorite launchpad missing');const favTitles=(await favSection.locator('.vf-home-recent-copy strong').allTextContents()).map(x=>x.trim());if(JSON.stringify(favTitles.slice(0,2))!==JSON.stringify(['V232 Home Navigation','V232 Home Channel']))throw new Error('favorite order '+JSON.stringify(favTitles));await favSection.locator('[data-edit-id]').first().click();await p.locator('[data-panel=\"detail\"]:visible').waitFor();await p.locator('[data-close-panel]:visible').first().click();",
    'favorite launchpad assertions'
)
replace_once(
    "await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw new Error('mobile command');",
    "await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw new Error('mobile command');if(await mp.locator('[data-open-add]:visible').count()!==1)throw new Error('mobile Add authority');if(!(await mp.locator('.vf-home-main-column').innerText()).includes('我的收藏'))throw new Error('mobile favorites missing');",
    'mobile polish assertions'
)
replace_once(
    "P01_V232_HOME_COMMAND_CENTER=PASS\n",
    "P01_V232_HOME_COMMAND_CENTER=PASS\nP01_V232_HOME_POLISH_SINGLE_FILE_DELTA=PASS\nP01_V232_HOME_DESKTOP_SINGLE_ADD_AUTHORITY=PASS\nP01_V232_HOME_FAVORITE_LAUNCHPAD=PASS\nP01_V232_HOME_FAVORITE_ORDER=PASS\nP01_V232_HOME_FAVORITE_EDIT=PASS\nP01_V232_HOME_MOBILE_SINGLE_ADD_AUTHORITY=PASS\n",
    'polish verdicts'
)
replace_once(
    "P01_V232_HOME_DESKTOP=PASS\\n",
    "P01_V232_HOME_DESKTOP=PASS\\nP01_V232_HOME_DESKTOP_SINGLE_ADD_AUTHORITY=PASS\\nP01_V232_HOME_FAVORITE_LAUNCHPAD=PASS\\nP01_V232_HOME_FAVORITE_ORDER=PASS\\nP01_V232_HOME_FAVORITE_EDIT=PASS\\nP01_V232_HOME_MOBILE_SINGLE_ADD_AUTHORITY=PASS\\n",
    'browser polish verdicts'
)

# Preserve the V7 baseline fence, plus prove this polish is exactly one file over current develop.
source_line = "printf '%s\\n' P01_V232_HOME_SOURCE_FENCE=PASS P01_V232_SIX_FILE_DELTA=PASS P01_V232_VERSION_UNCHANGED_2.31.0=PASS | tee \"$EVID/source.txt\"\n"
source_extra = source_line + "git -C \"$PRODUCT\" diff --name-only 23ada10bd7f76e21c48126a7ae29d8e32153f7fb...HEAD >\"$EVID/polish-diff.txt\"\ngrep -Fx src/app/FunctionalHome.php \"$EVID/polish-diff.txt\" >/dev/null\ntest \"$(wc -l < \"$EVID/polish-diff.txt\" | tr -d ' ')\" = 1\n"
replace_once(source_line, source_extra, 'single-file polish fence')

# V7 DB authority check for real recent usage, kept in the final V8 script.
browser_end = "node gate.mjs | tee \"$EVID/browser.txt\" | grep -Fx HOME_BROWSER_PASS\ncd /\n"
db_check = browser_end + "php -r 'require getenv(\"ROOT\").\"/app/bootstrap.php\";$db=vf_db();$s=$db->prepare(\"SELECT l.click_count,p.last_opened_at FROM links l LEFT JOIN resource_domain_profiles p ON p.link_id=l.id WHERE l.title=? AND l.lifecycle_state=\\\"active\\\" ORDER BY l.id DESC LIMIT 1\");$s->execute([\"V232 Home Navigation\"]);$r=$s->fetch(PDO::FETCH_ASSOC);if(!$r){fwrite(STDERR,\"OPEN_RECORD_MISSING\\n\");exit(2);}echo \"CLICK_COUNT=\".(int)($r[\"click_count\"]??0).PHP_EOL;echo \"LAST_OPENED_AT=\".(string)($r[\"last_opened_at\"]??\"\").PHP_EOL;' | tee \"$EVID/open-record.txt\"\ngrep -Eq '^CLICK_COUNT=[1-9][0-9]*$' \"$EVID/open-record.txt\"\ngrep -Eq '^LAST_OPENED_AT=.+$' \"$EVID/open-record.txt\"\n"
replace_once(browser_end, db_check, 'DB recent authority')

pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
bash "$TMP"
