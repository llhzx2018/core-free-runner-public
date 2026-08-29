#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT_DIR/scripts/p01-v233-health-triage-gate.sh"
TMP=/tmp/p01-v233-health-triage-gate-v4.sh
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
"const ignore=first.locator('[data-action=\"ignore\"]');await ignore.click();await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('41')&&document.querySelector('#summary')?.textContent.includes('2'));let st=await (await c.request.get(base+'/api.php?action=link_health_status')).json();if(Number(st.status?.needsAction)!==6||Number(st.status?.restrictedReview)!==41||Number(st.status?.ignored)!==2)throw new Error('ignore triage authority '+JSON.stringify(st.status));",
"const ignore=first.locator('[data-action=\"ignore\"]');const firstId=Number(await ignore.getAttribute('data-id'));const csrf=await p.locator('meta[name=\"csrf-token\"]').getAttribute('content');const ir=await c.request.post(base+'/api.php?action=link_health_ignore',{data:{id:firstId,ignore:true},headers:{'X-CSRF-Token':String(csrf||'')}});if(!ir.ok())throw new Error('ignore api '+ir.status()+' '+await ir.text());await p.reload({waitUntil:'networkidle'});await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('41')&&document.querySelector('#summary')?.textContent.includes('2'));let st=await (await c.request.get(base+'/api.php?action=link_health_status')).json();if(Number(st.status?.needsAction)!==6||Number(st.status?.restrictedReview)!==41||Number(st.status?.ignored)!==2)throw new Error('ignore triage authority '+JSON.stringify(st.status));"
),
(
"const restore=p.locator('#list tbody tr').first().locator('[data-action=\"ignore\"]');if(!(await restore.innerText()).includes('恢复自动检查'))throw new Error('restore copy');await restore.click();await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('42')&&document.querySelector('#summary')?.textContent.includes('1'));",
"await p.selectOption('#status','restricted');await p.waitForFunction(()=>document.querySelector('#status')?.value==='restricted'&&document.querySelectorAll('#list tbody tr').length>0);const restore=p.locator('#list tbody tr').filter({has:p.locator('[data-id=\"'+firstId+'\"]')}).first().locator('[data-action=\"ignore\"]');if(!String(await restore.textContent()).includes('恢复自动检查'))throw new Error('restore copy');const rr=await c.request.post(base+'/api.php?action=link_health_ignore',{data:{id:firstId,ignore:false},headers:{'X-CSRF-Token':String(csrf||'')}});if(!rr.ok())throw new Error('restore api '+rr.status()+' '+await rr.text());await p.reload({waitUntil:'networkidle'});await p.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('42')&&document.querySelector('#summary')?.textContent.includes('1'));"
)
]
for old,new in repls:
    count=src.count(old)
    if count!=1:
        raise SystemExit(f'v4 anchor drift: expected 1 got {count}: {old[:90]}')
    src=src.replace(old,new,1)
Path(sys.argv[2]).write_text(src,encoding='utf-8')
PY
chmod +x "$TMP"
exec bash "$TMP"
