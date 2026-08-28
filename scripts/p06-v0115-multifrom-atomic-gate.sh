#!/usr/bin/env bash
set -Eeuo pipefail
: "${GH_TOKEN:?GH_TOKEN required}"

ROOT="$RUNNER_TEMP/p06-v0115-multifrom"
REPO="$ROOT/repo"
UPDATE="$ROOT/VF_Press_V0.1.15_UPDATE.zip"
UPDATE_BYTES='278578'
UPDATE_SHA='152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe'
RELEASE_SOURCE='a9300382d3a862fb599b8b928961ead38dee8f31'
rm -rf "$ROOT"
mkdir -p "$ROOT"

gh repo clone llhzx2018/vf-press "$REPO" >/dev/null
for spec in \
  '0.1.12:6d4e0e4a5fd02ec625012bca02acc9399b724aa6' \
  '0.1.13:cec5ecd28b3cdc585d1b7cac17a9e2167d520ea1' \
  '0.1.14:d689b79a6f1d98f0bf5bccba438f3c9a74077782'; do
  version="${spec%%:*}"; sha="${spec#*:}"
  git -C "$REPO" cat-file -e "$sha^{commit}"
  git -C "$REPO" worktree add --detach "$ROOT/src-$version" "$sha" >/dev/null
  test "$(tr -d '\r\n' < "$ROOT/src-$version/VERSION")" = "$version"
done

test "$(git -C "$REPO" rev-parse origin/main)" = "$RELEASE_SOURCE"
gh release download v0.1.15 -R llhzx2018/vf-press -p 'VF_Press_V0.1.15_UPDATE.zip' -D "$ROOT"
test "$(stat -c %s "$UPDATE")" = "$UPDATE_BYTES"
test "$(sha256sum "$UPDATE" | awk '{print $1}')" = "$UPDATE_SHA"
python3 - "$UPDATE" <<'PY'
import json,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    c=json.loads(z.read('VF_UPDATE.json'))
    assert c['schema']=='vf-press-update/v1'
    assert c['project_id']=='P06'
    assert c['target_version']=='0.1.15'
print('P06_V0115_OFFICIAL_UPDATE_CONTRACT=PASS')
PY

