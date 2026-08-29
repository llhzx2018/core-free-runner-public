#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE='da430cf426915a11198cfb9c6aa5335da391402f'
CANDIDATE_TREE='064b40e984c26a6d13b29e020415259a8e192a6a'
RUNTIME_TREE='febc1b01a5b59963bc974cdc6455cfa824c0adc3'
PRODUCT='faf853ab897c9e9b080dd365ab54df7698a8428c'
PRODUCT_TREE='f81d776da1fa92d04acd31ccbe6444cb1d9f0d43'
V4_PRODUCT='0a0ef35f3b719c0cd4f262c1203ca5e912596735'
SOURCE='120a42667fce7357fdaef03b64cb7ea41392040d'
SOURCE_TREE='d0fa7c87ebefef083712ec0b7707a6c4273943f2'
SOURCE_RUNTIME_TREE='f348cb314623906acc851cb79d75b1c8f6637aff'
SCHEMA='2026082901'
ART=/tmp/p01-v2330-candidate-evidence
OUT=/tmp/p01-v2330-candidate-artifacts
rm -rf "$ART" "$OUT" /tmp/p01-v2330-*runtime
mkdir -p "$ART"

# 1. Exact identity and V4 product-byte binding.
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$PRODUCT^{tree}")" = "$PRODUCT_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = '2.33.0'
test "$(cat candidate/src/VERSION.txt)" = '2.33.0'
test "$(cat production/VERSION)" = '2.32.0'
test "$(cat production/src/VERSION.txt)" = '2.32.0'
grep -Fx "define('VF_VERSION', '2.33.0');" candidate/src/app/bootstrap.php >/dev/null
grep -Fx "define('VF_VERSION', '2.32.0');" production/src/app/bootstrap.php >/dev/null
if git -C candidate diff --name-only "$SOURCE"..."$CANDIDATE" -- src/migrations/ | grep .; then echo UNEXPECTED_MIGRATION; exit 1; fi
for f in src/app/FunctionalHome.php src/app/LinkHealth.php src/assets/health.js src/health.php; do
  cmp <(git -C candidate show "$V4_PRODUCT:$f") "candidate/$f"
done
cat >"$ART/v4-binding.txt" <<'EOF'
V4_RUN=33267181746 PASS
V4_PRODUCT_SOURCE=0a0ef35f3b719c0cd4f262c1203ca5e912596735
V4_PRODUCT_TREE=f81d776da1fa92d04acd31ccbe6444cb1d9f0d43
V4_ARTIFACT=9718999692
V4_SHA256=9b702201f22f4ce8a3a0d7fe2300aa273997259eed59e77e2a559f60a17f7164
CANDIDATE_HEALTH_BYTES_MATCH_V4=PASS
RAW_PROBLEMS_COMPAT_49=PASS
HOME_NEEDS_ACTION_6=PASS
RESTRICTED_REVIEW_42=PASS
RESTRICTED_NOT_INVALID=PASS
OPEN_URL_ACTION=PASS
IGNORE_EXCLUDED_FROM_REVIEW=PASS
DESKTOP_MOBILE=PASS
ANONYMOUS_BOUNDARY=PASS
EOF

while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
printf '%s\n' \
  P01_V2330_EXACT_CANDIDATE_SOURCE=PASS \
  P01_V2330_VERSION_TRIPLE_BINDING=PASS \
  P01_V2330_SCHEMA_UNCHANGED=PASS \
  P01_V2330_NO_MIGRATION=PASS \
  P01_V2330_HEALTH_BYTES_BOUND_TO_V4=PASS | tee "$ART/source-fence.txt"

# 2. Deterministic unpublished artifacts and repair self-test.
python3 runner/scripts/p01-v2330-build-candidate-artifacts.py | tee "$ART/build-1.json"
REPAIR="$OUT/repair-v2.33.0.php"
FULL="$OUT/VF-Start-V2.33.0-FULL.zip"
UPDATE="$OUT/VF_Start_V2.33.0_UPDATE.zip"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="CANDIDATE_ARTIFACT_BUILD_PASS" and .candidate_source=="da430cf426915a11198cfb9c6aa5335da391402f" and .source_commit=="120a42667fce7357fdaef03b64cb7ea41392040d" and .schema=="2026082901" and .schema_change==false and .runtime_delta_count==6 and (.runtime_added|length)==0 and (.runtime_removed|length)==0 and .owner_production_write==false' "$OUT/P01-V2.33.0-CANDIDATE-GATE.json" >/dev/null
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-1.txt"
rm -rf "$OUT"
python3 runner/scripts/p01-v2330-build-candidate-artifacts.py | tee "$ART/build-2.json"
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-2.txt"
diff -u "$ART/artifacts-sha-1.txt" "$ART/artifacts-sha-2.txt"
unzip -Z1 "$UPDATE" | grep -Fx repair-v2.33.0.php >/dev/null
echo P01_V2330_DETERMINISTIC_CANDIDATE_ARTIFACTS=PASS | tee "$ART/artifact-verdict.txt"

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
start_server(){
  local root="$1" port="$2" log="$3"
  php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 &
  local pid=$!; PIDS+=("$pid")
  for i in $(seq 1 60); do if curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null; then break; fi; sleep .25; done
  echo "$pid"
}
setup_root(){
  local root="$1" source_dir="$2" port="$3" pass="$4" label="$5"
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
    --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.33 Candidate Gate" \
    --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/${label}-setup-post.html"
  kill "$pid" >/dev/null 2>&1 || true
  php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}
