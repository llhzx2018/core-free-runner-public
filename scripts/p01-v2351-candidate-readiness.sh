#!/usr/bin/env bash
set -Eeuo pipefail

: "${CANDIDATE:?}" "${CANDIDATE_TREE:?}" "${RUNTIME_TREE:?}" "${PRODUCT:?}" "${PRODUCT_TREE:?}"
: "${SOURCE:?}" "${SOURCE_TREE:?}" "${SOURCE_RUNTIME_TREE:?}" "${ART:?}" "${OUT:?}" "${UP:?}" "${FRESH:?}" "${PORT:?}"
rm -rf "$ART" "$OUT" "$UP" "$FRESH" /tmp/p01-v2351-first /tmp/p01-v2351-ui
mkdir -p "$ART"

# Exact source fence.
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = 2.35.1
test "$(cat candidate/src/VERSION.txt)" = 2.35.1
grep -Fx "define('VF_VERSION', '2.35.1');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = 2.35.0
test "$(cat production/src/VERSION.txt)" = 2.35.0
grep -Fx "define('VF_VERSION', '2.35.0');" production/src/app/bootstrap.php >/dev/null
if git -C candidate diff --name-only "$SOURCE"..."$CANDIDATE" -- src/migrations/ | grep .; then echo UNEXPECTED_MIGRATION; exit 1; fi
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
printf '%s\n' P01_V2351_EXACT_SOURCE=PASS P01_V2351_VERSION_TRIPLE=PASS P01_V2351_SCHEMA_UNCHANGED=PASS P01_V2351_NO_MIGRATION=PASS | tee "$ART/source-fence.txt"

