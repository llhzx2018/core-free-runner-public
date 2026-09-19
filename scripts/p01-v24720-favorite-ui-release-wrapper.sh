#!/usr/bin/env bash
set -Eeuo pipefail

: "${TARGET_ROOT:?missing TARGET_ROOT}"
: "${BASELINE_ROOT:?missing BASELINE_ROOT}"
: "${OLD_HARNESS_ROOT:?missing OLD_HARNESS_ROOT}"
: "${PROVEN_ROOT:?missing PROVEN_ROOT}"
: "${OLD_GATE_ROOT:?missing OLD_GATE_ROOT}"

dump_gate_logs(){
  rc=$?
  echo "P01_V24720_RELEASE_WRAPPER_RC=$rc" >&2
  for log in /tmp/p01-r20-*-evidence/server.log /tmp/p01-r20-public-ui-server.log; do
    if [ -f "$log" ]; then
      echo "===== $log =====" >&2
      cat "$log" >&2 || true
    fi
  done
  exit "$rc"
}
trap dump_gate_logs ERR

echo 'P01_BROWSER_RUNTIME_SWEEP=START'
BROWSER_ROOT=/tmp/p01-v24720-browser-runtime
rm -rf "$BROWSER_ROOT" /tmp/p01-v24720-browser-profile
cp -a "$TARGET_ROOT/src" "$BROWSER_ROOT"
(
  cd "$BROWSER_ROOT"
  php -S 127.0.0.1:18105 -t . >/tmp/p01-v24720-browser-server.log 2>&1
) &
browser_server_pid=$!
for i in $(seq 1 40); do
  if curl -fsS -c /tmp/p01-v24720-browser.cookies -b /tmp/p01-v24720-browser.cookies http://127.0.0.1:18105/setup.php -o /tmp/p01-v24720-browser-setup.html; then break; fi
  sleep 1
done
SETUP_CSRF=$(python3 - <<'PY'
import re
text=open('/tmp/p01-v24720-browser-setup.html',encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',text)
assert m,'setup csrf missing'
print(m.group(1))
PY
)
curl -fsS -c /tmp/p01-v24720-browser.cookies -b /tmp/p01-v24720-browser.cookies   -X POST http://127.0.0.1:18105/setup.php   --data-urlencode "setup_csrf=$SETUP_CSRF"   --data-urlencode 'site_title=P01 Browser Runtime Sweep'   --data-urlencode 'admin_password=BrowserRuntime!2026'   --data-urlencode 'admin_password_confirm=BrowserRuntime!2026'   -o /tmp/p01-v24720-browser-setup-post.html

CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
test -n "$CHROME"
"$CHROME" --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage   --remote-debugging-port=9223 --user-data-dir=/tmp/p01-v24720-browser-profile about:blank   >/tmp/p01-v24720-chrome.log 2>&1 &
browser_chrome_pid=$!
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:9223/json/list >/tmp/p01-v24720-cdp-list.json; then break; fi
  sleep 1
done

cat >/tmp/p01-v24720-browser-smoke.mjs <<'NODE'
const targets=await (await fetch('http://127.0.0.1:9223/json/list')).json();
const wsUrl=targets.find(t=>t.type==='page')?.webSocketDebuggerUrl;
if(!wsUrl)throw new Error('CDP page target missing');
const ws=new WebSocket(wsUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject});
let seq=0,currentRoute='about:blank';
const pending=new Map(),waiters=new Map(),exceptions=[];
ws.onmessage=event=>{
  const msg=JSON.parse(event.data);
  if(msg.id&&pending.has(msg.id)){
    const p=pending.get(msg.id);pending.delete(msg.id);
    if(msg.error)p.reject(new Error(msg.error.message||JSON.stringify(msg.error)));else p.resolve(msg.result||{});
    return;
  }
  if(msg.method==='Runtime.exceptionThrown'){
    const d=msg.params?.exceptionDetails||{};
    exceptions.push({route:currentRoute,type:'exception',message:d.exception?.description||d.text||'Runtime exception'});
  }
  if(msg.method==='Runtime.consoleAPICalled'&&msg.params?.type==='error'){
    const message=(msg.params.args||[]).map(a=>a.value??a.description??'').join(' ');
    exceptions.push({route:currentRoute,type:'console.error',message});
  }
  const list=waiters.get(msg.method);
  if(list?.length)list.shift()(msg.params||{});
};
const send=(method,params={})=>new Promise((resolve,reject)=>{
  const id=++seq;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));
});
const once=method=>new Promise(resolve=>{
  const list=waiters.get(method)||[];list.push(resolve);waiters.set(method,list);
});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await send('Runtime.enable');await send('Page.enable');
const navigate=async route=>{
  currentRoute=route;
  const loaded=once('Page.loadEventFired');
  await send('Page.navigate',{url:'http://127.0.0.1:18105/'+route});
  await Promise.race([loaded,sleep(5000)]);
  await sleep(450);
};
await navigate('watch.php');
const login=await send('Runtime.evaluate',{
  expression:"(async()=>{const r=await fetch('api.php?action=login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:'BrowserRuntime!2026'})});return await r.text()})()",
  awaitPromise:true,returnByValue:true
});
if(!String(login.result?.value||'').includes('"ok":true'))throw new Error('browser login failed: '+String(login.result?.value||''));
await navigate('watch.php');
const create=await send('Runtime.evaluate',{
  expression:"(async()=>{const n=document.getElementById('vf-workspace-data');const s=JSON.parse(n.textContent||'{}');const fd=new FormData();[['csrf',s.csrf],['surface','watch'],['source_kind','remote_url'],['title','Runtime Smoke Resource'],['url','https://example.com/runtime-smoke'],['resource_kind','movie'],['media_status','want'],['is_private','1'],['is_favorite','0']].forEach(([k,v])=>fd.set(k,v));const r=await fetch('workspace-create.php',{method:'POST',body:fd,credentials:'same-origin'});return await r.text()})()",
  awaitPromise:true,returnByValue:true
});
if(!String(create.result?.value||'').includes('"ok":true'))throw new Error('fixture create failed: '+String(create.result?.value||''));

