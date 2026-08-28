#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_DIR="${1:-source}"
TARGET_DIR="${2:-target}"
TARGET_SOURCE="a9300382d3a862fb599b8b928961ead38dee8f31"
SOURCE_SOURCE="d689b79a6f1d98f0bf5bccba438f3c9a74077782"
ROOT="$RUNNER_TEMP/p06-v0115-release-atomic"
DIST1="$ROOT/dist1"
DIST2="$ROOT/dist2"
APP="$ROOT/app"
STORAGE="$ROOT/storage"
DB="$STORAGE/app.db"

rm -rf "$ROOT"
mkdir -p "$DIST1" "$DIST2" "$APP" "$STORAGE"

test "$(git -C "$SOURCE_DIR" rev-parse HEAD)" = "$SOURCE_SOURCE"
test "$(git -C "$TARGET_DIR" rev-parse HEAD)" = "$TARGET_SOURCE"
test "$(tr -d '\r\n' < "$SOURCE_DIR/VERSION")" = '0.1.14'
test "$(tr -d '\r\n' < "$TARGET_DIR/VERSION")" = '0.1.15'

# This release changes UI/authority only; the actual updater implementation must be the same one already deployed in 0.1.14.
for f in \
  src/Infrastructure/Update/CoreUpdates/UpdateCore.php \
  src/Infrastructure/Update/CoreUpdates/UpdateAdapter.php \
  src/Infrastructure/Update/VFPressUpdateAdapter.php \
  src/Infrastructure/Recovery/RecoveryService.php; do
  cmp "$SOURCE_DIR/$f" "$TARGET_DIR/$f"
done
echo P06_V0115_UPDATER_SOURCE_IDENTITY=PASS

(cd "$SOURCE_DIR" && composer install --no-interaction --prefer-dist --no-progress)
(cd "$TARGET_DIR" && composer install --no-interaction --prefer-dist --no-progress)

# Build the exact target release twice and prove deterministic FULL/UPDATE bytes.
(cd "$TARGET_DIR" && php bin/build-release.php "$DIST1")
(cd "$TARGET_DIR" && php bin/build-release.php "$DIST2")
for f in VF_Press_V0.1.15_FULL.zip VF_Press_V0.1.15_UPDATE.zip SHA256SUMS.txt; do
  cmp "$DIST1/$f" "$DIST2/$f"
done
UPDATE="$DIST1/VF_Press_V0.1.15_UPDATE.zip"
FULL="$DIST1/VF_Press_V0.1.15_FULL.zip"
UPDATE_BYTES="$(stat -c %s "$UPDATE")"
UPDATE_SHA="$(sha256sum "$UPDATE" | awk '{print $1}')"
FULL_BYTES="$(stat -c %s "$FULL")"
FULL_SHA="$(sha256sum "$FULL" | awk '{print $1}')"

echo "P06_V0115_FULL_BYTES=$FULL_BYTES"
echo "P06_V0115_FULL_SHA256=$FULL_SHA"
echo "P06_V0115_UPDATE_BYTES=$UPDATE_BYTES"
echo "P06_V0115_UPDATE_SHA256=$UPDATE_SHA"
echo P06_V0115_DETERMINISTIC_RELEASE=PASS

python3 - "$UPDATE" <<'PY'
import json,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    names=set(z.namelist())
    assert 'VF_UPDATE.json' in names
    c=json.loads(z.read('VF_UPDATE.json'))
    assert c['schema']=='vf-press-update/v1'
    assert c['project_id']=='P06'
    assert c['target_version']=='0.1.15'
    assert c['delete']==[]
    assert any(x['path']=='VERSION' for x in c['files'])
    assert any(x['path']=='src/Http/Studio/SystemBaselineController.php' for x in c['files'])
print('P06_V0115_UPDATE_CONTRACT=PASS')
PY

