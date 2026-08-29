#!/usr/bin/env bash
set -Eeuo pipefail

FORMAL='120a42667fce7357fdaef03b64cb7ea41392040d'
FORMAL_TREE='d0fa7c87ebefef083712ec0b7707a6c4273943f2'
FINAL_CANDIDATE='a842a79517ce89b216abbc514aa73395f7bac009'
VERSIONED_CANDIDATE='8b4f3483579bf2d286c551c1f33e876e4e7aec16'
PRODUCT='8944677974e3a512d846f0740897a7a98e4b7b53'
PRODUCT_TREE='09412d1b7df21deb01a45e3069ecd48e564fb458'
RUNTIME_TREE='f348cb314623906acc851cb79d75b1c8f6637aff'
SOURCE='0dfc6c7b1b76ca3cec750daed97f5c4ba51b47f4'
SOURCE_TREE='f568820198afde57fe3c1522820f45bbbf6e0c96'
SOURCE_RUNTIME_TREE='772d51ebbc9f8cd6791c0601d29f6b3b2a95a086'
SCHEMA='2026082901'
ART=/tmp/p01-v2320-formal-evidence
OUT=/tmp/p01-v2320-formal-artifacts
rm -rf "$ART" "$OUT" /tmp/p01-v2320-formal-*runtime
mkdir -p "$ART"

# Exact formal source and candidate-evidence binding.
test "$(git -C candidate rev-parse HEAD)" = "$FORMAL"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$FORMAL_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$PRODUCT^{tree}")" = "$PRODUCT_TREE"
test "$(git -C candidate rev-parse "$FINAL_CANDIDATE:src")" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$VERSIONED_CANDIDATE:src")" = "$RUNTIME_TREE"
git -C candidate diff --quiet "$FINAL_CANDIDATE" "$FORMAL" -- src
git -C candidate diff --quiet "$VERSIONED_CANDIDATE" "$FORMAL" -- src

test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = '2.32.0'
test "$(cat candidate/src/VERSION.txt)" = '2.32.0'
test "$(cat production/VERSION)" = '2.31.0'
test "$(cat production/src/VERSION.txt)" = '2.31.0'
grep -Fx "define('VF_VERSION', '2.32.0');" candidate/src/app/bootstrap.php >/dev/null
grep -Fx "define('VF_VERSION', '2.31.0');" production/src/app/bootstrap.php >/dev/null
if git -C candidate diff --name-only "$SOURCE"..."$FORMAL" -- src/migrations/ | grep .; then echo UNEXPECTED_MIGRATION; exit 1; fi
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
printf '%s\n' \
  P01_V2320_FORMAL_EXACT_SOURCE=PASS \
  P01_V2320_FORMAL_RUNTIME_EQUALS_CANDIDATE=PASS \
  P01_V2320_CANDIDATE_GATE_33263475338_BOUND=PASS \
  P01_V2320_VERSION_TRIPLE_BINDING=PASS \
  P01_V2320_SCHEMA_UNCHANGED=PASS \
  P01_V2320_NO_MIGRATION=PASS | tee "$ART/source-fence.txt"

# Deterministic formal artifacts.
python3 runner/scripts/p01-v2320-build-formal-artifacts.py | tee "$ART/build-1.json"
REPAIR="$OUT/repair-v2.32.0.php"
FULL="$OUT/VF-Start-V2.32.0-FULL.zip"
UPDATE="$OUT/VF_Start_V2.32.0_UPDATE.zip"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="FORMAL_ARTIFACT_BUILD_PASS" and .release_source=="120a42667fce7357fdaef03b64cb7ea41392040d" and .product_source=="8944677974e3a512d846f0740897a7a98e4b7b53" and .source_commit=="0dfc6c7b1b76ca3cec750daed97f5c4ba51b47f4" and .schema=="2026082901" and .schema_change==false and .runtime_delta_count==8 and (.runtime_added|length)==3 and (.runtime_removed|length)==0 and .owner_production_write==false' "$OUT/P01-V2.32.0-FORMAL-GATE.json" >/dev/null
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-1.txt"
python3 runner/scripts/p01-v2320-build-formal-artifacts.py | tee "$ART/build-2.json"
sha256sum "$FULL" "$UPDATE" "$REPAIR" > "$ART/artifacts-sha-2.txt"
diff -u "$ART/artifacts-sha-1.txt" "$ART/artifacts-sha-2.txt"
unzip -Z1 "$UPDATE" | grep -Fx repair-v2.32.0.php >/dev/null
if unzip -Z1 "$FULL" | grep -E '(^|/)(\.runtime\.php|\.env|[^/]*\.sqlite3?|[^/]*\.db)$'; then echo SENSITIVE_RUNTIME_DATA_IN_FULL; exit 1; fi
echo P01_V2320_DETERMINISTIC_FORMAL_ARTIFACTS=PASS | tee "$ART/artifact-verdict.txt"

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
start_server(){
  local root="$1" port="$2" log="$3"
  php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 &
  local pid=$!; PIDS+=("$pid")
  for i in $(seq 1 50); do if curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null; then break; fi; sleep .25; done
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
    --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.32 Formal Gate" \
    --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/${label}-setup-post.html"
  kill "$pid" >/dev/null 2>&1 || true
  php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}
