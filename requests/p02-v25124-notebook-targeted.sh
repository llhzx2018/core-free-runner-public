#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$PWD"; PRODUCT="$ROOT/product"; SITE="$RUNNER_TEMP/p02-v25124-notebook-probe"; COOKIE="$RUNNER_TEMP/p02-v25124-notebook-cookie.txt"; PORT=18226; BASE="http://127.0.0.1:$PORT"; PASSWORD="P02-V25124-NOTEBOOK-${GITHUB_RUN_ID}!"
cleanup(){ if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi; }
trap cleanup EXIT
rm -rf "$SITE" "$COOKIE"
bash "$PRODUCT/scripts/build-deploy-tree.sh" "$SITE"
php -d display_errors=0 -S "127.0.0.1:$PORT" -t "$SITE" >"$RUNNER_TEMP/p02-v25124-notebook-server.log" 2>&1 & PID=$!
for _ in $(seq 1 80); do curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$COOKIE" "$BASE/setup.php" > "$RUNNER_TEMP/setup.html"
TOKEN="$(python3 - "$RUNNER_TEMP/setup.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)"
test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" --data-urlencode "setup_csrf=$TOKEN" --data-urlencode "password=$PASSWORD" --data-urlencode "password_confirm=$PASSWORD" "$BASE/setup.php")" = "303"
export VF_UX_E2E_BASE_URL="$BASE" VF_UX_E2E_PASSWORD="$PASSWORD" VF_UX_E2E_VERSION="2.5.124"
cd "$PRODUCT"
cat > .p02-v25124-notebook-hover-probe.mjs <<'JS'
import { chromium } from 'playwright';
const base=process.env.VF_UX_E2E_BASE_URL,password=process.env.VF_UX_E2E_PASSWORD;
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const page=await context.newPage();
const assert=(v,m)=>{if(!v)throw new Error(m);};
await page.goto(base+'/',{waitUntil:'networkidle'});
if(await page.locator('[data-open-login]').count()){
  await page.evaluate(()=>openLogin());
  await page.locator('#loginForm input[name="password"]').fill(password);
  await page.locator('#loginSubmit').click();
  await page.waitForFunction(async()=>{const j=await (await fetch('/api.php?action=session',{cache:'no-store'})).json();return Boolean(j?.ok&&j?.site?.auth);});
}
const fixture=await page.evaluate(async()=>{
  const cat=await api('category_save',{method:'POST',body:{name:'V25124 Hover Probe',description:'',icon:'folder'}});
  const one=await api('content_save',{method:'POST',body:{category_id:cat.id,title:'V25124_HOVER_ONE',content:'one',content_mode:'article',content_format:'markdown',primary_action:'read',status:'active'}});
  const two=await api('content_save',{method:'POST',body:{category_id:cat.id,title:'V25124_HOVER_TWO',content:'two',content_mode:'article',content_format:'markdown',primary_action:'read',status:'active'}});
  state.contentView='notebook';localStorage.setItem('vftb-content-view','notebook');
  await selectCategory(cat.id);
  return {catId:cat.id,oneId:one.item.id,twoId:two.item.id};
});
await page.waitForSelector('[data-notebook-item="'+fixture.oneId+'"]');
await page.locator('[data-notebook-item="'+fixture.oneId+'"]').click();
await page.waitForFunction(id=>Number(state.readerItem?.id)===Number(id),fixture.oneId);
const quiet=page.locator('.notebook-title-entry:not(.active)').filter({has:page.locator('[data-notebook-item="'+fixture.twoId+'"]')}).first();
assert(await quiet.count()===1,'quiet row missing');
await page.mouse.move(1100,80);
await page.waitForTimeout(80);
const before=await quiet.evaluate(entry=>{
  const row=entry.querySelector('.notebook-title-row'),more=entry.querySelector('.notebook-title-more');
  const rs=getComputedStyle(row),ms=getComputedStyle(more),bs=getComputedStyle(document.body);
  return {bodyClass:document.body.className,width:innerWidth,entryHover:entry.matches(':hover'),rowHover:row.matches(':hover'),rowBg:rs.backgroundColor,moreOpacity:ms.opacity,hoverVar:bs.getPropertyValue('--v2537-hover').trim(),rowRect:row.getBoundingClientRect().toJSON?.()||null};
});
await quiet.locator('.notebook-title-row').hover();
const immediate=await quiet.evaluate(entry=>{
  const row=entry.querySelector('.notebook-title-row'),more=entry.querySelector('.notebook-title-more');
  return {entryHover:entry.matches(':hover'),rowHover:row.matches(':hover'),rowBg:getComputedStyle(row).backgroundColor,moreOpacity:getComputedStyle(more).opacity};
});
await page.waitForTimeout(220);
const after=await quiet.evaluate(entry=>{
  const row=entry.querySelector('.notebook-title-row'),more=entry.querySelector('.notebook-title-more');
  return {entryHover:entry.matches(':hover'),rowHover:row.matches(':hover'),rowBg:getComputedStyle(row).backgroundColor,moreOpacity:getComputedStyle(more).opacity};
});
console.log('HOVER_PROBE_BEFORE='+JSON.stringify(before));
console.log('HOVER_PROBE_IMMEDIATE='+JSON.stringify(immediate));
console.log('HOVER_PROBE_AFTER='+JSON.stringify(after));
assert(immediate.rowHover===true,'row :hover did not engage');
assert(immediate.rowBg!==before.rowBg,'direct row hover has no visual background affordance');
assert(Number(immediate.moreOpacity)>=.9,'direct row hover did not reveal More');
console.log('P02_V25124_NOTEBOOK_HOVER_TARGETED=PASS');
await browser.close();
JS
node .p02-v25124-notebook-hover-probe.mjs
rm -f .p02-v25124-notebook-hover-probe.mjs
echo P02_V25124_NOTEBOOK_TARGETED_BROWSER=PASS
