#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE='8cd4b78ec27ced5657888a692a32bad1cc953fcd'
CANDIDATE_TREE='67ece5c16135e43acbfe6be8d1dad96e3d541900'
RUNTIME_TREE='f3eeb66fbce3949ef50483ac4c5a821edbd15d35'
PRODUCT='25dd705582a6f2c0c06a3f52c32c780c2268b5fa'
PRODUCT_TREE='d44882648a101e314ba66a66eb8b7f72ec67b283'
SOURCE='8c819c8bfd055d16b3ac367cef15f723431d9a42'
SOURCE_TREE='db5a6e2b6a852e6925727b974fb7130359e3cdf8'
SOURCE_RUNTIME_TREE='febc1b01a5b59963bc974cdc6455cfa824c0adc3'
SCHEMA='2026082901'
ART=/tmp/p01-v2340-candidate-evidence
OUT=/tmp/p01-v2340-candidate-artifacts
UP=/tmp/p01-v2340-upgrade-runtime
FRESH=/tmp/p01-v2340-fresh-runtime
PASS='P01V234!Resource'
PORT=18342
rm -rf "$ART" "$OUT" "$UP" "$FRESH" /tmp/p01-v2340-*.cookies /tmp/p01-v2340-ids.json
mkdir -p "$ART"

# 1. Exact candidate identity + metadata-only versioning fence.
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$PRODUCT^{tree}")" = "$PRODUCT_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = '2.34.0'
test "$(cat candidate/src/VERSION.txt)" = '2.34.0'
test "$(cat production/VERSION)" = '2.33.0'
test "$(cat production/src/VERSION.txt)" = '2.33.0'
grep -Fx "define('VF_VERSION', '2.34.0');" candidate/src/app/bootstrap.php >/dev/null
grep -Fx "define('VF_VERSION', '2.33.0');" production/src/app/bootstrap.php >/dev/null

cat > /tmp/p01-v2340-metadata-expected.txt <<'EOF'
CHANGELOG.md
VERSION
VF_PROJECT.json
docs/authority/CURRENT.md
docs/evidence/P01_V2.34.0_CANDIDATE_READINESS_20260830.md
docs/handoff/CURRENT_STATE.md
src/VERSION.txt
src/app/bootstrap.php
EOF
git -C candidate diff --name-only "$PRODUCT"..."$CANDIDATE" | sort > /tmp/p01-v2340-metadata-actual.txt
diff -u /tmp/p01-v2340-metadata-expected.txt /tmp/p01-v2340-metadata-actual.txt
if git -C candidate diff --name-only "$SOURCE"..."$CANDIDATE" -- src/migrations/ | grep .; then echo UNEXPECTED_MIGRATION; exit 1; fi
python3 - <<'PY'
import json
p=json.load(open('candidate/VF_PROJECT.json',encoding='utf-8'))
assert p['project_id']=='P01'
assert p['production_version']=='2.33.0'
assert p['working_version']=='2.34.0'
assert p['target_release_version']=='2.34.0'
assert str(p['working_schema_version'])=='2026082901'
assert p['current_change']['product_develop_source']=='25dd705582a6f2c0c06a3f52c32c780c2268b5fa'
assert p['current_change']['product_complete_evidence']['run']==33313092778
assert p['current_change']['product_complete_evidence']['artifact_id']==9732605682
assert p['current_change']['schema_change'] is False
assert p['current_change']['migration'] is None
assert p['v2_34_tag_state']=='NOT_CREATED'
assert p['core_updates_v2_34_state']=='NOT_PUBLISHED'
print('P01_V2340_AUTHORITY=PASS')
PY
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
printf '%s\n' P01_V2340_EXACT_SOURCE=PASS P01_V2340_VERSION_TRIPLE=PASS P01_V2340_METADATA_ONLY_FENCE=PASS P01_V2340_SCHEMA_UNCHANGED=PASS P01_V2340_NO_MIGRATION=PASS | tee "$ART/source-fence.txt"