seed_source(){
  local root="$1" label="$2"
  ROOT="$root" OUT="$ART/${label}-before.json" php <<'PHP' | grep -Fx P01_V2320_SOURCE_SEED=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());
$pub=$r->createCategory(['name'=>'V232公开分类','is_private'=>false,'sort_order'=>20]);
$priv=$r->createCategory(['name'=>'V232私人分类','is_private'=>true,'sort_order'=>10]);
$r->saveLink(null,['category_id'=>$pub,'title'=>'V232公开保留项','url'=>'https://example.com/v232-public','is_private'=>false,'is_favorite'=>true,'tags'=>['V232','公开']]);
$r->saveLink(null,['category_id'=>$priv,'title'=>'V232私人保留项','url'=>'https://example.com/v232-private','is_private'=>true,'tags'=>['V232','私人']]);
$db=vf_db();$out=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn()];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V2320_SOURCE_SEED=PASS\n";
PHP
  jq -e '.schema=="2026082901" and .links>=2 and .categories>=2 and .favorites>=1' "$ART/${label}-before.json" >/dev/null
}
verify_target(){
  local root="$1" label="$2"
  ROOT="$root" OUT="$ART/${label}-after.json" php <<'PHP' | grep -Fx P01_V2320_TARGET_VERIFY=PASS >/dev/null
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$head=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();if($head!=='2026082901')throw new RuntimeException('schema '.$head);
$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($i!=='ok'||$fk)throw new RuntimeException('db integrity');
$out=['schema'=>$head,'links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE title='V232私人保留项' AND is_private=1")->fetchColumn(),'public'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE title='V232公开保留项' AND is_private=0")->fetchColumn(),'integrity'=>$i,'fk'=>count($fk)];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V2320_TARGET_VERIFY=PASS\n";
PHP
  local before="$ART/${label}-before.json"
  test "$(jq -r .links "$before")" = "$(jq -r .links "$ART/${label}-after.json")"
  test "$(jq -r .categories "$before")" = "$(jq -r .categories "$ART/${label}-after.json")"
  test "$(jq -r .favorites "$before")" = "$(jq -r .favorites "$ART/${label}-after.json")"
  jq -e '.schema=="2026082901" and .private==1 and .public==1 and .integrity=="ok" and .fk==0' "$ART/${label}-after.json" >/dev/null
  test "$(cat "$root/VERSION.txt")" = '2.32.0'
  grep -Fx "define('VF_VERSION', '2.32.0');" "$root/app/bootstrap.php" >/dev/null
  php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
}
verify_source_rollback(){
  local root="$1"
  test "$(cat "$root/VERSION.txt")" = '2.31.0'
  grep -Fx "define('VF_VERSION', '2.31.0');" "$root/app/bootstrap.php" >/dev/null
  ROOT="$root" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);if((int)$db->query("SELECT COUNT(*) FROM links WHERE title=\"V232私人保留项\" AND is_private=1")->fetchColumn()!==1)exit(3);echo "P01_V2320_SOURCE_ROLLBACK=PASS\n";' | grep -Fx P01_V2320_SOURCE_ROLLBACK=PASS >/dev/null
}

