#!/usr/bin/env bash
set -Eeuo pipefail

: "${CANDIDATE:?}"
: "${CANDIDATE_TREE:?}"
: "${PRODUCTION:?}"
: "${VERSION:?}"
: "${SOURCE_VERSION:?}"
: "${SCHEMA:?}"

install_instance() {
  local root="$1" port="$2" title="$3" password="$4" prefix="$5"
  rm -f "/tmp/${prefix}.cookies" "/tmp/${prefix}-setup.html" "/tmp/${prefix}-result.html"
  php -S "127.0.0.1:${port}" -t "$root" >"/tmp/${prefix}-server.log" 2>&1 &
  local pid=$!
  local ok=0
  for _ in $(seq 1 30); do
    if curl -fsS -c "/tmp/${prefix}.cookies" "http://127.0.0.1:${port}/setup.php" -o "/tmp/${prefix}-setup.html"; then ok=1; break; fi
    sleep 1
  done
  if [[ "$ok" != 1 ]]; then cat "/tmp/${prefix}-server.log" >&2 || true; kill "$pid" || true; return 1; fi
  local csrf
  csrf="$(python3 - "/tmp/${prefix}-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
print(m.group(1) if m else '')
PY
)"
  if [[ -z "$csrf" ]]; then cat "/tmp/${prefix}-setup.html" >&2; kill "$pid" || true; return 1; fi
  curl -fsS -b "/tmp/${prefix}.cookies" -c "/tmp/${prefix}.cookies" -X POST "http://127.0.0.1:${port}/setup.php" \
    --data-urlencode "setup_csrf=${csrf}" \
    --data-urlencode "site_title=${title}" \
    --data-urlencode "admin_password=${password}" \
    --data-urlencode "admin_password_confirm=${password}" \
    -o "/tmp/${prefix}-result.html"
  kill "$pid" || true
  wait "$pid" 2>/dev/null || true
  test -f "$root/app/.runtime.php"
  php "$root/cli/verify.php" | tee "/tmp/${prefix}-verify.txt"
  grep -q 'VERIFY_PASS=YES' "/tmp/${prefix}-verify.txt"
}

fresh_copy_install() {
  local dest="$1" port="$2" title="$3" password="$4" prefix="$5"
  rm -rf "$dest"
  cp -a production/src "$dest"
  install_instance "$dest" "$port" "$title" "$password" "$prefix"
}

echo '=== P01 FORMAL CANDIDATE V2 ==='
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C production rev-parse HEAD)" = "$PRODUCTION"
test "$(tr -d '\r\n' < candidate/VERSION)" = "$VERSION"
test "$(tr -d '\r\n' < production/VERSION)" = "$SOURCE_VERSION"
diff -qr candidate/src/browser-extension production/src/browser-extension >/dev/null
echo 'EXACT_SOURCE_AND_EXTENSION_IDENTITY=PASS'

rm -rf dist
python3 runner/scripts/p01-build-release-v2.py \
  --candidate candidate/src \
  --production production/src \
  --out dist \
  --candidate-commit "$CANDIDATE" \
  --candidate-tree "$CANDIDATE_TREE" \
  --production-commit "$PRODUCTION"
for f in \
  "VF_Start_V${VERSION}_FULL.zip" \
  "VF_Start_V${VERSION}_SOURCE.zip" \
  "VF_Start_V${VERSION}_ATOMIC.zip" \
  "VF_Start_V${VERSION}_UPDATE.zip" \
  "repair-v${VERSION}.php" \
  "P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" \
  "VF_Start_V${VERSION}_RELEASE_MANIFEST.json" \
  "VF_Start_V${VERSION}_RELEASE_NOTES.md" \
  SHA256SUMS.txt; do test -f "dist/$f"; done
echo 'FORMAL_BYTES_BUILT=PASS'

python3 - <<'PY'
import pathlib,re,zipfile
root=pathlib.Path('dist')
for p in root.glob('*.zip'):
    with zipfile.ZipFile(p) as z:
        names=z.namelist()
        if len(names)!=len(set(names)): raise SystemExit(f'duplicate member: {p}')
        for n in names:
            q=pathlib.PurePosixPath(n)
            if n.startswith('/') or '..' in q.parts or '\\' in n: raise SystemExit(f'unsafe path: {p}:{n}')
            if ((z.getinfo(n).external_attr>>16)&0o170000)==0o120000: raise SystemExit(f'symlink: {p}:{n}')
