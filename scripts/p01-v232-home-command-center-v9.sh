#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v8.sh"
TMP="$(mktemp /tmp/p01-v232-home-v9-wrapper.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')

# V9 keeps the proven V8 transformer, but updates its incremental authority
# from the one-file polish to the current two-file Activity/Health rail.
src = src.replace('P01_V232_HOME_POLISH_SINGLE_FILE_DELTA=PASS', 'P01_V232_HOME_ACTIVITY_TWO_FILE_DELTA=PASS')
old = '''source_extra = source_line + "git -C \\\"$PRODUCT\\\" diff --name-only 23ada10bd7f76e21c48126a7ae29d8e32153f7fb...HEAD >\\\"$EVID/polish-diff.txt\\\"\\ngrep -Fx src/app/FunctionalHome.php \\\"$EVID/polish-diff.txt\\\" >/dev/null\\ntest \\\"$(wc -l < \\\"$EVID/polish-diff.txt\\\" | tr -d ' ')\\\" = 1\\n"'''
new = '''source_extra = source_line + "git -C \\\"$PRODUCT\\\" diff --name-only ac628d91c21dd29c9b5518997ebdf56228750e32...HEAD | sort >\\\"$EVID/activity-diff.txt\\\"\\nprintf '%s\\\\n' src/app/FunctionalHome.php src/assets/workspace-home.css | sort >\\\"$EVID/activity-expected.txt\\\"\\ndiff -u \\\"$EVID/activity-expected.txt\\\" \\\"$EVID/activity-diff.txt\\\"\\n"'''
if old not in src:
    raise SystemExit('V9 incremental fence anchor drift')
src = src.replace(old, new, 1)

extra = r'''
# V9 Activity/Health transforms on the final generated shell.
replace_once(
    "cleanup(){ rm -f \"$ROOT/__p01_v232_home_gate_seed.php\"; if test -f \"$PIDFILE\"; then kill \"$(cat \"$PIDFILE\")\" >/dev/null 2>&1 || true; fi; }",
    "cleanup(){ rm -f \"$ROOT/__p01_v232_home_gate_seed.php\" \"$ROOT/__p01_v232_home_health_fixture.php\"; if test -f \"$PIDFILE\"; then kill \"$(cat \"$PIDFILE\")\" >/dev/null 2>&1 || true; fi; }",
    'health fixture cleanup'
)
replace_once(
    "php -l \"$ROOT/__p01_v232_home_gate_seed.php\" >/dev/null\n\n# 4. Real browser + authenticated create/open + privacy boundary.",
    "php -l \"$ROOT/__p01_v232_home_gate_seed.php\" >/dev/null\ncat >\"$ROOT/__p01_v232_home_health_fixture.php\" <<'PHP'\n<?php\ndeclare(strict_types=1);\nrequire __DIR__ . '/app/bootstrap.php';\nheader('Content-Type: text/plain; charset=utf-8');header('Cache-Control: no-store');\nif (!vf_is_admin()) { http_response_code(403); echo \"FORBIDDEN\\n\"; exit; }\ntry { $id=max(1,(int)($_GET['id']??0)); $r=(new VfLinkHealth(vf_db()))->confirmInvalid($id,true); echo \"HEALTH_CONFIRMED=\".(int)($r['status']['confirmed']??0).\"\\n\"; }\nfinally { @unlink(__FILE__); }\nPHP\nphp -l \"$ROOT/__p01_v232_home_health_fixture.php\" >/dev/null\n\n# 4. Real browser + authenticated create/open + privacy boundary.",
    'health fixture endpoint'
)
replace_once(
    "const opened=await d.request.get(base+'/surface-open.php?id='+a.id,{maxRedirects:0});if(![302,303].includes(opened.status()))throw new Error('tracked open '+opened.status());",
    "const opened=await d.request.get(base+'/surface-open.php?id='+a.id,{maxRedirects:0});if(![302,303].includes(opened.status()))throw new Error('tracked open '+opened.status());const health=await d.request.get(base+'/__p01_v232_home_health_fixture.php?id='+a.id);if(health.status()!==200||!(await health.text()).includes('HEALTH_CONFIRMED=1'))throw new Error('health fixture');",
    'confirmed health fixture'
)
replace_once(
    "await p.goto(base+'/home.php',{waitUntil:'networkidle'});const text=await p.locator('.vf-home-command').innerText();",
    "await p.goto(base+'/home.php',{waitUntil:'networkidle'});if(await p.locator('.vf-home-action-section:visible').count()!==0)throw new Error('zero-pending action placeholder visible');const activity=p.locator('.vf-home-activity-section');if(await activity.count()!==1)throw new Error('activity section missing');const activityText=await activity.innerText();if(!activityText.includes('最近操作')||!activityText.includes('新增')||!activityText.includes('V232 Home Topic'))throw new Error('activity content '+activityText);if(!/(刚刚|分钟前|小时前|天前)/.test(activityText))throw new Error('activity relative time missing '+activityText);if(await activity.locator('.vf-home-activity-item').count()!==5)throw new Error('activity cap');const healthSection=p.locator('.vf-home-health-section');if(await healthSection.count()!==1)throw new Error('health section missing');const healthText=await healthSection.innerText();if(!healthText.includes('有 1 个网址需要检查')||!healthText.includes('确认失效'))throw new Error('health content '+healthText);const text=await p.locator('.vf-home-command').innerText();",
    'activity and health browser assertions'
)
replace_once(
    "test ! -e \"$ROOT/__p01_v232_home_gate_seed.php\"",
    "test ! -e \"$ROOT/__p01_v232_home_gate_seed.php\"\ntest ! -e \"$ROOT/__p01_v232_home_health_fixture.php\"",
    'fixture self deletion'
)
replace_once(
    "P01_V232_HOME_COMMAND_CENTER=PASS\n",
    "P01_V232_HOME_COMMAND_CENTER=PASS\nP01_V232_HOME_ACTIVITY_RAIL=PASS\nP01_V232_HOME_ACTIVITY_REAL_HISTORY=PASS\nP01_V232_HOME_ACTIVITY_RELATIVE_TIME=PASS\nP01_V232_HOME_HEALTH_SIGNAL=PASS\nP01_V232_HOME_ZERO_PENDING_NO_PLACEHOLDER=PASS\n",
    'activity verdicts'
)
replace_once(
    "P01_V232_HOME_DESKTOP_SINGLE_ADD_AUTHORITY=PASS\\n",
    "P01_V232_HOME_DESKTOP_SINGLE_ADD_AUTHORITY=PASS\\nP01_V232_HOME_ACTIVITY_RAIL=PASS\\nP01_V232_HOME_ACTIVITY_REAL_HISTORY=PASS\\nP01_V232_HOME_ACTIVITY_RELATIVE_TIME=PASS\\nP01_V232_HOME_HEALTH_SIGNAL=PASS\\nP01_V232_HOME_ZERO_PENDING_NO_PLACEHOLDER=PASS\\n",
    'browser activity verdicts'
)
'''
anchor = "pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')\n"
if src.count(anchor) != 1:
    raise SystemExit('V9 transformer tail anchor drift')
src = src.replace(anchor, extra + "\n" + anchor, 1)
pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
bash "$TMP"