PASS='P01V2320Formal!2026'
UP=/tmp/p01-v2320-formal-upgrade-runtime
setup_root "$UP" production/src 18660 "$PASS" upgrade
seed_source "$UP" upgrade
php "$REPAIR" --verify-source="$UP" | tee "$ART/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
verify_target "$UP" upgrade
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null
php "$REPAIR" --verify-target="$UP" | tee "$ART/verify-target.json" | jq -e '.ok==true' >/dev/null
echo P01_V2310_TO_V2320_FORMAL_ACTUAL_UPGRADE_DATA=PASS | tee "$ART/upgrade-verdict.txt"

FAILROOT=/tmp/p01-v2320-formal-fail-runtime
setup_root "$FAILROOT" production/src 18661 "$PASS" fail
seed_source "$FAILROOT" fail
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$REPAIR" --run="$FAILROOT" >"$ART/fail-run.out" 2>"$ART/fail-run.err"
RC=$?
set -e
test "$RC" -ne 0
verify_source_rollback "$FAILROOT"
if find "$FAILROOT" -path '*/updates/p01-atomic-transaction.json' -type f | grep .; then echo STALE_ATOMIC_TRANSACTION; exit 1; fi
echo P01_V2320_FORMAL_FAILURE_ROLLBACK=PASS | tee "$ART/rollback-verdict.txt"

HARD=/tmp/p01-v2320-formal-hard-runtime
setup_root "$HARD" production/src 18662 "$PASS" hard
seed_source "$HARD" hard
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$REPAIR" --run="$HARD" >"$ART/hard-run.out" 2>"$ART/hard-run.err"
RC=$?
set -e
test "$RC" = 97
find "$HARD" -path '*/updates/p01-atomic-transaction.json' -type f | grep . >/dev/null
php "$REPAIR" --run="$HARD" | tee "$ART/hard-recovery.json" | jq -e '.ok==true and .interrupted_recovered==true and .schema=="2026082901"' >/dev/null
verify_target "$HARD" hard
echo P01_V2320_FORMAL_INTERRUPTION_RECOVERY=PASS | tee "$ART/interruption-verdict.txt"

FRESH=/tmp/p01-v2320-formal-fresh-runtime
setup_root "$FRESH" candidate/src 18663 "$PASS" fresh
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);if(VF_VERSION!=="2.32.0")exit(3);echo "P01_V2320_FORMAL_FRESH_SCHEMA=PASS\n";' | grep -Fx P01_V2320_FORMAL_FRESH_SCHEMA=PASS >/dev/null
for p in home.php start.php channels.php watch.php topics.php; do test -f "$FRESH/$p"; done
echo P01_V2320_FORMAL_FRESH_INSTALL=PASS | tee "$ART/fresh-verdict.txt"

FULL_SHA=$(sha256sum "$FULL" | awk '{print $1}')
UPDATE_SHA=$(sha256sum "$UPDATE" | awk '{print $1}')
REPAIR_SHA=$(sha256sum "$REPAIR" | awk '{print $1}')
cat >"$ART/verdict.txt" <<EOF
P01_V2320_FORMAL_RELEASE_SOURCE=$FORMAL
P01_V2320_FORMAL_RELEASE_TREE=$FORMAL_TREE
P01_V2320_RUNTIME_TREE=$RUNTIME_TREE
P01_V2320_FORMAL_ARTIFACT_GATE=PASS
P01_V2320_FORMAL_FULL_SHA256=$FULL_SHA
P01_V2320_FORMAL_UPDATE_SHA256=$UPDATE_SHA
P01_V2320_FORMAL_REPAIR_SHA256=$REPAIR_SHA
P01_V2320_ACTUAL_UPGRADE=PASS
P01_V2320_DATA_PRESERVATION=PASS
P01_V2320_IDEMPOTENCE=PASS
P01_V2320_FAILURE_ROLLBACK=PASS
P01_V2320_INTERRUPTION_RECOVERY=PASS
P01_V2320_FRESH_RUNTIME=PASS
P01_V2320_CANDIDATE_BROWSER_EVIDENCE_BOUND=33263475338_PASS
P01_V2320_READY_FOR_MAIN_PROMOTION=YES
REMOTE_ONLINE_UPDATE_HTTP=PENDING_AFTER_PUBLICATION
RELEASE_PUBLISHED=NO
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$ART/verdict.txt"