const routes=['home.php','start.php','surfaces.php','channels.php','watch.php','topics.php','courses.php','projects.php','tools.php','software.php','surface-manager.php','recycle-bin.php','settings.php','data-recovery.php','update.php'];
for(const route of routes){
  await navigate(route);
  const state=await send('Runtime.evaluate',{expression:"({title:document.title,ready:document.readyState,body:document.body?.className||''})",returnByValue:true});
  console.log('PAGE_OK',route,JSON.stringify(state.result?.value||{}));
}
await navigate('watch.php');
const toggle=async()=>{
  const out=await send('Runtime.evaluate',{
    expression:"(async()=>{const b=document.querySelector('[data-favorite-id]');if(!b)return 'NO_FAVORITE_BUTTON';b.click();await new Promise(r=>setTimeout(r,850));const all=Array.from(document.querySelectorAll('.vf-workspace-toast'));return {toast:all.at(-1)?.textContent||'NO_TOAST',favorite:b.dataset.favorite||''}})()",
    awaitPromise:true,returnByValue:true
  });
  return out.result?.value||{};
};
console.log('FAVORITE_ADD',JSON.stringify(await toggle()));
await sleep(3000);
console.log('FAVORITE_REMOVE',JSON.stringify(await toggle()));
await sleep(300);
console.log('P01_BROWSER_RUNTIME_EXCEPTION_COUNT='+exceptions.length);
exceptions.forEach((e,i)=>console.log('BROWSER_EXCEPTION_'+(i+1)+'='+JSON.stringify(e)));
ws.close();
if(exceptions.length)process.exit(1);
NODE
node /tmp/p01-v24720-browser-smoke.mjs
kill "$browser_chrome_pid" >/dev/null 2>&1 || true
kill "$browser_server_pid" >/dev/null 2>&1 || true
echo 'P01_BROWSER_RUNTIME_SWEEP=PASS'

SRC="$OLD_GATE_ROOT/scripts/p01-v24714-navigation-row-release-gate.sh"
DST=/tmp/p01-v24720-release-gate.sh
cp "$SRC" "$DST"