seed_source(){
  local root="$1"
  ROOT="$root" php <<'PHP' | grep -Fx P01_V2330_SOURCE_SEED=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());
$pub=$r->createCategory(['name'=>'V233公开分类','is_private'=>false,'sort_order'=>20]);
$priv=$r->createCategory(['name'=>'V233私人分类','is_private'=>true,'sort_order'=>10]);
$r->saveLink(null,['category_id'=>$pub,'title'=>'V233公开保留项','url'=>'https://example.com/v233-public','is_private'=>false,'is_favorite'=>true,'tags'=>['V233','公开']]);
$r->saveLink(null,['category_id'=>$priv,'title'=>'V233私人保留项','url'=>'https://example.com/v233-private','is_private'=>true,'tags'=>['V233','私人']]);
echo "P01_V2330_SOURCE_SEED=PASS\n";
PHP
}
verify_target(){
  local root="$1"
  ROOT="$root" php <<'PHP' | grep -Fx P01_V2330_TARGET_VERIFY=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$head=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();if($head!=='2026082901')throw new RuntimeException('schema '.$head);
$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($i!=='ok'||$fk)throw new RuntimeException('db integrity');
if((int)$db->query("SELECT COUNT(*) FROM links WHERE title='V233私人保留项' AND is_private=1")->fetchColumn()!==1)throw new RuntimeException('private lost');
if((int)$db->query("SELECT COUNT(*) FROM links WHERE title='V233公开保留项' AND is_private=0 AND is_favorite=1")->fetchColumn()!==1)throw new RuntimeException('public/favorite lost');
echo "P01_V2330_TARGET_VERIFY=PASS\n";
PHP
  test "$(cat "$root/VERSION.txt")" = '2.33.0'
  grep -Fx "define('VF_VERSION', '2.33.0');" "$root/app/bootstrap.php" >/dev/null
  php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
}

# 3. Real non-production V2.32 -> V2.33 Atomic Upgrade, preservation and idempotence.
PASS='P01V2330Candidate!2026'
UP=/tmp/p01-v2330-upgrade-runtime
setup_root "$UP" production/src 18670 "$PASS" upgrade
seed_source "$UP"
php "$REPAIR" --verify-source="$UP" | tee "$ART/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
verify_target "$UP"
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null
php "$REPAIR" --verify-target="$UP" | tee "$ART/verify-target.json" | jq -e '.ok==true' >/dev/null
echo P01_V2320_TO_V2330_ACTUAL_UPGRADE_DATA=PASS | tee "$ART/upgrade-verdict.txt"

# 4. Fresh V2.33 install/runtime verification.
FRESH=/tmp/p01-v2330-fresh-runtime
setup_root "$FRESH" candidate/src 18671 "$PASS" fresh
test "$(cat "$FRESH/VERSION.txt")" = '2.33.0'
grep -Fx "define('VF_VERSION', '2.33.0');" "$FRESH/app/bootstrap.php" >/dev/null
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();$i=strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn());$fk=$db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC);if($h!=="2026082901"||$i!=="ok"||$fk)exit(2);echo "P01_V2330_FRESH_DB=PASS\n";' | grep -Fx P01_V2330_FRESH_DB=PASS >/dev/null
echo P01_V2330_FRESH_RUNTIME=PASS | tee "$ART/fresh-verdict.txt"

cat >"$ART/verdict.txt" <<EOF
P01_V2330_CANDIDATE_SOURCE=$CANDIDATE
P01_V2330_CANDIDATE_TREE=$CANDIDATE_TREE
P01_V2330_RUNTIME_TREE=$RUNTIME_TREE
P01_V2330_PRODUCT_SOURCE=$PRODUCT
P01_V2330_PRODUCT_TREE=$PRODUCT_TREE
P01_V2330_CANDIDATE_READINESS=PASS
P01_V2330_HEALTH_TRIAGE_V4_BINDING=PASS
P01_V2330_DETERMINISTIC_ARTIFACTS=PASS
P01_V2320_TO_V2330_ACTUAL_UPGRADE=PASS
P01_V2330_DATA_PRESERVATION=PASS
P01_V2330_IDEMPOTENCE=PASS
P01_V2330_REPAIR_SELF_TEST=PASS
P01_V2330_FRESH_RUNTIME=PASS
P01_V2330_SCHEMA_UNCHANGED_2026082901=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat "$ART/verdict.txt"
