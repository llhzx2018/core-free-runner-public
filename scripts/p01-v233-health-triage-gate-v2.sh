#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT_DIR/scripts/p01-v233-health-triage-gate.sh"
TMP=/tmp/p01-v233-health-triage-gate-v2.sh
python3 - "$SRC" "$TMP" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text(encoding='utf-8')
old="await p.selectOption('#status','restricted');await p.waitForFunction(()=>document.querySelector('#list')?.textContent.includes('V233 Health Restricted'));const first=p.locator('#list tbody tr').first();"
new="await p.selectOption('#status','restricted');await p.waitForFunction(()=>{const rows=[...document.querySelectorAll('#list tbody tr')];const text=document.querySelector('#list')?.textContent||'';return document.querySelector('#status')?.value==='restricted'&&rows.length>0&&rows.every(row=>row.textContent.includes('访问受限'))&&!text.includes('V233 Health Suspected');});const first=p.locator('#list tbody tr').first();"
if src.count(old)!=1:
    raise SystemExit(f'restricted wait anchor drift: {src.count(old)}')
Path(sys.argv[2]).write_text(src.replace(old,new,1),encoding='utf-8')
PY
chmod +x "$TMP"
exec bash "$TMP"