# Deterministic candidate artifacts from the same proven Atomic builder used by V2.35.0.
cat > /tmp/p01-v2351-build.py <<'PY'
from pathlib import Path
import hashlib,importlib.util,json,os
ROOT=Path(os.environ['GITHUB_WORKSPACE']); VERSION='2.35.1'; SOURCE_VERSION='2.35.0'; SCHEMA='2026082901'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
base=load('base',ROOT/'proven/scripts/p01-build-release.py'); v2=load('v2',ROOT/'proven/scripts/p01-build-release-v2.py')
sha=lambda b:hashlib.sha256(b).hexdigest(); gate_only={'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
def runtime(files): return {k:v for k,v in files.items() if k!='release-manifest.json' and k not in gate_only and k!='VF-Start-Browser-Extension.zip'}
td=base.collect(ROOT/'candidate/src'); sd=base.collect(ROOT/'production/src'); target=runtime(td); source=runtime(sd)
changed=sorted(k for k in target if k not in source or sha(target[k])!=sha(source[k])); added=sorted(set(target)-set(source)); removed=sorted(set(source)-set(target))
required={'VERSION.txt','app/bootstrap.php','app/FunctionalHome.php','assets/resource-media.css','assets/workspace-home.css'}
assert td['VERSION.txt'].strip()==VERSION.encode() and sd['VERSION.txt'].strip()==SOURCE_VERSION.encode()
if removed: raise SystemExit('unexpected removed runtime files '+json.dumps(removed))
if not required.issubset(set(changed)): raise SystemExit('missing expected runtime delta '+json.dumps(changed))
manifest={'project':'VF Start','project_id':'P01','component_id':'APP','version':VERSION,'source_version':SOURCE_VERSION,'schema_version':SCHEMA,'source_schema_version':SCHEMA,'release_type':'candidate','stage':'CANDIDATE_READINESS_GATE','deployable':False,'release_authorized':False,'candidate_source_commit':os.environ['CANDIDATE'],'candidate_source_tree':os.environ['CANDIDATE_TREE'],'product_source_commit':os.environ['PRODUCT'],'product_source_tree':os.environ['PRODUCT_TREE'],'runtime_source_tree':os.environ['RUNTIME_TREE'],'production_source_commit':os.environ['SOURCE'],'production_source_tree':os.environ['SOURCE_TREE'],'production_runtime_tree':os.environ['SOURCE_RUNTIME_TREE'],'schema_change':False,'schema_migrations':[],'runtime_data_included':False,'runtime_files':{k:sha(v) for k,v in sorted(target.items())},'atomic_runtime_boundary':{'source_version':SOURCE_VERSION,'target_version':VERSION,'source_schema':SCHEMA,'target_schema':SCHEMA,'added_files':added,'removed_files':removed,'runtime_delta':changed},'update':{'asset_name':'VF_Start_V2.35.1_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},'ux_v2351':{'topic_fallback_identity':True,'watch_fallback_identity':True,'home_mobile_empty_recent_density':True,'home_action_priority':True,'final_visual_sweep_run':33338822193,'home_action_priority_gate':33338635840}}
mb=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode(); full=dict(td); full['release-manifest.json']=mb; atomic=dict(target); atomic['release-manifest.json']=mb
repair=v2.build_repair(source,atomic,sha(target['app/UpdateManager.php']))
old="public const SOURCE_VERSION='2.21.14';\n    public const TARGET_VERSION='2.21.15';\n    public const TARGET_SCHEMA='2026080902';"
new="public const SOURCE_VERSION='2.35.0';\n    public const TARGET_VERSION='2.35.1';\n    public const TARGET_SCHEMA='2026082901';"
if repair.count(old)!=1: raise SystemExit('repair constant anchor mismatch')
repair=repair.replace(old,new,1)
out=Path(os.environ['OUT']); out.mkdir(parents=True,exist_ok=True); rp=out/'repair-v2.35.1.php'; rp.write_text(repair,encoding='utf-8',newline='\n')
base.deterministic_zip(out/'VF-Start-V2.35.1-FULL.zip',full); base.deterministic_zip(out/'VF_Start_V2.35.1_UPDATE.zip',{rp.name:rp.read_bytes()})
result={'status':'CANDIDATE_ARTIFACT_BUILD_PASS','candidate_source':os.environ['CANDIDATE'],'candidate_tree':os.environ['CANDIDATE_TREE'],'runtime_tree':os.environ['RUNTIME_TREE'],'source_commit':os.environ['SOURCE'],'version':VERSION,'source_version':SOURCE_VERSION,'schema':SCHEMA,'runtime_delta_count':len(changed),'runtime_delta':changed,'runtime_added':added,'runtime_removed':removed,'owner_production_write':False,'release_published':False}
(out/'P01-V2.35.1-CANDIDATE-GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
arts=[p for p in sorted(out.iterdir()) if p.is_file()]; (out/'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in arts),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False))
PY
python3 /tmp/p01-v2351-build.py | tee "$ART/build-1.json"
REPAIR="$OUT/repair-v2.35.1.php"; FULL="$OUT/VF-Start-V2.35.1-FULL.zip"; UPDATE="$OUT/VF_Start_V2.35.1_UPDATE.zip"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-1.txt"
cp -a "$OUT" /tmp/p01-v2351-first; rm -rf "$OUT"
python3 /tmp/p01-v2351-build.py | tee "$ART/build-2.json"
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-2.txt"
diff -u "$ART/artifacts-sha-1.txt" "$ART/artifacts-sha-2.txt"
unzip -Z1 "$UPDATE" | grep -Fx repair-v2.35.1.php >/dev/null
echo P01_V2351_DETERMINISTIC_ARTIFACTS=PASS | tee "$ART/artifact-verdict.txt"

setup_root(){
  local root="$1" src="$2" port="$3" label="$4" pass="$5" cookie="$ART/$label.cookies"
  rm -rf "$root"; cp -a "$src" "$root"; rm -f "$cookie"
  php -S 127.0.0.1:$port -t "$root" >"$ART/$label-server.log" 2>&1 & local pid=$!
  local ready=0
  for i in $(seq 1 60); do if curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:$port/setup.php" -o "$ART/$label-setup.html"; then ready=1; break; fi; sleep .25; done
  test "$ready" = 1
  local csrf; csrf=$(python3 - "$ART/$label-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
  curl -fsS -c "$cookie" -b "$cookie" -X POST "http://127.0.0.1:$port/setup.php" --data-urlencode "setup_csrf=$csrf" --data-urlencode 'site_title=V2351 Gate' --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/$label-setup-post.html"
  kill "$pid" || true
  php "$root/cli/verify.php" | tee "$ART/$label-post-setup-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}

# Real V2.35.0 -> V2.35.1 Atomic upgrade.
setup_root "$UP" production/src 18373 source 'V2351Gate!2026'
ROOT="$UP" php <<'PHP' | tee "$ART/seed.txt"
<?php
require getenv('ROOT').'/app/bootstrap.php'; require_once getenv('ROOT').'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());$c=$r->createCategory(['name'=>'发布验证','description'=>'','is_private'=>false]);$ids=[];$domains=['start','channels','watch','topics'];
for($i=1;$i<=48;$i++){ $x=$r->saveLink(null,['category_id'=>$c,'title'=>'Gate '.$i,'url'=>'https://example.com/v2351-'.$i,'description'=>'V2351 preserve','tags'=>'release','is_private'=>$i%4===0,'is_favorite'=>$i<=4],'manual');$ids[]=(int)$x['id'];$d=$domains[($i-1)%4];if($d!=='start')$s->upsertProfile((int)$x['id'],['surface'=>$d,'resource_kind'=>$d==='channels'?'creator':($d==='watch'?'movie':'guide')]);if($i<=8)$s->recordOpen((int)$x['id']); }
$db=vf_db();$now=gmdate('c');$ins=$db->prepare("INSERT INTO link_health(link_id,status,http_status,last_checked_at,updated_at,ignore_auto) VALUES(?,?,?,?,?,0)");foreach([[$ids[0],'confirmed',410],[$ids[1],'suspected',404],[$ids[2],'temporary',503],[$ids[3],'restricted',403]] as [$id,$st,$code])$ins->execute([$id,$st,$code,$now,$now]);
echo "P01_V2351_SEED_48=PASS\n";
PHP
grep -Fx P01_V2351_SEED_48=PASS "$ART/seed.txt"
ROOT="$UP" php <<'PHP' | tee "$ART/pre-upgrade-data.json"
<?php
require getenv('ROOT').'/app/bootstrap.php';$db=vf_db();$hs=(new VfLinkHealth($db))->status();$x=[
'active_links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),
'profiles'=>(int)$db->query("SELECT COUNT(*) FROM resource_domain_profiles")->fetchColumn(),
'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE is_favorite=1 AND lifecycle_state='active'")->fetchColumn(),
'needs_action'=>(int)$hs['needsAction'],'restricted'=>(int)$hs['restrictedReview'],
'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn()];
echo json_encode($x,JSON_UNESCAPED_SLASHES)."\n";
PHP
jq -e '.active_links==48 and .needs_action==3 and .restricted==1 and .schema=="2026082901"' "$ART/pre-upgrade-data.json" >/dev/null
php "$REPAIR" --verify-source="$UP" | tee "$ART/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
test "$(cat "$UP/VERSION.txt")" = 2.35.1; grep -Fx "define('VF_VERSION', '2.35.1');" "$UP/app/bootstrap.php" >/dev/null
ROOT="$UP" PRE="$ART/pre-upgrade-data.json" php <<'PHP' | tee "$ART/post-upgrade-data.json"
<?php
require getenv('ROOT').'/app/bootstrap.php';$db=vf_db();$hs=(new VfLinkHealth($db))->status();$pre=json_decode((string)file_get_contents(getenv('PRE')),true);$after=[
'active_links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),
'profiles'=>(int)$db->query("SELECT COUNT(*) FROM resource_domain_profiles")->fetchColumn(),
'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE is_favorite=1 AND lifecycle_state='active'")->fetchColumn(),
'needs_action'=>(int)$hs['needsAction'],'restricted'=>(int)$hs['restrictedReview'],
'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn()];
if($after!==$pre){fwrite(STDERR,json_encode(['pre'=>$pre,'after'=>$after],JSON_PRETTY_PRINT)."\n");exit(8);}if(strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(9);if($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))exit(10);echo json_encode($after,JSON_UNESCAPED_SLASHES)."\n";
PHP
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true' >/dev/null
php "$REPAIR" --verify-target="$UP" | tee "$ART/verify-target.json" | jq -e '.ok==true' >/dev/null
php "$UP/cli/verify.php" | tee "$ART/upgraded-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
php "$UP/cli/surface-verify.php" | tee "$ART/upgraded-surface.txt" | grep -E 'MULTI_SURFACE_PASS=YES|CURRENT_DOMAIN_PASS=YES' >/dev/null
php "$UP/cli/baseline-verify.php" | tee "$ART/upgraded-baseline.txt"
grep -Fx BASELINE_CORE_PASS=YES "$ART/upgraded-baseline.txt"; grep -Fx DRIFT_COUNT=0 "$ART/upgraded-baseline.txt"; grep -Fx UNKNOWN_COUNT=0 "$ART/upgraded-baseline.txt"
echo P01_V2350_TO_V2351_ACTUAL_UPGRADE=PASS | tee "$ART/upgrade-verdict.txt"

# Fresh candidate install.
setup_root "$FRESH" candidate/src 18374 fresh 'V2351Fresh!2026'
php "$FRESH/cli/verify.php" | tee "$ART/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
php "$FRESH/cli/surface-verify.php" | tee "$ART/fresh-surface.txt" | grep -E 'MULTI_SURFACE_PASS=YES|CURRENT_DOMAIN_PASS=YES' >/dev/null
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();if((string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn()!=="2026082901")exit(1);if(strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(2);if($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(3);echo "P01_V2351_FRESH_DB=PASS\n";' | tee "$ART/fresh-db.txt"

# Browser smoke on the actual upgraded runtime, including Home action priority.
php -S 127.0.0.1:$PORT -t "$UP" >"$ART/browser-server.log" 2>&1 & echo $! >/tmp/p01-v2351-browser.pid
for i in $(seq 1 60); do curl -fsS "http://127.0.0.1:$PORT/index.php" -o /dev/null && break; sleep .25; done
mkdir -p /tmp/p01-v2351-ui; cd /tmp/p01-v2351-ui; npm init -y >/dev/null 2>&1; npm install playwright@1.55.0 --no-save >/dev/null 2>&1; npx playwright install chromium --with-deps >/dev/null 2>&1
cat > smoke.cjs <<'JS'
const {chromium}=require('playwright'),fs=require('fs');
(async()=>{const b=await chromium.launch({headless:true}),c=await b.newContext({viewport:{width:1440,height:1000}});let r=await c.request.post('http://127.0.0.1:18376/api.php?action=login',{data:{password:'V2351Gate!2026'}});if(!r.ok()||!(await r.json()).ok)throw Error('login');const p=await c.newPage(),pages=['home.php','start.php','channels.php','watch.php','topics.php'];const out={};for(const f of pages){for(const theme of ['light','dark']){await p.goto('http://127.0.0.1:18376/'+f,{waitUntil:'networkidle'});await p.evaluate(t=>{document.documentElement.dataset.theme=t;localStorage.setItem('vf_theme',t)},theme);await p.reload({waitUntil:'networkidle'});const m=await p.evaluate(()=>({version:document.body.innerText.includes('V2.35.1'),overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,first:document.querySelector('.vf-home-status-grid>a')?.innerText.replace(/\s+/g,' ').trim()||'',rail:document.querySelector('.vf-home-rail>.vf-home-section')?.className||''}));if(!m.version||m.overflow>1)throw Error(f+' '+theme+' '+JSON.stringify(m));if(f==='home.php'&&(!m.first.startsWith('网址健康 3')||!m.rail.includes('vf-home-health-section')))throw Error('home priority '+theme+' '+JSON.stringify(m));out[f+'-'+theme]=m;await p.screenshot({path:process.env.ART+'/'+f.replace('.php','')+'-1440-'+theme+'.png',fullPage:false});}}await p.setViewportSize({width:390,height:844});for(const f of pages){await p.goto('http://127.0.0.1:18376/'+f,{waitUntil:'networkidle'});const m=await p.evaluate(()=>({overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,first:document.querySelector('.vf-home-status-grid>a')?.innerText.replace(/\s+/g,' ').trim()||''}));if(m.overflow>1)throw Error('mobile '+f);if(f==='home.php'&&!m.first.startsWith('网址健康 3'))throw Error('mobile home priority '+JSON.stringify(m));await p.screenshot({path:process.env.ART+'/'+f.replace('.php','')+'-390.png',fullPage:false});}fs.writeFileSync(process.env.ART+'/browser-metrics.json',JSON.stringify(out,null,2));await b.close();console.log('P01_V2351_BROWSER=PASS')})().catch(e=>{console.error(e);process.exit(1)});
JS
ART="$ART" node smoke.cjs | tee "$ART/browser-result.txt"
grep -Fx P01_V2351_BROWSER=PASS "$ART/browser-result.txt"
kill "$(cat /tmp/p01-v2351-browser.pid)" 2>/dev/null || true

cat > "$ART/verdict.txt" <<EOF
P01_V2351_CANDIDATE_SOURCE=$CANDIDATE
P01_V2351_CANDIDATE_TREE=$CANDIDATE_TREE
P01_V2351_RUNTIME_TREE=$RUNTIME_TREE
P01_V2351_CANDIDATE_READINESS=PASS
P01_V2351_DETERMINISTIC_ARTIFACTS=PASS
P01_V2350_TO_V2351_ACTUAL_UPGRADE=PASS
P01_V2351_DATA_PRESERVATION=PASS
P01_V2351_IDEMPOTENCE=PASS
P01_V2351_FRESH_RUNTIME=PASS
P01_V2351_BROWSER=PASS
P01_V2351_HOME_ACTION_PRIORITY=PASS
P01_V2351_SCHEMA_UNCHANGED_2026082901=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat "$ART/verdict.txt"
