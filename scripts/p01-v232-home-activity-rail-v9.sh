#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v8.sh"
TMP="$(mktemp /tmp/p01-v232-home-v9.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')

old = '''source_extra = source_line + "git -C \\\"$PRODUCT\\\" diff --name-only 23ada10bd7f76e21c48126a7ae29d8e32153f7fb...HEAD >\\\"$EVID/polish-diff.txt\\\"\\ngrep -Fx src/app/FunctionalHome.php \\\"$EVID/polish-diff.txt\\\" >/dev/null\\ntest \\\"$(wc -l < \\\"$EVID/polish-diff.txt\\\" | tr -d ' ')\\\" = 1\\n"'''
new = '''source_extra = source_line + "git -C \\\"$PRODUCT\\\" diff --name-only ac628d91c21dd29c9b5518997ebdf56228750e32...HEAD | sort >\\\"$EVID/activity-diff.txt\\\"\\nprintf '%s\\\\n' src/app/FunctionalHome.php src/assets/workspace-home.css | sort >\\\"$EVID/activity-expected-diff.txt\\\"\\ndiff -u \\\"$EVID/activity-expected-diff.txt\\\" \\\"$EVID/activity-diff.txt\\\"\\n"'''
if src.count(old) != 1:
    raise SystemExit('V9 activity diff fence target drift')
src = src.replace(old, new, 1)

needle = "pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')\n"
insert = r'''# V9 Activity Rail assertions, applied to the final generated V8 gate script.
replace_once(
    "await p.screenshot({path:e+'/home-desktop.png',fullPage:true});",
    "const activity=p.locator('.vf-home-activity-section');if(await activity.count()!==1)throw new Error('activity rail missing');if(await p.locator('.vf-home-action-section:visible').count()!==0)throw new Error('zero-pending action placeholder visible');const activityItems=activity.locator('.vf-home-activity-item');if(await activityItems.count()!==5)throw new Error('activity count '+await activityItems.count());const activityActions=(await activity.locator('.vf-home-activity-copy b').allTextContents()).map(x=>x.trim());if(activityActions.some(x=>x!=='新增'))throw new Error('activity actions '+JSON.stringify(activityActions));const activityObjects=(await activity.locator('.vf-home-activity-copy small').allTextContents()).map(x=>x.trim());const expectedActivity=['V232 Home Topic','V232 Home Watch','V232 Home Channel','V232 Home Navigation'];if(JSON.stringify(activityObjects.slice(0,4))!==JSON.stringify(expectedActivity))throw new Error('activity order '+JSON.stringify(activityObjects));const activityText=await activity.innerText();if(activityText.includes('create')||activityText.includes('link #'))throw new Error('internal history terminology leaked '+activityText);await p.screenshot({path:e+'/home-desktop.png',fullPage:true});",
    'activity rail browser assertions'
)
replace_once(
    "if(!(await mp.locator('.vf-home-main-column').innerText()).includes('我的收藏'))throw new Error('mobile favorites missing');",
    "if(!(await mp.locator('.vf-home-main-column').innerText()).includes('我的收藏'))throw new Error('mobile favorites missing');if(!(await mp.locator('.vf-home-rail').innerText()).includes('最近操作'))throw new Error('mobile activity missing');",
    'mobile activity assertion'
)
replace_once(
    "P01_V232_HOME_COMMAND_CENTER=PASS\\n",
    "P01_V232_HOME_COMMAND_CENTER=PASS\\nP01_V232_HOME_ACTIVITY_TWO_FILE_DELTA=PASS\\nP01_V232_HOME_ACTIVITY_REAL_HISTORY=PASS\\nP01_V232_HOME_ACTIVITY_ORDER=PASS\\nP01_V232_HOME_ACTIVITY_HUMAN_READABLE=PASS\\nP01_V232_HOME_ZERO_PENDING_NO_PLACEHOLDER=PASS\\nP01_V232_HOME_ACTIVITY_MOBILE=PASS\\n",
    'activity verdicts'
)
replace_once(
    "P01_V232_HOME_DESKTOP=PASS\\\\n",
    "P01_V232_HOME_DESKTOP=PASS\\\\nP01_V232_HOME_ACTIVITY_REAL_HISTORY=PASS\\\\nP01_V232_HOME_ACTIVITY_ORDER=PASS\\\\nP01_V232_HOME_ACTIVITY_HUMAN_READABLE=PASS\\\\nP01_V232_HOME_ZERO_PENDING_NO_PLACEHOLDER=PASS\\\\nP01_V232_HOME_ACTIVITY_MOBILE=PASS\\\\n",
    'activity browser verdicts'
)

'''
if src.count(needle) != 1:
    raise SystemExit('V9 wrapper insertion target drift')
src = src.replace(needle, insert + needle, 1)
pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
bash "$TMP"
