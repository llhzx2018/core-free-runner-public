#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v4.sh"
TMP="$(mktemp /tmp/p01-v232-home-v6.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
old = "const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const openedAsset=(state.assets||[]).find(x=>Number(x.id)===Number(a.id));if(!openedAsset)throw new Error('opened asset absent from Home payload');if(!String(openedAsset.last_surface_opened_at||''))throw new Error('navigation last_surface_opened_at missing');if(Number(openedAsset.click_count||0)<1)throw new Error('navigation click_count not incremented');"
new = "const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const rawAssets=state.assets||[];const assets=Array.isArray(rawAssets)?rawAssets:Object.values(rawAssets);const openedAsset=assets.find(x=>Number(x.id)===Number(a.id));if(!openedAsset)throw new Error('opened asset absent from Home payload');"
if old not in src:
    raise SystemExit('V6 JS patch target not found')
src = src.replace(old, new, 1)
needle = "node gate.mjs | tee \"$EVID/browser.txt\" | grep -Fx HOME_BROWSER_PASS\ncd /\n"
insert = "node gate.mjs | tee \"$EVID/browser.txt\" | grep -Fx HOME_BROWSER_PASS\ncd /\nphp -r 'require getenv(\"ROOT\").\"/app/bootstrap.php\";$db=vf_db();$s=$db->prepare(\"SELECT l.click_count,p.last_opened_at FROM links l LEFT JOIN resource_domain_profiles p ON p.link_id=l.id WHERE l.title=? AND l.lifecycle_state=\\\"active\\\" ORDER BY l.id DESC LIMIT 1\");$s->execute([\"V232 Home Navigation\"]);$r=$s->fetch(PDO::FETCH_ASSOC);if(!$r){fwrite(STDERR,\"OPEN_RECORD_MISSING\\n\");exit(2);}echo \"CLICK_COUNT=\".(int)($r[\"click_count\"]??0).PHP_EOL;echo \"LAST_OPENED_AT=\".(string)($r[\"last_opened_at\"]??\"\").PHP_EOL;' | tee \"$EVID/open-record.txt\"\ngrep -Eq '^CLICK_COUNT=[1-9][0-9]*$' \"$EVID/open-record.txt\"\ngrep -Eq '^LAST_OPENED_AT=.+$' \"$EVID/open-record.txt\"\n"
if needle not in src:
    raise SystemExit('V6 shell patch target not found')
src = src.replace(needle, insert, 1)
pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
bash "$TMP"
