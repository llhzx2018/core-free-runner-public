#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT_DIR/scripts/p01-v233-health-triage-gate.sh"
TMP=/tmp/p01-v233-health-triage-gate-v3.sh
python3 - "$SRC" "$TMP" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text(encoding='utf-8')
repls=[
(
"await p.selectOption('#status','restricted');await p.waitForFunction(()=>document.querySelector('#list')?.textContent.includes('V233 Health Restricted'));const first=p.locator('#list tbody tr').first();",
"await p.selectOption('#status','restricted');await p.waitForFunction(()=>{const rows=[...document.querySelectorAll('#list tbody tr')];const text=document.querySelector('#list')?.textContent||'';return document.querySelector('#status')?.value==='restricted'&&rows.length>0&&rows.every(row=>row.textContent.includes('访问受限'))&&!text.includes('V233 Health Suspected');});const first=p.locator('#list tbody tr').first();"
),
(
"const ignore=first.locator('[data-action=\"ignore\"]');await ignore.click();",
"const more=first.getByRole('button',{name:'更多',exact:true});if(await more.count())await more.click();const ignore=first.locator('[data-action=\"ignore\"]');await ignore.click();"
),
(
"const restore=p.locator('#list tbody tr').first().locator('[data-action=\"ignore\"]');if(!(await restore.innerText()).includes('恢复自动检查'))throw new Error('restore copy');await restore.click();",
"const restoreRow=p.locator('#list tbody tr').first();const restoreMore=restoreRow.getByRole('button',{name:'更多',exact:true});if(await restoreMore.count())await restoreMore.click();const restore=restoreRow.locator('[data-action=\"ignore\"]');if(!(await restore.innerText()).includes('恢复自动检查'))throw new Error('restore copy');await restore.click();"
)
]
for old,new in repls:
    count=src.count(old)
    if count!=1:
        raise SystemExit(f'v3 anchor drift: expected 1 got {count}: {old[:80]}')
    src=src.replace(old,new,1)
Path(sys.argv[2]).write_text(src,encoding='utf-8')
PY
chmod +x "$TMP"
exec bash "$TMP"
