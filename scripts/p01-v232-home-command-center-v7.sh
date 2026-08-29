#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v4.sh"
TMP="$(mktemp /tmp/p01-v232-home-v7.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
repls = []
repls.append((
"printf '%s\\n' src/app/FunctionalHome.php src/app/FunctionalWorkspaceShell.php src/app/SurfaceRepository.php src/assets/workspace-home.css src/home.php | sort >\"$EVID/expected-diff.txt\"",
"printf '%s\\n' src/app/FunctionalHome.php src/app/FunctionalWorkspaceShell.php src/app/SurfaceRepository.php src/assets/workspace-home.css src/home.php src/index.php | sort >\"$EVID/expected-diff.txt\""
))
repls.append((
"php -l \"$ROOT/app/SurfaceRepository.php\" >/dev/null",
"php -l \"$ROOT/app/SurfaceRepository.php\" >/dev/null\nphp -l \"$ROOT/index.php\" >/dev/null"
))
repls.append((
"P01_V232_FIVE_FILE_DELTA=PASS",
"P01_V232_SIX_FILE_DELTA=PASS"
))
repls.append((
"const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);",
"const d=await browser.newContext({viewport:{width:1440,height:960}});await login(d);const adminRoot=await d.request.get(base+'/',{maxRedirects:0});if(adminRoot.status()!==302||!(adminRoot.headers()['location']||'').includes('home.php'))throw new Error('admin root '+adminRoot.status()+' '+(adminRoot.headers()['location']||''));"
))
repls.append((
"const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const openedAsset=(state.assets||[]).find(x=>Number(x.id)===Number(a.id));if(!openedAsset)throw new Error('opened asset absent from Home payload');if(!String(openedAsset.last_surface_opened_at||''))throw new Error('navigation last_surface_opened_at missing');if(Number(openedAsset.click_count||0)<1)throw new Error('navigation click_count not incremented');",
"const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const rawAssets=state.assets||[];const assets=Array.isArray(rawAssets)?rawAssets:Object.values(rawAssets);const openedAsset=assets.find(x=>Number(x.id)===Number(a.id));if(!openedAsset)throw new Error('opened asset absent from Home payload');"
))
repls.append((
"P01_V232_ANONYMOUS_BOUNDARY=PASS\\n');console.log('HOME_BROWSER_PASS');",
"P01_V232_ADMIN_ROOT_HOME=PASS\\nP01_V232_ANONYMOUS_BOUNDARY=PASS\\n');console.log('HOME_BROWSER_PASS');"
))
for old,new in repls:
    if old not in src:
        raise SystemExit('V7 patch target not found: '+old[:80])
    src=src.replace(old,new,1)
needle="node gate.mjs | tee \"$EVID/browser.txt\" | grep -Fx HOME_BROWSER_PASS\ncd /\n"
insert="node gate.mjs | tee \"$EVID/browser.txt\" | grep -Fx HOME_BROWSER_PASS\ncd /\nphp -r 'require getenv(\"ROOT\").\"/app/bootstrap.php\";$db=vf_db();$s=$db->prepare(\"SELECT l.click_count,p.last_opened_at FROM links l LEFT JOIN resource_domain_profiles p ON p.link_id=l.id WHERE l.title=? AND l.lifecycle_state=\\\"active\\\" ORDER BY l.id DESC LIMIT 1\");$s->execute([\"V232 Home Navigation\"]);$r=$s->fetch(PDO::FETCH_ASSOC);if(!$r){fwrite(STDERR,\"OPEN_RECORD_MISSING\\n\");exit(2);}echo \"CLICK_COUNT=\".(int)($r[\"click_count\"]??0).PHP_EOL;echo \"LAST_OPENED_AT=\".(string)($r[\"last_opened_at\"]??\"\").PHP_EOL;' | tee \"$EVID/open-record.txt\"\ngrep -Eq '^CLICK_COUNT=[1-9][0-9]*$' \"$EVID/open-record.txt\"\ngrep -Eq '^LAST_OPENED_AT=.+$' \"$EVID/open-record.txt\"\n"
if needle not in src:
    raise SystemExit('V7 shell patch target not found')
src=src.replace(needle,insert,1)
verdict_needle="P01_V232_ANONYMOUS_PUBLIC_ROOT_UNCHANGED=PASS\n"
if verdict_needle not in src:
    raise SystemExit('V7 verdict patch target not found')
src=src.replace(verdict_needle,"P01_V232_ADMIN_ROOT_HOME=PASS\n"+verdict_needle,1)
pathlib.Path(sys.argv[2]).write_text(src,encoding='utf-8')
PY
bash "$TMP"