for kind in ('UPDATE','ATOMIC'):
    p=root/f'VF_Start_V2.21.15_{kind}.zip'
    with zipfile.ZipFile(p) as z:
        if z.namelist()!=['repair-v2.21.15.php']: raise SystemExit(f'{kind} member contract failed')
        if z.read('repair-v2.21.15.php')!=(root/'repair-v2.21.15.php').read_bytes(): raise SystemExit(f'{kind} repair byte mismatch')
bad=re.compile(rb'(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|VF_PRIVATE_READ_TOKEN\s*=\s*[^\s]+|VF_RELEASE_WRITE_TOKEN\s*=\s*[^\s]+)')
for p in root.iterdir():
    if p.is_file() and bad.search(p.read_bytes()): raise SystemExit(f'secret-like payload: {p.name}')
with zipfile.ZipFile(root/'VF_Start_V2.21.15_FULL.zip') as z:
    names=set(z.namelist())
    for n in names:
        low=n.lower()
        if '.vfnav-data-' in low or low.endswith(('.sqlite','.sqlite3','.db','.log','.env')) or '/private_data/' in low:
            raise SystemExit(f'FULL private/runtime contamination: {n}')
PY
(cd dist && sha256sum -c SHA256SUMS.txt)
for kind in FULL SOURCE ATOMIC UPDATE; do unzip -t "dist/VF_Start_V${VERSION}_${kind}.zip" >/dev/null; done
echo 'FINAL_BYTES_STRUCTURE_PRIVACY=PASS'

docker run --rm -v "$PWD:/work:ro" -w /work php:8.0-cli php -l "dist/repair-v${VERSION}.php" >/dev/null
docker run --rm -v "$PWD:/work:ro" -w /work php:8.0-cli php -l "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" >/dev/null
php "dist/repair-v${VERSION}.php" --self-test | tee /tmp/p01-atomic-selftest.json
php "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" --self-test | tee /tmp/p01-bridge-selftest.json
grep -q '"global_barrier":true' /tmp/p01-atomic-selftest.json
grep -q '"interruption_recovery":true' /tmp/p01-atomic-selftest.json
echo 'PHP80_ATOMIC_BRIDGE_SELFTEST=PASS'

rm -rf /tmp/p01-final-target && mkdir -p /tmp/p01-final-target
unzip -q "dist/VF_Start_V${VERSION}_FULL.zip" -d /tmp/p01-final-target
php "dist/repair-v${VERSION}.php" --verify-source=production/src | tee /tmp/p01-source-verify.json
php "dist/repair-v${VERSION}.php" --verify-target=/tmp/p01-final-target | tee /tmp/p01-target-verify.json
grep -q '"ok":true' /tmp/p01-source-verify.json
grep -q '"ok":true' /tmp/p01-target-verify.json
php /tmp/p01-final-target/cli/verify.php | tee /tmp/p01-final-seed-verify.txt
grep -q 'VERIFY_PASS=YES' /tmp/p01-final-seed-verify.txt
echo 'EXACT_MANIFEST_AND_FINAL_SEED=PASS'

rm -rf /tmp/p01-bridge && cp -a production/src /tmp/p01-bridge
before_version="$(sha256sum /tmp/p01-bridge/VERSION.txt | awk '{print $1}')"
before_migrations="$(find /tmp/p01-bridge/migrations -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
php "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" --run=/tmp/p01-bridge | tee /tmp/p01-bridge-run.json
test "$(tr -d '\r\n' < /tmp/p01-bridge/VERSION.txt)" = "$SOURCE_VERSION"
test "$(sha256sum /tmp/p01-bridge/VERSION.txt | awk '{print $1}')" = "$before_version"
test "$(find /tmp/p01-bridge/migrations -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')" = "$before_migrations"
test -f /tmp/p01-bridge/app/CoreUpdates/UpdateCore.php
test -f /tmp/p01-bridge/app/CoreUpdates/GitHubClient.php
php "dist/repair-v${VERSION}.php" --verify-source=/tmp/p01-bridge | grep -q '"ok":true'
php "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" --run=/tmp/p01-bridge | tee /tmp/p01-bridge-repeat.json
grep -q '"already_applied":true' /tmp/p01-bridge-repeat.json
echo 'DISCOVERY_BRIDGE_EXACT_MINIMAL_IDEMPOTENT=PASS'

