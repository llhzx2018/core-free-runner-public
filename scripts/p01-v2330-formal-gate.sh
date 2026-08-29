#!/usr/bin/env bash
set -Eeuo pipefail
FORMAL='8c819c8bfd055d16b3ac367cef15f723431d9a42'
FORMAL_TREE='db5a6e2b6a852e6925727b974fb7130359e3cdf8'
FINAL_CANDIDATE='bfc122fe61bf629984583304fff37f7feaa0a294'
VERSIONED_CANDIDATE='da430cf426915a11198cfb9c6aa5335da391402f'
PRODUCT='faf853ab897c9e9b080dd365ab54df7698a8428c'
PRODUCT_TREE='f81d776da1fa92d04acd31ccbe6444cb1d9f0d43'
V4_PRODUCT='0a0ef35f3b719c0cd4f262c1203ca5e912596735'
RUNTIME_TREE='febc1b01a5b59963bc974cdc6455cfa824c0adc3'
SOURCE='120a42667fce7357fdaef03b64cb7ea41392040d'
SOURCE_TREE='d0fa7c87ebefef083712ec0b7707a6c4273943f2'
SOURCE_RUNTIME_TREE='f348cb314623906acc851cb79d75b1c8f6637aff'
SCHEMA='2026082901'
ART=/tmp/p01-v2330-formal-evidence
OUT=/tmp/p01-v2330-formal-artifacts
rm -rf "$ART" "$OUT" /tmp/p01-v2330-formal-*runtime
mkdir -p "$ART"

test "$(git -C candidate rev-parse HEAD)" = "$FORMAL"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$FORMAL_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$PRODUCT^{tree}")" = "$PRODUCT_TREE"
test "$(git -C candidate rev-parse "$FINAL_CANDIDATE:src")" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$VERSIONED_CANDIDATE:src")" = "$RUNTIME_TREE"
git -C candidate diff --quiet "$FINAL_CANDIDATE" "$FORMAL" -- src
git -C candidate diff --quiet "$VERSIONED_CANDIDATE" "$FORMAL" -- src
for f in src/app/FunctionalHome.php src/app/LinkHealth.php src/assets/health.js src/health.php; do cmp <(git -C candidate show "$V4_PRODUCT:$f") "candidate/$f"; done

test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = 2.33.0
test "$(cat candidate/src/VERSION.txt)" = 2.33.0
test "$(cat production/VERSION)" = 2.32.0
test "$(cat production/src/VERSION.txt)" = 2.32.0
grep -Fx "define('VF_VERSION', '2.33.0');" candidate/src/app/bootstrap.php >/dev/null
grep -Fx "define('VF_VERSION', '2.32.0');" production/src/app/bootstrap.php >/dev/null
if git -C candidate diff --name-only "$SOURCE"..."$FORMAL" -- src/migrations/ | grep .; then echo UNEXPECTED_MIGRATION; exit 1; fi
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
printf '%s\n' P01_V2330_FORMAL_EXACT_SOURCE=PASS P01_V2330_RUNTIME_EQUALS_CANDIDATE=PASS P01_V2330_HEALTH_BYTES_BOUND_TO_V4=PASS P01_V2330_CANDIDATE_GATE_33268162412_BOUND=PASS P01_V2330_VERSION_TRIPLE_BINDING=PASS P01_V2330_SCHEMA_UNCHANGED=PASS P01_V2330_NO_MIGRATION=PASS | tee "$ART/source-fence.txt"