# 2. Deterministic unpublished candidate artifacts + repair self-test.
python3 runner/scripts/p01-v2340-build-candidate-artifacts.py | tee "$ART/build-1.json"
REPAIR="$OUT/repair-v2.34.0.php"
FULL="$OUT/VF-Start-V2.34.0-FULL.zip"
UPDATE="$OUT/VF_Start_V2.34.0_UPDATE.zip"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="CANDIDATE_ARTIFACT_BUILD_PASS" and .candidate_source=="8cd4b78ec27ced5657888a692a32bad1cc953fcd" and .source_commit=="8c819c8bfd055d16b3ac367cef15f723431d9a42" and .schema=="2026082901" and .schema_change==false and .runtime_delta_count==11 and .runtime_added==["assets/workspace-primary-open.js"] and (.runtime_removed|length)==0 and .owner_production_write==false' "$OUT/P01-V2.34.0-CANDIDATE-GATE.json" >/dev/null
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-1.txt"
rm -rf "$OUT"
python3 runner/scripts/p01-v2340-build-candidate-artifacts.py | tee "$ART/build-2.json"
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-2.txt"
diff -u "$ART/artifacts-sha-1.txt" "$ART/artifacts-sha-2.txt"
unzip -Z1 "$UPDATE" | grep -Fx repair-v2.34.0.php >/dev/null
echo P01_V2340_DETERMINISTIC_CANDIDATE_ARTIFACTS=PASS | tee "$ART/artifact-verdict.txt"

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
start_server(){
  local root="$1" port="$2" log="$3"
  php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 &
  local pid=$!; PIDS+=("$pid")
  for i in $(seq 1 60); do if curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null; then echo "$pid"; return 0; fi; sleep .25; done
  return 1
}
setup_root(){
  local root="$1" source_dir="$2" port="$3" label="$4"
  rm -rf "$root"; cp -a "$source_dir" "$root"
  local pid; pid=$(start_server "$root" "$port" "$ART/${label}-server.log")
  local cookie="$ART/${label}.cookies" page="$ART/${label}-setup.html"
  curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:${port}/setup.php" -o "$page"
  local csrf; csrf=$(python3 - "$page" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
  curl -fsS -c "$cookie" -b "$cookie" -X POST "http://127.0.0.1:${port}/setup.php" \
    --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.34 Candidate Gate" \
    --data-urlencode "admin_password=$PASS" --data-urlencode "admin_password_confirm=$PASS" -o "$ART/${label}-setup-post.html"
  kill "$pid" >/dev/null 2>&1 || true
  php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}

seed_423(){
  ROOT="$1" php <<'PHP' | grep -Fx P01_V2340_SEED_423=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());$db=vf_db();
$dev=$r->createCategory(['name'=>'开发工具','description'=>'','is_private'=>false]);
$ai=$r->createCategory(['name'=>'AI 资料','description'=>'','is_private'=>false]);
$ops=$r->createCategory(['name'=>'运维工具','description'=>'','is_private'=>false]);
$ids=[];
for($i=1;$i<=423;$i++){
  $category=$i<=210?$dev:($i<=360?$ai:$ops);
  $title=$i===423?'Needle Resource 423':'Resource '.str_pad((string)$i,3,'0',STR_PAD_LEFT);
  $saved=$r->saveLink(null,['category_id'=>$category,'title'=>$title,'url'=>'https://resource'.$i.'.example.com','description'=>$i%25===0?'常用效率工具':'resource fixture','tags'=>$i%10===0?'效率,常用':'效率','is_private'=>true,'is_favorite'=>$i%37===0],'manual');
  $ids[]=(int)$saved['id'];
}
$recent=[[$ids[0],3],[$ids[1],20],[$ids[2],60],[$ids[3],150]];
$update=$db->prepare('UPDATE resource_domain_profiles SET last_opened_at=?, updated_at=? WHERE link_id=?');
foreach($recent as [$id,$days]){$s->recordOpen((int)$id);$stamp=gmdate('c',time()-((int)$days*86400));$update->execute([$stamp,$stamp,(int)$id]);}
file_put_contents('/tmp/p01-v2340-ids.json',json_encode(['all'=>$ids,'dev'=>$dev,'ai'=>$ai,'ops'=>$ops,'recent'=>array_map(static fn($x)=>(int)$x[0],$recent)],JSON_THROW_ON_ERROR));
echo "P01_V2340_SEED_423=PASS\n";
PHP
}