# Create a real installed V0.1.14 runtime, separate from either checkout.
rsync -a --exclude='.git' "$SOURCE_DIR/" "$APP/"
export APP_ENV=test
export VF_PRESS_STORAGE_PATH="$STORAGE"
export VF_PRESS_DB_PATH="$DB"
export VF_PRESS_OWNER_USERNAME=atomic-owner
export VF_PRESS_OWNER_PASSWORD='P06-Atomic-Owner-Password-2026!'
export VF_PRESS_OWNER_DISPLAY_NAME='Atomic Owner'
(cd "$APP" && php bin/migrate.php)
test "$(sqlite3 "$DB" 'SELECT MAX(version) FROM schema_migrations;')" = '3'
(cd "$APP" && php bin/create-owner.php)
sqlite3 "$DB" "CREATE TABLE vf_atomic_sentinel(k TEXT PRIMARY KEY,v TEXT NOT NULL); INSERT INTO vf_atomic_sentinel VALUES('owner-data','PRESERVE-0.1.14-TO-0.1.15');"
test "$(sqlite3 "$DB" "SELECT v FROM vf_atomic_sentinel WHERE k='owner-data';")" = 'PRESERVE-0.1.14-TO-0.1.15'
test "$(tr -d '\r\n' < "$APP/VERSION")" = '0.1.14'
echo P06_V0115_SOURCE_RUNTIME=PASS

export P06_ATOMIC_APP="$APP"
export P06_ATOMIC_STORAGE="$STORAGE"
export P06_ATOMIC_DB="$DB"
export P06_ATOMIC_ZIP="$UPDATE"
export P06_ATOMIC_SHA="$UPDATE_SHA"
export P06_ATOMIC_BYTES="$UPDATE_BYTES"
cat > "$ROOT/atomic.php" <<'PHP'
<?php
declare(strict_types=1);
use CoreUpdates\UpdateCore;
use VF\Press\Infrastructure\Config\AppConfig;
use VF\Press\Infrastructure\Recovery\RecoveryService;
use VF\Press\Infrastructure\Security\AuditLogger;
use VF\Press\Infrastructure\Update\VFPressUpdateAdapter;
$app=getenv('P06_ATOMIC_APP'); $storage=getenv('P06_ATOMIC_STORAGE'); $db=getenv('P06_ATOMIC_DB'); $zip=getenv('P06_ATOMIC_ZIP');
if (!$app||!$storage||!$db||!$zip) throw new RuntimeException('Atomic gate env missing');
require $app.'/vendor/autoload.php';
$config=new AppConfig($app,$storage,$db,'test'); $config->ensureRuntimeDirectories();
$pdo=new PDO('sqlite:'.$db); $pdo->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION); $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE,PDO::FETCH_ASSOC); $pdo->exec('PRAGMA foreign_keys=ON');
$audit=new AuditLogger($pdo); $recovery=new RecoveryService($pdo,$audit,$storage,$db); $adapter=new VFPressUpdateAdapter($pdo,$config,$audit,$recovery); $core=new UpdateCore('P06');
$manifest=[
 'schema_version'=>'1.0','project_id'=>'P06','component_id'=>'APP','enabled'=>true,
 'target_version'=>'0.1.15','update_type'=>'ATOMIC','from_versions'=>['0.1.14'],
 'schema_from'=>'3','schema_to'=>'3','repository'=>'llhzx2018/vf-press','release_tag'=>'v0.1.15',
 'asset_name'=>'VF_Press_V0.1.15_UPDATE.zip','asset_bytes'=>(int)getenv('P06_ATOMIC_BYTES'),'asset_sha256'=>getenv('P06_ATOMIC_SHA'),
 'backup_required'=>true,'rollback_supported'=>true,'minimum_php'=>'8.2.0','released_at'=>'2026-08-28T00:00:00Z'
];
$result=$core->upgrade('0.1.14','3',$adapter,$zip,$manifest);
if (!in_array($result['status']??'', ['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'], true)) throw new RuntimeException('Atomic update failed: '.json_encode($result));
echo 'P06_V0115_ATOMIC_STATUS='.($result['status']??'UNKNOWN')."\n";
PHP
php "$ROOT/atomic.php"