python3 runner/scripts/p01-v2330-build-formal-artifacts.py | tee "$ART/build-1.json"
REPAIR="$OUT/repair-v2.33.0.php"; FULL="$OUT/VF-Start-V2.33.0-FULL.zip"; UPDATE="$OUT/VF_Start_V2.33.0_UPDATE.zip"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="FORMAL_ARTIFACT_BUILD_PASS" and .release_source=="8c819c8bfd055d16b3ac367cef15f723431d9a42" and .source_commit=="120a42667fce7357fdaef03b64cb7ea41392040d" and .schema=="2026082901" and .schema_change==false and .runtime_delta_count==6 and (.runtime_added|length)==0 and (.runtime_removed|length)==0 and .owner_production_write==false' "$OUT/P01-V2.33.0-FORMAL-GATE.json" >/dev/null
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-1.txt"
rm -rf "$OUT"; python3 runner/scripts/p01-v2330-build-formal-artifacts.py | tee "$ART/build-2.json"
REPAIR="$OUT/repair-v2.33.0.php"; FULL="$OUT/VF-Start-V2.33.0-FULL.zip"; UPDATE="$OUT/VF_Start_V2.33.0_UPDATE.zip"
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-2.txt"; diff -u "$ART/artifacts-sha-1.txt" "$ART/artifacts-sha-2.txt"
unzip -Z1 "$UPDATE" | grep -Fx repair-v2.33.0.php >/dev/null
if unzip -Z1 "$FULL" | grep -E '(^|/)(\.runtime\.php|\.env|[^/]*\.sqlite3?|[^/]*\.db)$'; then echo SENSITIVE_RUNTIME_DATA_IN_FULL; exit 1; fi
echo P01_V2330_DETERMINISTIC_FORMAL_ARTIFACTS=PASS | tee "$ART/artifact-verdict.txt"

PIDS=(); cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }; trap cleanup EXIT
start_server(){ local root="$1" port="$2" log="$3"; php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 & local pid=$!; PIDS+=("$pid"); for i in $(seq 1 60); do curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null && break || true; sleep .25; done; echo "$pid"; }
setup_root(){ local root="$1" source_dir="$2" port="$3" pass="$4" label="$5"; rm -rf "$root"; cp -a "$source_dir" "$root"; local pid; pid=$(start_server "$root" "$port" "$ART/${label}-server.log"); local cookie="$ART/${label}.cookies" page="$ART/${label}-setup.html"; curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:${port}/setup.php" -o "$page"; local csrf; csrf=$(python3 - "$page" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
); curl -fsS -c "$cookie" -b "$cookie" -X POST "http://127.0.0.1:${port}/setup.php" --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.33 Formal Gate" --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/${label}-setup-post.html"; kill "$pid" >/dev/null 2>&1 || true; php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null; }
seed_source(){ local root="$1"; ROOT="$root" php <<'PHP' | grep -Fx P01_V2330_SOURCE_SEED=PASS >/dev/null
<?php
declare(strict_types=1);$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());$pub=$r->createCategory(['name'=>'V233公开分类','is_private'=>false,'sort_order'=>20]);$priv=$r->createCategory(['name'=>'V233私人分类','is_private'=>true,'sort_order'=>10]);$r->saveLink(null,['category_id'=>$pub,'title'=>'V233公开保留项','url'=>'https://example.com/v233-public','is_private'=>false,'is_favorite'=>true,'tags'=>['V233','公开']]);$r->saveLink(null,['category_id'=>$priv,'title'=>'V233私人保留项','url'=>'https://example.com/v233-private','is_private'=>true,'tags'=>['V233','私人']]);echo "P01_V2330_SOURCE_SEED=PASS\n";
PHP
}
verify_target(){ local root="$1"; ROOT="$root" php <<'PHP' | grep -Fx P01_V2330_TARGET_VERIFY=PASS >/dev/null
<?php
declare(strict_types=1);$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($h!=='2026082901'||$i!=='ok'||$fk)throw new RuntimeException('db');if((int)$db->query("SELECT COUNT(*) FROM links WHERE title='V233私人保留项' AND is_private=1")->fetchColumn()!==1)throw new RuntimeException('private');if((int)$db->query("SELECT COUNT(*) FROM links WHERE title='V233公开保留项' AND is_private=0 AND is_favorite=1")->fetchColumn()!==1)throw new RuntimeException('public');echo "P01_V2330_TARGET_VERIFY=PASS\n";
PHP
 test "$(cat "$root/VERSION.txt")" = 2.33.0; grep -Fx "define('VF_VERSION', '2.33.0');" "$root/app/bootstrap.php" >/dev/null; php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null; }
