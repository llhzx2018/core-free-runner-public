#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-command-center-v4.sh"
TMP="$(mktemp /tmp/p01-v232-home-v5.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
old = "const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const openedAsset=(state.assets||[]).find(x=>Number(x.id)===Number(a.id));"
new = "const state=await p.locator('#vf-workspace-data').evaluate(n=>JSON.parse(n.textContent||'{}'));const rawAssets=state.assets||[];const assets=Array.isArray(rawAssets)?rawAssets:Object.values(rawAssets);const openedAsset=assets.find(x=>Number(x.id)===Number(a.id));"
if old not in src:
    raise SystemExit('V5 patch target not found')
src = src.replace(old, new, 1)
pathlib.Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
bash "$TMP"