rm -rf /tmp/p01-fresh && mkdir -p /tmp/p01-fresh
unzip -q "dist/VF_Start_V${VERSION}_FULL.zip" -d /tmp/p01-fresh
install_instance /tmp/p01-fresh 18101 'VF Start Fresh Runner' 'P01Fresh!22115Runner' p01fresh
php -r 'require "/tmp/p01-fresh/app/bootstrap.php";$d=vf_db();foreach(["categories","links","import_batches","backup_records","operation_history"] as $t){$n=(int)$d->query("SELECT COUNT(*) FROM $t")->fetchColumn();if($n!==0){fwrite(STDERR,"$t=$n\n");exit(1);}}echo "FRESH_BUSINESS_RUNTIME_DATA_ZERO=PASS\n";'
echo 'FRESH_INSTALL_FINAL_FULL=PASS'

fresh_copy_install /tmp/p01-upgrade 18102 'VF Start Upgrade Runner' 'P01Upgrade!22114Runner' p01upgrade
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$r=new VfRepository(vf_db());$c=$r->createCategory(["name"=>"Runner Sentinel","description"=>"upgrade preservation","is_private"=>1]);$r->saveLink(null,["category_id"=>$c,"title"=>"Runner Link","url"=>"https://example.com/?p01=22114","description"=>"keep me","is_private"=>1]);$b=(new VfBackupManager(vf_db()))->create("P01 pre-upgrade runner","pre-update",true);file_put_contents("/tmp/p01-backup-key",$b["backup_key"]);echo "PRE_UPGRADE_SENTINEL_AND_BACKUP=PASS\n";'
php "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" --run=/tmp/p01-upgrade | tee /tmp/p01-upgrade-bridge.json
test "$(tr -d '\r\n' < /tmp/p01-upgrade/VERSION.txt)" = "$SOURCE_VERSION"
php "dist/repair-v${VERSION}.php" --run=/tmp/p01-upgrade | tee /tmp/p01-upgrade-run.json
test "$(tr -d '\r\n' < /tmp/p01-upgrade/VERSION.txt)" = "$VERSION"
php /tmp/p01-upgrade/cli/verify.php | tee /tmp/p01-upgrade-verify.txt
grep -q 'VERIFY_PASS=YES' /tmp/p01-upgrade-verify.txt
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$d=vf_db();$n=(int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Runner Link\" AND url=\"https://example.com/?p01=22114\"")->fetchColumn();if($n!==1)exit(1);$k=trim(file_get_contents("/tmp/p01-backup-key"));$v=(new VfBackupManager($d))->verify($k);if(($v["validation_status"]??"")!=="valid")exit(2);echo "UPGRADE_DATA_AND_BACKUP=PASS\n";'
php "dist/repair-v${VERSION}.php" --run=/tmp/p01-upgrade | tee /tmp/p01-upgrade-repeat.json
grep -q '"already_current":true' /tmp/p01-upgrade-repeat.json
echo 'EXACT_UPGRADE_AND_IDEMPOTENT_REPEAT=PASS'

# Actual product Backup/Restore after upgrade: mutate live data, restore pre-upgrade snapshot,
# confirm restored data is migrated to current code and the post-backup mutation disappears.
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$r=new VfRepository(vf_db());$c=$r->createCategory(["name"=>"Post Upgrade Mutation","is_private"=>1]);$r->saveLink(null,["category_id"=>$c,"title"=>"Must Disappear After Restore","url"=>"https://example.com/post-upgrade","is_private"=>1]);echo "POST_UPGRADE_MUTATION=PASS\n";'
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$k=trim(file_get_contents("/tmp/p01-backup-key"));$x=VfBackupManager::performRestore($k);if(empty($x["restored"])||($x["integrity"]??"")!=="ok"||(int)($x["foreign_key_errors"]??-1)!==0)exit(1);echo "PRODUCT_RESTORE_EXECUTED=PASS\n";'
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$d=vf_db();$keep=(int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Runner Link\"")->fetchColumn();$gone=(int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Must Disappear After Restore\"")->fetchColumn();if($keep!==1||$gone!==0)exit(1);echo "BACKUP_RESTORE_DATA_SEMANTICS=PASS\n";'
php /tmp/p01-upgrade/cli/verify.php | grep -q 'VERIFY_PASS=YES'
echo 'BACKUP_RESTORE_REAL_PATH=PASS'