verify_source_rollback(){ local root="$1"; test "$(cat "$root/VERSION.txt")" = 2.32.0; grep -Fx "define('VF_VERSION', '2.32.0');" "$root/app/bootstrap.php" >/dev/null; ROOT="$root" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);if((int)$db->query("SELECT COUNT(*) FROM links WHERE title=\"V233私人保留项\" AND is_private=1")->fetchColumn()!==1)exit(3);echo "PASS\n";' | grep -Fx PASS >/dev/null; }

PASS='P01V2330Formal!2026'
UP=/tmp/p01-v2330-formal-upgrade-runtime; setup_root "$UP" production/src 18680 "$PASS" upgrade; seed_source "$UP"; php "$REPAIR" --verify-source="$UP" | tee "$ART/verify-source.json" | jq -e '.ok==true' >/dev/null; php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null; verify_target "$UP"; php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null; php "$REPAIR" --verify-target="$UP" | tee "$ART/verify-target.json" | jq -e '.ok==true' >/dev/null; echo P01_V2320_TO_V2330_FORMAL_ACTUAL_UPGRADE_DATA=PASS | tee "$ART/upgrade-verdict.txt"

FAILROOT=/tmp/p01-v2330-formal-fail-runtime; setup_root "$FAILROOT" production/src 18681 "$PASS" fail; seed_source "$FAILROOT"; set +e; VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$REPAIR" --run="$FAILROOT" >"$ART/fail-run.out" 2>"$ART/fail-run.err"; RC=$?; set -e; test "$RC" -ne 0; verify_source_rollback "$FAILROOT"; if find "$FAILROOT" -path '*/updates/p01-atomic-transaction.json' -type f | grep .; then echo STALE_ATOMIC_TRANSACTION; exit 1; fi; echo P01_V2330_FORMAL_FAILURE_ROLLBACK=PASS | tee "$ART/rollback-verdict.txt"

HARD=/tmp/p01-v2330-formal-hard-runtime; setup_root "$HARD" production/src 18682 "$PASS" hard; seed_source "$HARD"; set +e; VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$REPAIR" --run="$HARD" >"$ART/hard-run.out" 2>"$ART/hard-run.err"; RC=$?; set -e; test "$RC" = 97; find "$HARD" -path '*/updates/p01-atomic-transaction.json' -type f | grep . >/dev/null; php "$REPAIR" --run="$HARD" | tee "$ART/hard-recovery.json" | jq -e '.ok==true and .interrupted_recovered==true and .schema=="2026082901"' >/dev/null; verify_target "$HARD"; echo P01_V2330_FORMAL_INTERRUPTION_RECOVERY=PASS | tee "$ART/hard-verdict.txt"

FRESH=/tmp/p01-v2330-formal-fresh-runtime; setup_root "$FRESH" candidate/src 18683 "$PASS" fresh; verify_target "$FRESH" || { php "$FRESH/cli/verify.php"; exit 1; }; echo P01_V2330_FORMAL_FRESH_INSTALL=PASS | tee "$ART/fresh-verdict.txt"
cat >"$ART/verdict.txt" <<EOF
P01_V2330_FORMAL_RELEASE_SOURCE=$FORMAL
P01_V2330_FORMAL_RELEASE_TREE=$FORMAL_TREE
P01_V2330_RUNTIME_TREE=$RUNTIME_TREE
P01_V2330_FORMAL_ARTIFACT_GATE=PASS
P01_V2330_HEALTH_TRIAGE_V4_BINDING=PASS
P01_V2330_CANDIDATE_READINESS_BINDING=PASS
P01_V2320_TO_V2330_ACTUAL_UPGRADE=PASS
P01_V2330_DATA_PRESERVATION=PASS
P01_V2330_IDEMPOTENCE=PASS
P01_V2330_FAILURE_ROLLBACK=PASS
P01_V2330_INTERRUPTION_RECOVERY=PASS
P01_V2330_FRESH_INSTALL=PASS
P01_V2330_SCHEMA_UNCHANGED_2026082901=PASS
RELEASE_PUBLISHED=NO
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$ART/verdict.txt"