# Exact post-update truth and user-data preservation.
test "$(tr -d '\r\n' < "$APP/VERSION")" = '0.1.15'
test "$(sqlite3 "$DB" 'SELECT MAX(version) FROM schema_migrations;')" = '3'
test "$(sqlite3 "$DB" 'PRAGMA integrity_check;')" = 'ok'
test "$(sqlite3 "$DB" "SELECT v FROM vf_atomic_sentinel WHERE k='owner-data';")" = 'PRESERVE-0.1.14-TO-0.1.15'
test -d "$STORAGE/backups"
test -d "$STORAGE/update-source-backups"
test -n "$(find "$STORAGE/update-source-backups" -type f -path '*/source/VERSION' -print -quit)"
test "$(tr -d '\r\n' < "$(find "$STORAGE/update-source-backups" -type f -path '*/source/VERSION' -print -quit)")" = '0.1.14'
echo P06_V0115_RECOVERY_AND_SENTINEL=PASS

# New runtime self-tests after the actual Atomic replacement.
(cd "$APP" && php bin/preflight.php)
(cd "$APP" && php bin/common-baseline-v2-self-test.php)
(cd "$APP" && php bin/common-baseline-human-ui-self-test.php)
(cd "$APP" && composer update-self-test)
echo P06_V0115_POST_UPDATE_REGRESSION=PASS

# Real post-upgrade HTTP health from the upgraded runtime.
PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
mkdir -p "$ROOT/sessions"
(cd "$APP" && php -d session.save_path="$ROOT/sessions" -S 127.0.0.1:$PORT -t public public/index.php >"$ROOT/server.log" 2>&1) &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
READY=0
for _ in $(seq 1 100); do if curl -fsS "http://127.0.0.1:$PORT/health" >"$ROOT/health.json" 2>/dev/null; then READY=1; break; fi; sleep .1; done
test "$READY" = 1
python3 - "$ROOT/health.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); assert x['status']=='ok' and x['version']=='0.1.15' and x['schema']==3 and x['sqlite_integrity']=='ok',x
print('P06_V0115_POST_UPDATE_HTTP=PASS')
PY
kill "$PID"; wait "$PID" || true; trap - EXIT
! grep -Eqi 'Fatal error|Parse error|Uncaught|EADDRINUSE' "$ROOT/server.log"

# Copy only the verified formal release set to artifact staging.
mkdir -p "$ROOT/formal"
cp "$DIST1/VF_Press_V0.1.15_FULL.zip" "$ROOT/formal/"
cp "$DIST1/VF_Press_V0.1.15_UPDATE.zip" "$ROOT/formal/"
cp "$DIST1/SHA256SUMS.txt" "$ROOT/formal/"
cp "$DIST1/RELEASE_INFO.json" "$ROOT/formal/"
printf '%s\n' "$TARGET_SOURCE" > "$ROOT/formal/RELEASE_SOURCE.txt"
printf '%s\n' "$UPDATE_BYTES" > "$ROOT/formal/UPDATE_BYTES.txt"
printf '%s\n' "$UPDATE_SHA" > "$ROOT/formal/UPDATE_SHA256.txt"
printf '%s\n' "$FULL_BYTES" > "$ROOT/formal/FULL_BYTES.txt"
printf '%s\n' "$FULL_SHA" > "$ROOT/formal/FULL_SHA256.txt"

echo P06_V0115_RELEASE_SOURCE="$TARGET_SOURCE"
echo P06_V0115_SCHEMA=3
echo P06_V0115_ATOMIC_FROM=0.1.14
echo P06_V0115_MACHINE=PASS
