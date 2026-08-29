#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v7.sh"
TMP="$(mktemp /tmp/p01-v232-home-v8.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
repls=[
("await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(!p.url().endsWith('/home.php'))throw new Error('home route '+p.url());",
 "await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(!p.url().endsWith('/home.php'))throw new Error('home route '+p.url());if(await p.locator('.vf-home-command-head [data-open-add]:visible').count()!==0)throw new Error('duplicate Home head Add visible');if(await p.locator('.vf-app-topbar [data-open-add]:visible').count()!==1)throw new Error('desktop global Add authority');"),
("await post(common('V232 Home Channel','https://v232-home-channel.example.com','channels'));",
 "await post({...common('V232 Home Channel','https://v232-home-channel.example.com','channels'),is_favorite:'1'});"),
("const fav=await p.locator('.vf-home-status-grid a').filter({hasText:'我的收藏'}).innerText();if(!/\\b1\\b/.test(fav))throw new Error('favorite '+fav);",
 "const fav=await p.locator('.vf-home-status-grid a').filter({hasText:'我的收藏'}).innerText();if(!/\\b2\\b/.test(fav))throw new Error('favorite '+fav);const favSection=p.locator('.vf-home-main-column .vf-home-section').filter({has:p.locator('h2',{hasText:'我的收藏'})});if(await favSection.count()!==1)throw new Error('favorite launchpad missing');const favTitles=(await favSection.locator('.vf-home-recent-copy strong').allTextContents()).map(x=>x.trim());if(JSON.stringify(favTitles.slice(0,2))!==JSON.stringify(['V232 Home Navigation','V232 Home Channel']))throw new Error('favorite order '+JSON.stringify(favTitles));await favSection.locator('[data-edit-id]').first().click();await p.locator('[data-panel=\"edit\"]:visible').waitFor();await p.locator('[data-close-panel]:visible').first().click();"),
("await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw new Error('mobile command');",
 "await mp.goto(base+'/home.php',{waitUntil:'networkidle'});if(await mp.locator('.vf-home-mobile-command:visible').count()!==1)throw new Error('mobile command');if(await mp.locator('[data-open-add]:visible').count()!==1)throw new Error('mobile Add authority');if(!(await mp.locator('.vf-home-main-column').innerText()).includes('我的收藏'))throw new Error('mobile favorites missing');"),
("P01_V232_HOME_COMMAND_CENTER=PASS\n",
 "P01_V232_HOME_COMMAND_CENTER=PASS\nP01_V232_HOME_POLISH_SINGLE_FILE_DELTA=PASS\nP01_V232_HOME_DESKTOP_SINGLE_ADD_AUTHORITY=PASS\nP01_V232_HOME_FAVORITE_LAUNCHPAD=PASS\nP01_V232_HOME_FAVORITE_ORDER=PASS\nP01_V232_HOME_FAVORITE_EDIT=PASS\nP01_V232_HOME_MOBILE_SINGLE_ADD_AUTHORITY=PASS\n")
]
for old,new in repls:
    if old not in src:
        raise SystemExit('V8 patch target missing: '+old[:100])
    src=src.replace(old,new,1)
# Additional exact delta vs current develop while retaining V2.31 baseline six-file fence.
needle="printf '%s\\n' P01_V232_HOME_SOURCE_FENCE=PASS P01_V232_SIX_FILE_DELTA=PASS P01_V232_VERSION_UNCHANGED_2.31.0=PASS | tee \"$EVID/source.txt\"\n"
insert=needle+"git -C \"$PRODUCT\" diff --name-only 23ada10bd7f76e21c48126a7ae29d8e32153f7fb...HEAD >\"$EVID/polish-diff.txt\"\ngrep -Fx src/app/FunctionalHome.php \"$EVID/polish-diff.txt\" >/dev/null\ntest \"$(wc -l < \"$EVID/polish-diff.txt\" | tr -d ' ')\" = 1\n"
if needle not in src: raise SystemExit('V8 source fence anchor missing')
src=src.replace(needle,insert,1)
pathlib.Path(sys.argv[2]).write_text(src,encoding='utf-8')
PY
bash "$TMP"