verify_upgraded(){
  local root="$1"
  ROOT="$root" php <<'PHP' | grep -Fx P01_V2340_UPGRADED_DATA=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$head=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();
if($head!=='2026082901')throw new RuntimeException('schema '.$head);
if((int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn()!==423)throw new RuntimeException('count');
if((int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_private=1")->fetchColumn()!==423)throw new RuntimeException('privacy');
if((int)$db->query("SELECT COUNT(*) FROM links WHERE title='Needle Resource 423'")->fetchColumn()!==1)throw new RuntimeException('needle');
if((int)$db->query("SELECT COUNT(*) FROM resource_domain_profiles WHERE last_opened_at IS NOT NULL")->fetchColumn()!==4)throw new RuntimeException('recent');
if(strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn())!=='ok')throw new RuntimeException('integrity');
if($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))throw new RuntimeException('fk');
echo "P01_V2340_UPGRADED_DATA=PASS\n";
PHP
  test "$(cat "$root/VERSION.txt")" = '2.34.0'
  grep -Fx "define('VF_VERSION', '2.34.0');" "$root/app/bootstrap.php" >/dev/null
  php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
  php "$root/cli/surface-verify.php" | tee "$ART/upgraded-surface-verify.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES >/dev/null
}

# 3. Actual isolated V2.33.0 -> V2.34.0 Atomic Upgrade with 423-resource data preservation.
setup_root "$UP" production/src 18340 upgrade-source
seed_423 "$UP"
php "$REPAIR" --verify-source="$UP" | tee "$ART/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
verify_upgraded "$UP"
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null
php "$REPAIR" --verify-target="$UP" | tee "$ART/verify-target.json" | jq -e '.ok==true' >/dev/null
printf '%s\n' P01_V2330_TO_V2340_ACTUAL_UPGRADE=PASS P01_V2340_DATA_PRESERVATION_423=PASS P01_V2340_IDEMPOTENCE=PASS | tee "$ART/upgrade-verdict.txt"

# 4. Fresh V2.34 install/runtime verification.
setup_root "$FRESH" candidate/src 18341 fresh
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();$i=strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn());$fk=$db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC);if($h!=="2026082901"||$i!=="ok"||$fk)exit(2);echo "P01_V2340_FRESH_DB=PASS\n";' | grep -Fx P01_V2340_FRESH_DB=PASS >/dev/null
printf '%s\n' P01_V2340_FRESH_RUNTIME=PASS | tee "$ART/fresh-verdict.txt"

# 5. Start the upgraded 423-resource runtime for the real browser gate.
php -S 127.0.0.1:$PORT -t "$UP" >"$ART/browser-server.log" 2>&1 &
echo $! >/tmp/p01-v2340-browser-server.pid
for i in $(seq 1 60); do if curl -fsS "http://127.0.0.1:${PORT}/index.php" -o /dev/null; then break; fi; sleep .25; done

cat >"$ART/machine-verdict.txt" <<EOF
P01_V2340_CANDIDATE_SOURCE=$CANDIDATE
P01_V2340_CANDIDATE_TREE=$CANDIDATE_TREE
P01_V2340_RUNTIME_TREE=$RUNTIME_TREE
P01_V2340_PRODUCT_SOURCE=$PRODUCT
P01_V2340_PRODUCT_TREE=$PRODUCT_TREE
P01_V2340_SOURCE_PRODUCTION=$SOURCE
P01_V2340_MACHINE_READINESS=PASS
P01_V2340_METADATA_ONLY_FENCE=PASS
P01_V2340_DETERMINISTIC_ARTIFACTS=PASS
P01_V2330_TO_V2340_ACTUAL_UPGRADE=PASS
P01_V2340_DATA_PRESERVATION_423=PASS
P01_V2340_IDEMPOTENCE=PASS
P01_V2340_REPAIR_SELF_TEST=PASS
P01_V2340_FRESH_RUNTIME=PASS
P01_V2340_SCHEMA_UNCHANGED_2026082901=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat "$ART/machine-verdict.txt"
trap - EXIT