fresh_copy_install /tmp/p01-rollback 18103 'VF Start Rollback Runner' 'P01Rollback!22114Runner' p01rollback
php -r 'require "/tmp/p01-rollback/app/bootstrap.php";$r=new VfRepository(vf_db());$c=$r->createCategory(["name"=>"Rollback Sentinel","is_private"=>1]);$r->saveLink(null,["category_id"=>$c,"title"=>"Rollback Link","url"=>"https://example.org/rollback","is_private"=>1]);'
php "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" --run=/tmp/p01-rollback >/dev/null
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "dist/repair-v${VERSION}.php" --run=/tmp/p01-rollback >/tmp/p01-rollback.out 2>/tmp/p01-rollback.err
rollback_rc=$?
set -e
test "$rollback_rc" -ne 0
test "$(tr -d '\r\n' < /tmp/p01-rollback/VERSION.txt)" = "$SOURCE_VERSION"
php "dist/repair-v${VERSION}.php" --verify-source=/tmp/p01-rollback | grep -q '"ok":true'
php -r 'require "/tmp/p01-rollback/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Rollback Link\"")->fetchColumn()!==1)exit(1);echo "ROLLBACK_DATA_PRESERVED=PASS\n";'
php /tmp/p01-rollback/cli/verify.php | grep -q 'VERIFY_PASS=YES'
echo 'FAILURE_ROLLBACK=PASS'

fresh_copy_install /tmp/p01-interrupted 18104 'VF Start Interrupted Runner' 'P01Interrupted!22114Runner' p01interrupted
php -r 'require "/tmp/p01-interrupted/app/bootstrap.php";$r=new VfRepository(vf_db());$c=$r->createCategory(["name"=>"Interrupted Sentinel","is_private"=>1]);$r->saveLink(null,["category_id"=>$c,"title"=>"Interrupted Link","url"=>"https://example.net/interrupted","is_private"=>1]);'
php "dist/P01_V${SOURCE_VERSION}_DISCOVERY_BRIDGE.php" --run=/tmp/p01-interrupted >/dev/null
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "dist/repair-v${VERSION}.php" --run=/tmp/p01-interrupted >/tmp/p01-interrupted-hard.out 2>/tmp/p01-interrupted-hard.err
interrupt_rc=$?
set -e
test "$interrupt_rc" = 97
php "dist/repair-v${VERSION}.php" --run=/tmp/p01-interrupted | tee /tmp/p01-interrupted-retry.json
grep -q '"interrupted_recovered":true' /tmp/p01-interrupted-retry.json
test "$(tr -d '\r\n' < /tmp/p01-interrupted/VERSION.txt)" = "$VERSION"
php -r 'require "/tmp/p01-interrupted/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Interrupted Link\"")->fetchColumn()!==1)exit(1);echo "INTERRUPTED_DATA_PRESERVED=PASS\n";'
php /tmp/p01-interrupted/cli/verify.php | grep -q 'VERIFY_PASS=YES'
echo 'HARD_INTERRUPTION_RECOVERY_AND_RETRY=PASS'

# Missing credential is fail-closed in the real P01 adapter. The test callback makes
# manifest transport deterministic; the absence of VF_PRIVATE_READ_TOKEN must still block installability.
cat >/tmp/p01-update-status-test.php <<'PHP'
<?php
declare(strict_types=1);
require '/tmp/p01-fresh/app/bootstrap.php';
putenv('VF_PRIVATE_READ_TOKEN');
$manifest=[
 'schema_version'=>'1.0','project_id'=>'P01','component_id'=>'APP','enabled'=>true,
 'target_version'=>'2.21.16','update_type'=>'ATOMIC','from_versions'=>['2.21.15'],
 'schema_from'=>'2026080902','schema_to'=>'2026080902','repository'=>'llhzx2018/vf-start',
 'release_tag'=>'v2.21.16','asset_name'=>'VF_Start_V2.21.16_UPDATE.zip','asset_bytes'=>1,
 'asset_sha256'=>str_repeat('0',64),'backup_required'=>true,'rollback_supported'=>true,
 'released_at'=>'2026-08-15T00:00:00Z','minimum_php'=>'8.0.0'
];
$u=new VfUpdateManager(vf_db(),['manifest_fetcher'=>static fn()=> $manifest,'capabilities'=>['curl'=>true,'zip'=>true]]);
$r=$u->check(true);$s=$u->status();
if(empty($r['available'])||!empty($r['can_update'])||!empty($s['can_update'])||strpos((string)$s['reason'],'VF_PRIVATE_READ_TOKEN')===false){fwrite(STDERR,json_encode([$r,$s],JSON_UNESCAPED_UNICODE));exit(1);}echo "MISSING_CREDENTIAL_FAIL_CLOSED=PASS\n";
PHP
php /tmp/p01-update-status-test.php

echo 'P01_V2.21.15_FORMAL_CANDIDATE_V2=PASS'
echo "CANDIDATE_COMMIT=$CANDIDATE"
echo "CANDIDATE_TREE=$CANDIDATE_TREE"
echo 'SECRET_GATE=PASS'
echo 'PRIVATE_DATA_GATE=PASS'
echo 'PRODUCTION_UPGRADE=NOT_EXECUTED'