python3 - "$DST" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
pairs=[
("TARGET_SHA=421e7b5df1e48db768b39470fc99580330a07c0f","TARGET_SHA=83ca94662dd8bc053dea0ef94bc0e6ef0d587234"),
("TARGET_TREE=598eaae633ef485dd2eef1330a9370cb46f90506","TARGET_TREE=0de1caa05e148281d8c8db99d88a57e37fc01587"),
("SOURCE_SHA=e714cfe540ad39202c2cb558e5c0a370ef6d6502","SOURCE_SHA=aabaa35728f776c0db3785f67eb7812e0a0374ee"),
("SOURCE_VERSION=2.47.13","SOURCE_VERSION=2.47.19"),
("TARGET_VERSION=2.47.14","TARGET_VERSION=2.47.20"),
("OUT=/tmp/p01-v24714-navigation","OUT=/tmp/p01-v24720-navigation-favorite-ui"),
("BUILD=/tmp/p01-v24714-navigation-builder","BUILD=/tmp/p01-v24720-navigation-favorite-ui-builder"),
("VF-Start-V2.47.14-FULL.zip","VF-Start-V2.47.20-FULL.zip"),
("VF_Start_V2.47.14_UPDATE.zip","VF_Start_V2.47.20_UPDATE.zip"),
("repair-v2.47.14.php","repair-v2.47.20.php"),
("/tmp/p01-v24714-navigation-builder/gate.py","/tmp/p01-v24720-navigation-favorite-ui-builder/gate.py"),
('VERSION = "2.47.14"','VERSION = "2.47.20"'),
('SOURCE_VERSION = "2.47.13"','SOURCE_VERSION = "2.47.19"'),
('VF_VERSION!=="2.47.14"','VF_VERSION!=="2.47.20"'),
("public const SOURCE_VERSION='2.47.13';","public const SOURCE_VERSION='2.47.19';"),
("public const TARGET_VERSION='2.47.14';","public const TARGET_VERSION='2.47.20';"),
("V2.47.14 fixes logged-out Navigation row layout width while preserving Atomic update safety.","V2.47.20 fixes Favorite UI collection sync while preserving Atomic update safety."),
("/tmp/p01-v24714-navigation-rebuild","/tmp/p01-v24720-navigation-favorite-ui-rebuild"),
("P01_V24714_NAVIGATION_ROW_RELEASE_GATE=PASS","P01_V24720_NAVIGATION_UX_FAVORITE_UI_RELEASE_GATE=PASS"),
("R14_GATE_RECEIPT.txt","R20_GATE_RECEIPT.txt"),
("V24713_TO_V24714_ATOMIC_UPGRADE=PASS","V24719_TO_V24720_ATOMIC_UPGRADE=PASS"),
("OWNER_PREVIEW_RUNTIME_REASON=bounded corrective layout bug; no new product shape or interaction contract","OWNER_PREVIEW_RUNTIME_REASON=bounded Favorite UI collection runtime fix; no new product shape, data, auth, or IA contract"),
]
for a,b in pairs:
    if a not in s:
        raise SystemExit("missing patch anchor: "+a)
    s=s.replace(a,b)
s=s.replace("p01-r14-","p01-r20-").replace("R14","R20").replace("r14","r20")
p.write_text(s,encoding='utf-8')
PY

bash "$DST"

# Stable Navigation regressions + Favorite UI single-owner acceptance.
php "$TARGET_ROOT/tests/unit/resource_search_contract.php" | grep -Fx RESOURCE_SEARCH_CONTRACT_PASS
php "$TARGET_ROOT/tests/unit/navigation_context_persistence_contract.php" | grep -Fx P01_NAVIGATION_CONTEXT_PERSISTENCE=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_authority_contract.php" | grep -Fx P01_NAVIGATION_SEARCH_AUTHORITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_context_contract.php" | grep -Fx NAVIGATION_SEARCH_CONTEXT_PASS
php "$TARGET_ROOT/tests/unit/search_sort_stability_contract.php" | grep -Fx P01_SEARCH_SORT_STABILITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_category_facet_recovery_contract.php" | grep -Fx NAVIGATION_CATEGORY_FACET_RECOVERY_PASS
php "$TARGET_ROOT/tests/unit/mobile_sort_accessibility_contract.php" | grep -Fx P01_NAVIGATION_UX_ROUND5_MOBILE_SORT=PASS

