#!/usr/bin/env bash
set -Eeuo pipefail
: "${GH_TOKEN:?GH_TOKEN required}"
: "${VF_PRIVATE_READ_TOKEN:?VF_PRIVATE_READ_TOKEN required}"

SOURCE='6d4e0e4a5fd02ec625012bca02acc9399b724aa6'
CORE_SOURCE='0e834d734a0a1ed6b2173feee3435eb8f6015d96'
ROOT="$RUNNER_TEMP/p06-v0115-v0112-discovery"
APP="$ROOT/app"
STORAGE="$ROOT/storage"
DB="$STORAGE/app.db"
rm -rf "$ROOT" && mkdir -p "$ROOT" "$STORAGE"

gh repo clone llhzx2018/vf-press "$APP" >/dev/null
git -C "$APP" checkout --detach "$SOURCE" >/dev/null
test "$(git -C "$APP" rev-parse HEAD)" = "$SOURCE"
test "$(tr -d '\r\n' < "$APP/VERSION")" = '0.1.12'
test "$(gh api repos/llhzx2018/core-updates/git/ref/heads/main --jq .object.sha)" = "$CORE_SOURCE"

(cd "$APP" && composer install --no-interaction --prefer-dist --no-progress)
export APP_ENV=test
export VF_PRESS_STORAGE_PATH="$STORAGE"
export VF_PRESS_DB_PATH="$DB"
export VF_PRESS_OWNER_USERNAME='discovery-owner'
export VF_PRESS_OWNER_PASSWORD='P06-Discovery-Owner-Password-2026!'
export VF_PRESS_OWNER_DISPLAY_NAME='Discovery Owner'
export VF_PRIVATE_READ_TOKEN
(cd "$APP" && php bin/migrate.php >/dev/null)
test "$(sqlite3 "$DB" 'SELECT MAX(version) FROM schema_migrations;')" = '3'

cat > "$ROOT/check.php" <<'PHP'
<?php
declare(strict_types=1);
use CoreUpdates\UpdateCore;
use VF\Press\Application\Operations\OnlineUpdateService;
use VF\Press\Infrastructure\Config\AppConfig;
use VF\Press\Infrastructure\Recovery\RecoveryService;
use VF\Press\Infrastructure\Security\AuditLogger;
use VF\Press\Infrastructure\Update\VFPressUpdateAdapter;
$base=getenv('P06_DISCOVERY_APP'); $storage=getenv('VF_PRESS_STORAGE_PATH'); $db=getenv('VF_PRESS_DB_PATH');
if(!$base||!$storage||!$db) throw new RuntimeException('Discovery env missing');
require $base.'/vendor/autoload.php';
$config=new AppConfig($base,$storage,$db,'test'); $config->ensureRuntimeDirectories();
$pdo=new PDO('sqlite:'.$db); $pdo->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION); $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE,PDO::FETCH_ASSOC); $pdo->exec('PRAGMA foreign_keys=ON');
$audit=new AuditLogger($pdo); $recovery=new RecoveryService($pdo,$audit,$storage,$db); $adapter=new VFPressUpdateAdapter($pdo,$config,$audit,$recovery);
$service=new OnlineUpdateService($pdo,$config,$audit,$adapter);
$result=$service->check();
if(($result['status']??null)!=='AVAILABLE') throw new RuntimeException('Expected AVAILABLE: '.json_encode($result,JSON_UNESCAPED_SLASHES));
if(($result['current_version']??null)!=='0.1.12') throw new RuntimeException('Wrong current version');
if((string)($result['current_schema']??'')!=='3') throw new RuntimeException('Wrong current schema');
$m=$result['manifest']??null;
if(!is_array($m)) throw new RuntimeException('Manifest missing');
$expected=[
 'target_version'=>'0.1.15','update_type'=>'ATOMIC','from_versions'=>['0.1.12','0.1.13','0.1.14'],
 'schema_from'=>'3','schema_to'=>'3','repository'=>'llhzx2018/vf-press','release_tag'=>'v0.1.15',
 'release_id'=>378572142,'product_identity'=>'a9300382d3a862fb599b8b928961ead38dee8f31',
 'asset_name'=>'VF_Press_V0.1.15_UPDATE.zip','asset_bytes'=>278578,
 'asset_sha256'=>'152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe',
 'backup_required'=>true,'rollback_supported'=>true,'minimum_php'=>'8.2.0'
];
foreach($expected as $k=>$v){ if(($m[$k]??null)!==$v) throw new RuntimeException('Manifest mismatch '.$k); }
$pure=(new UpdateCore('P06'))->check('0.1.12','3',$m);
if(($pure['status']??null)!=='AVAILABLE') throw new RuntimeException('UpdateCore did not accept V0.1.12: '.json_encode($pure));
echo "P06_V0112_REAL_ONLINE_UPDATE_SERVICE=PASS\n";
echo "P06_V0112_DISCOVERY_STATUS=AVAILABLE\n";
echo "P06_V0112_DISCOVERY_TARGET=0.1.15\n";
echo "P06_V0112_DISCOVERY_SCHEMA=3_TO_3\n";
echo "P06_V0112_DISCOVERY_GATE=PASS\n";
PHP
export P06_DISCOVERY_APP="$APP"
php "$ROOT/check.php"