run_upgrade() {
  local from="$1"
  local src="$ROOT/src-$from"
  local app="$ROOT/app-$from"
  local storage="$ROOT/storage-$from"
  local db="$storage/app.db"
  rm -rf "$app" "$storage"
  mkdir -p "$app" "$storage"
  rsync -a --exclude='.git' "$src/" "$app/"
  (cd "$app" && composer install --no-interaction --prefer-dist --no-progress)

  export APP_ENV=test
  export VF_PRESS_STORAGE_PATH="$storage"
  export VF_PRESS_DB_PATH="$db"
  export VF_PRESS_OWNER_USERNAME="owner-${from//./-}"
  export VF_PRESS_OWNER_PASSWORD='P06-MultiFrom-Owner-Password-2026!'
  export VF_PRESS_OWNER_DISPLAY_NAME="Owner $from"
  (cd "$app" && php bin/migrate.php)
  test "$(sqlite3 "$db" 'SELECT MAX(version) FROM schema_migrations;')" = '3'
  (cd "$app" && php bin/create-owner.php)
  sqlite3 "$db" "CREATE TABLE vf_multifrom_sentinel(k TEXT PRIMARY KEY,v TEXT NOT NULL); INSERT INTO vf_multifrom_sentinel VALUES('owner-data','PRESERVE-$from-TO-0.1.15');"
  test "$(tr -d '\r\n' < "$app/VERSION")" = "$from"

  export P06_MF_APP="$app"
  export P06_MF_STORAGE="$storage"
  export P06_MF_DB="$db"
  export P06_MF_ZIP="$UPDATE"
  export P06_MF_FROM="$from"
  export P06_MF_SHA="$UPDATE_SHA"
  export P06_MF_BYTES="$UPDATE_BYTES"
  cat > "$ROOT/atomic-$from.php" <<'PHP'
<?php
declare(strict_types=1);
use CoreUpdates\UpdateCore;
use VF\Press\Infrastructure\Config\AppConfig;
use VF\Press\Infrastructure\Recovery\RecoveryService;
use VF\Press\Infrastructure\Security\AuditLogger;
use VF\Press\Infrastructure\Update\VFPressUpdateAdapter;
$app=(string)getenv('P06_MF_APP'); $storage=(string)getenv('P06_MF_STORAGE'); $db=(string)getenv('P06_MF_DB'); $zip=(string)getenv('P06_MF_ZIP'); $from=(string)getenv('P06_MF_FROM');
require $app.'/vendor/autoload.php';
$config=new AppConfig($app,$storage,$db,'test'); $config->ensureRuntimeDirectories();
$pdo=new PDO('sqlite:'.$db); $pdo->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION); $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE,PDO::FETCH_ASSOC); $pdo->exec('PRAGMA foreign_keys=ON');
$audit=new AuditLogger($pdo); $recovery=new RecoveryService($pdo,$audit,$storage,$db); $adapter=new VFPressUpdateAdapter($pdo,$config,$audit,$recovery); $core=new UpdateCore('P06');
$manifest=[
 'schema_version'=>'1.0','project_id'=>'P06','component_id'=>'APP','enabled'=>true,
 'target_version'=>'0.1.15','update_type'=>'ATOMIC','from_versions'=>[$from],
 'schema_from'=>'3','schema_to'=>'3','repository'=>'llhzx2018/vf-press','release_tag'=>'v0.1.15',
 'release_id'=>378572142,'product_identity'=>'a9300382d3a862fb599b8b928961ead38dee8f31',
 'asset_name'=>'VF_Press_V0.1.15_UPDATE.zip','asset_bytes'=>(int)getenv('P06_MF_BYTES'),'asset_sha256'=>(string)getenv('P06_MF_SHA'),
 'backup_required'=>true,'rollback_supported'=>true,'minimum_php'=>'8.2.0','released_at'=>'2026-08-28T15:18:03Z'
];
$result=$core->upgrade($from,'3',$adapter,$zip,$manifest);
$status=(string)($result['status']??'');
if (!in_array($status,['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)) throw new RuntimeException('Atomic update failed from '.$from.': '.json_encode($result));
echo 'P06_V0115_FROM_'.$from.'_ATOMIC_STATUS='.$status."\n";
PHP
  php "$ROOT/atomic-$from.php"

  test "$(tr -d '\r\n' < "$app/VERSION")" = '0.1.15'
  test "$(sqlite3 "$db" 'SELECT MAX(version) FROM schema_migrations;')" = '3'
  test "$(sqlite3 "$db" 'PRAGMA integrity_check;')" = 'ok'
  test "$(sqlite3 "$db" "SELECT v FROM vf_multifrom_sentinel WHERE k='owner-data';")" = "PRESERVE-$from-TO-0.1.15"
  test -d "$storage/backups"
  test -d "$storage/update-source-backups"
  test -n "$(find "$storage/update-source-backups" -type f -path '*/source/VERSION' -print -quit)"
  test "$(tr -d '\r\n' < "$(find "$storage/update-source-backups" -type f -path '*/source/VERSION' -print -quit)")" = "$from"
  (cd "$app" && php bin/preflight.php >/dev/null)
  (cd "$app" && php bin/common-baseline-v2-self-test.php >/dev/null)
  (cd "$app" && php bin/common-baseline-human-ui-self-test.php >/dev/null)
  echo "P06_V0115_FROM_${from}_POST_UPDATE=PASS"
}

run_upgrade '0.1.12'
run_upgrade '0.1.13'
run_upgrade '0.1.14'

echo 'P06_V0115_MULTI_FROM=0.1.12,0.1.13,0.1.14'
echo P06_V0115_MULTI_FROM_ATOMIC_GATE=PASS