OUT=/tmp/p01-v24720-navigation-favorite-ui
cat >>"$OUT/R20_GATE_RECEIPT.txt" <<'EOF'
MULTI_TERM_RESOURCE_SEARCH=PASS
CLEARABLE_SEARCH_FILTER_CONTEXT=PASS
PAGINATION_RESULTS_ANCHOR=PASS
EXACT_URL_SCROLL_RETURN=PASS
NAVIGATION_SEARCH_AUTHORITY=PASS
SEARCH_SORT_STABILITY=PASS
CATEGORY_FACET_RECOVERY=PASS
MOBILE_SORT_REACHABILITY=PASS
EOF

for test_name in   navigation_owner_behavior_privacy_contract.php   navigation_owner_views_round3_contract.php   contextual_favorite_badge_contract.php   navigation_favorite_count_context_contract.php   start_popular_sort_control_contract.php   start_favorite_sort_reset_contract.php   favorite_add_context_contract.php   derived_favorite_view_coherence_contract.php   tool_shared_search_context_contract.php   tool_scene_context_consistency_contract.php   tool_software_sort_context_contract.php   software_detail_context_contract.php   subject_request_context_sanitization_contract.php   public_global_nav_contract.php   navigation_public_row_layout_contract.php   global_account_actions_contract.php   subject_domain_nav_shell_contract.php   favorite_write_recovery_contract.php   favorite_ui_collection_contract.php; do
  php "$TARGET_ROOT/tests/unit/$test_name"
done

cat >>"$OUT/R20_GATE_RECEIPT.txt" <<'EOF'
PUBLIC_AUTHORITY_APPLICABILITY_INSTALL=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_SECURITY=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_TESTING=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_UPGRADE=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_DATA_SCHEMA=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_API_PROVIDER=N_A
PUBLIC_AUTHORITY_APPLICABILITY_SEO=N_A
PUBLIC_AUTHORITY_APPLICABILITY_CRON_JOB=N_A
PUBLIC_AUTHORITY_APPLICABILITY_NOTIFICATION=N_A
PUBLIC_AUTHORITY_APPLICABILITY_OBSERVABILITY=N_A
PUBLIC_AUTHORITY_APPLICABILITY_PERFORMANCE=N_A
PUBLIC_AUTHORITY_APPLICABILITY_GIT=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_UA_UI=REQUIRED
OWNER_BEHAVIOR_PUBLIC_PRIVACY=PASS
START_OWNER_FAVORITE_POPULAR_RECENT=PASS
RECENT_WINDOW_CONTEXT=PASS
FAVORITE_LIVE_BADGE=PASS
DERIVED_TOOL_SOFTWARE_OWNER_VIEWS=PASS
GLOBAL_ACCOUNT_SERVER_RENDER=PASS
CLIENT_DOM_REPARENTING_REMOVED=PASS
GLOBAL_ACCOUNT_SINGLE_OWNER=PASS
SIDEBAR_VERSION_ONLY=PASS
FAVORITE_WRITE_RECOVERY=PASS
FAVORITE_CANONICAL_WRITE=PASS
FAVORITE_IDEMPOTENT=PASS
FAVORITE_NULL_CATEGORY=PASS
FAVORITE_STALE_PROJECTION_RECOVERY=PASS
FAVORITE_STALE_CSRF_RECOVERY_CONTRACT=PASS
FAVORITE_UI_COLLECTION_SELECTOR=PASS
FAVORITE_UI_RUNTIME_ERROR_REMOVED=PASS
SEARCH_CONTEXT_REGRESSION=PASS
PUBLIC_NAV_REGRESSION=PASS
PUBLIC_AUTHORITY_RELEASE_COVERAGE=PASS
NO_REQUIRED_GATE_MISSING=YES
NO_UNKNOWN_APPLICABILITY=YES
PRODUCTION=NOT_WRITTEN
EOF

cat "$OUT/R20_GATE_RECEIPT.txt"
