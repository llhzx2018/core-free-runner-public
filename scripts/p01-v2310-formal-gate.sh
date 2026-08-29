#!/usr/bin/env bash
set -Eeuo pipefail

FORMAL='0dfc6c7b1b76ca3cec750daed97f5c4ba51b47f4'
FORMAL_TREE='f568820198afde57fe3c1522820f45bbbf6e0c96'
PRODUCT='d541b7bb18d40705ec03f951fad3ed661aa11991'
PRODUCT_TREE='7e5eaed15187f48686ae3eb67ff91a63085ca003'
RUNTIME_TREE='772d51ebbc9f8cd6791c0601d29f6b3b2a95a086'
SOURCE='40b2d5239c557ab6c7b9aaaa092acffa9fb926f9'
SOURCE_TREE='771125988f07c01740e4b3dc3863ff90ebcdc5dd'
SOURCE_RUNTIME_TREE='500d485c5eda15f65cd59a61c5a6ad5a7c519f8b'
SCHEMA='2026082901'
ART=/tmp/p01-v2310-formal-evidence
rm -rf "$ART" /tmp/p01-v2310-*runtime /tmp/p01-v2310-artifacts
mkdir -p "$ART"

test "$(git -C candidate rev-parse HEAD)" = "$FORMAL"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$FORMAL_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$RUNTIME_TREE"
test "$(git -C candidate rev-parse "$PRODUCT^{tree}")" = "$PRODUCT_TREE"
test "$(git -C candidate rev-parse "$PRODUCT:src")" = "$RUNTIME_TREE"
git -C candidate diff --quiet "$PRODUCT" "$FORMAL" -- src
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = '2.31.0'
test "$(cat candidate/src/VERSION.txt)" = '2.31.0'
test "$(cat production/VERSION)" = '2.30.0'
test "$(cat production/src/VERSION.txt)" = '2.30.0'
grep -F "define('VF_VERSION', '2.31.0')" candidate/src/app/bootstrap.php >/dev/null
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find candidate/src -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find candidate/src -type f -name '*.js' -print0)
echo P01_V2310_FORMAL_SOURCE_SYNTAX=PASS

python3 runner/scripts/p01-v2310-build-artifacts.py | tee "$ART/build.json"
REPAIR=/tmp/p01-v2310-artifacts/repair-v2.31.0.php
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee "$ART/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null
jq -e '.status=="FORMAL_ARTIFACT_BUILD_PASS" and .release_source=="0dfc6c7b1b76ca3cec750daed97f5c4ba51b47f4" and .product_source=="d541b7bb18d40705ec03f951fad3ed661aa11991" and .schema=="2026082901" and .schema_change==false and .runtime_delta_count==6 and .owner_production_write==false' /tmp/p01-v2310-artifacts/P01-V2.31.0-FORMAL-GATE.json >/dev/null
echo P01_V2310_FORMAL_ARTIFACT_BUILD=PASS

PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
start_server(){
  local root="$1" port="$2" log="$3"
  php -d display_errors=1 -d log_errors=1 -d error_reporting=E_ALL -S "127.0.0.1:${port}" -t "$root" >"$log" 2>&1 &
  local pid=$!; PIDS+=("$pid")
  for i in $(seq 1 40); do curl -fsS "http://127.0.0.1:${port}/setup.php" -o /dev/null && break || sleep 0.25; done
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
    --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=P01 V2.31 Formal Gate" \
    --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" -o "$ART/${label}-setup-post.html"
  kill "$pid" >/dev/null 2>&1 || true
  php "$root/cli/verify.php" | tee "$ART/${label}-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
}
seed_source(){
  local root="$1" label="$2"
  cat >"$ART/${label}-seed.php" <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$r=new VfRepository(vf_db());
$pub=$r->createCategory(['name'=>'V231公开分类','is_private'=>false,'sort_order'=>20]);
$priv=$r->createCategory(['name'=>'V231私人分类','is_private'=>true,'sort_order'=>10]);
$r->saveLink(null,['category_id'=>$pub,'title'=>'V231公开保留项','url'=>'https://example.com/v231-public','is_private'=>false,'is_favorite'=>true,'tags'=>['V231','公开']]);
$r->saveLink(null,['category_id'=>$priv,'title'=>'V231私人保留项','url'=>'https://example.com/v231-private','is_private'=>true,'tags'=>['V231','私人']]);
$db=vf_db();$out=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn()];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V2310_SOURCE_SEED=PASS\n";
PHP
  ROOT="$root" OUT="$ART/${label}-before.json" php "$ART/${label}-seed.php" | grep -Fx P01_V2310_SOURCE_SEED=PASS >/dev/null
  jq -e '.schema=="2026082901" and .links>=2 and .categories>=2 and .favorites>=1' "$ART/${label}-before.json" >/dev/null
}
verify_target(){
  local root="$1" label="$2"
  ROOT="$root" OUT="$ART/${label}-after.json" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();
$head=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();if($head!=='2026082901')throw new RuntimeException('schema '.$head);
$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($i!=='ok'||$fk)throw new RuntimeException('db integrity');
$out=['schema'=>$head,'links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE title='V231私人保留项' AND is_private=1")->fetchColumn(),'public'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE title='V231公开保留项' AND is_private=0")->fetchColumn(),'integrity'=>$i,'fk'=>count($fk)];
file_put_contents(getenv('OUT'),json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "P01_V2310_TARGET_VERIFY=PASS\n";
PHP
  local before="$ART/${label}-before.json"
  test "$(jq -r .links "$before")" = "$(jq -r .links "$ART/${label}-after.json")"
  test "$(jq -r .categories "$before")" = "$(jq -r .categories "$ART/${label}-after.json")"
  test "$(jq -r .favorites "$before")" = "$(jq -r .favorites "$ART/${label}-after.json")"
  jq -e '.schema=="2026082901" and .private==1 and .public==1 and .integrity=="ok" and .fk==0' "$ART/${label}-after.json" >/dev/null
  test "$(cat "$root/VERSION.txt")" = '2.31.0'
  grep -F "define('VF_VERSION', '2.31.0')" "$root/app/bootstrap.php" >/dev/null
  php "$root/cli/verify.php" | grep -Fx VERIFY_PASS=YES >/dev/null
}
verify_source_rollback(){
  local root="$1"
  test "$(cat "$root/VERSION.txt")" = '2.30.0'
  grep -F "define('VF_VERSION', '2.30.0')" "$root/app/bootstrap.php" >/dev/null
  ROOT="$root" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);if((int)$db->query("SELECT COUNT(*) FROM links WHERE title=\"V231私人保留项\" AND is_private=1")->fetchColumn()!==1)exit(3);echo "P01_V2310_SOURCE_ROLLBACK=PASS\n";' | grep -Fx P01_V2310_SOURCE_ROLLBACK=PASS >/dev/null
}

PASS='P01V2310Formal!2026'
UP=/tmp/p01-v2310-upgrade-runtime
setup_root "$UP" production/src 18640 "$PASS" upgrade
seed_source "$UP" upgrade
php "$REPAIR" --verify-source="$UP" | jq -e '.ok==true' >/dev/null
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
verify_target "$UP" upgrade
php "$REPAIR" --run="$UP" | tee "$ART/upgrade-idempotent.json" | jq -e '.ok==true and .already_current==true and .schema=="2026082901"' >/dev/null
php "$REPAIR" --verify-target="$UP" | jq -e '.ok==true' >/dev/null
echo P01_V230_TO_V2310_ACTUAL_UPGRADE_DATA=PASS

FAILROOT=/tmp/p01-v2310-fail-runtime
setup_root "$FAILROOT" production/src 18642 "$PASS" fail
seed_source "$FAILROOT" fail
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$REPAIR" --run="$FAILROOT" >"$ART/fail-run.out" 2>"$ART/fail-run.err"
RC=$?
set -e
test "$RC" -ne 0
verify_source_rollback "$FAILROOT"
test ! -f "$FAILROOT/private_data/updates/p01-atomic-transaction.json"
echo P01_V2310_FAILURE_ROLLBACK=PASS

HARD=/tmp/p01-v2310-hard-runtime
setup_root "$HARD" production/src 18643 "$PASS" hard
seed_source "$HARD" hard
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$REPAIR" --run="$HARD" >"$ART/hard-run.out" 2>"$ART/hard-run.err"
RC=$?
set -e
test "$RC" = 97
find "$HARD" -path '*/updates/p01-atomic-transaction.json' -type f | grep . >/dev/null
php "$REPAIR" --run="$HARD" | tee "$ART/hard-recovery.json" | jq -e '.ok==true and .interrupted_recovered==true and .schema=="2026082901"' >/dev/null
verify_target "$HARD" hard
echo P01_V2310_INTERRUPTION_RECOVERY=PASS

FRESH=/tmp/p01-v2310-fresh-runtime
setup_root "$FRESH" candidate/src 18644 "$PASS" fresh
ROOT="$FRESH" php -r 'require getenv("ROOT")."/app/bootstrap.php";$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status=\"success\"")->fetchColumn();if($h!=="2026082901")exit(2);if(VF_VERSION!=="2.31.0")exit(3);echo "P01_V2310_FRESH_SCHEMA=PASS\n";' | grep -Fx P01_V2310_FRESH_SCHEMA=PASS >/dev/null
for p in start.php channels.php watch.php topics.php; do php -r '$p=$argv[1]; if(!is_file($p)) exit(2);' "$FRESH/$p"; done
echo P01_V2310_FRESH_INSTALL=PASS

echo P01_V2310_FORMAL_ARTIFACT_GATE=PASS
