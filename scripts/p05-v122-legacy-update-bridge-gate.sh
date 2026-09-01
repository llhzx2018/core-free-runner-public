#!/usr/bin/env bash
set -Eeuo pipefail

FULL_ROOT="${1:?FULL root required}"
BRIDGE="${2:?bridge file required}"
: "${VF_PRIVATE_READ_TOKEN:?VF_PRIVATE_READ_TOKEN missing}"

TMP="$(mktemp -d)"
SITE="$TMP/htdocs/seo.kewaro.com"
PASSWORD='BridgeGatePass-2026!'
PORT=$((18880 + ($$ % 700)))
BASE="http://127.0.0.1:$PORT"
COOKIE="$TMP/cookies.txt"
SERVER_LOG="$TMP/server.log"
SERVER_PID=''
cleanup(){ if [[ -n "$SERVER_PID" ]]; then kill "$SERVER_PID" >/dev/null 2>&1 || true; fi; rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$SITE"
cp -a "$FULL_ROOT/." "$SITE/"
cp "$BRIDGE" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php"
test "$(cat "$SITE/VERSION")" = '1.2.2'

# The artifact may name the secret but must never contain its value.
! grep -Fq -- "$VF_PRIVATE_READ_TOKEN" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php"
php -l "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php" >/dev/null
php -r 'if(!extension_loaded("sodium")) exit(2); if(!extension_loaded("pdo_sqlite")) exit(3); if(!extension_loaded("curl")) exit(4); if(!class_exists("ZipArchive")) exit(5);'

# Create a real format-3 installed v1.2.2 site through the formal browser installer.
env APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php -S "127.0.0.1:$PORT" -t "$SITE" "$SITE/index.php" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 80); do
  if curl -fsS "$BASE/setup" -o /dev/null 2>/dev/null; then break; fi
  sleep 0.1
done
curl -fsS -c "$COOKIE" "$BASE/setup" -o "$TMP/setup.html"
CSRF="$(grep -o 'name="csrf_token" value="[^"]*"' "$TMP/setup.html" | head -1 | sed 's/.*value="\([^"]*\)"/\1/')"
test -n "$CSRF"
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" \
  --data-urlencode "csrf_token=$CSRF" --data-urlencode 'username=owner' \
  --data-urlencode "password=$PASSWORD" --data-urlencode "password_confirm=$PASSWORD" \
  "$BASE/setup" -o "$TMP/installed.html"
grep -q '安装完成' "$TMP/installed.html"
test -f "$SITE/VF_INSTALL_INSTANCE.json"
kill "$SERVER_PID" >/dev/null 2>&1 || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=''

INSTANCE_ID="$(php -r '$v=json_decode(file_get_contents($argv[1]),true,32,JSON_THROW_ON_ERROR); echo $v["siteInstanceId"]??"";' "$SITE/VF_INSTALL_INSTANCE.json")"
test -n "$INSTANCE_ID"
STORAGE_ROOT="$TMP/htdocs/.vfseo-data-$INSTANCE_ID"
ENV_FILE="$STORAGE_ROOT/config/runtime.env"
DB_FILE="$STORAGE_ROOT/data/vf-seo.sqlite3"
BACKUP_DIR="$STORAGE_ROOT/backups"
test -f "$ENV_FILE" -a -f "$DB_FILE"
test "$(stat -c '%a' "$ENV_FILE")" = '600'

# Test bridge as a library so no token ever crosses a browser/JS boundary.
cat > "$TMP/bridge-init.php" <<'PHP'
<?php
define('P05_LEGACY_BRIDGE_LIBRARY_MODE', true);
require $argv[1];
$b = new P05LegacyUpdateBridge($argv[2]);
$r = $b->initialize($argv[3]);
file_put_contents($argv[4], json_encode($r, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
PHP
APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php "$TMP/bridge-init.php" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php" "$SITE" "$PASSWORD" "$TMP/init.json"
php -r '$v=json_decode(file_get_contents($argv[1]),true,32,JSON_THROW_ON_ERROR); if(($v["status"]??"")!=="WAITING_RELAY"||empty($v["publicKey"])||empty($v["nonce"])||empty($v["backupId"])) exit(1);' "$TMP/init.json"
PUBLIC_KEY="$(php -r '$v=json_decode(file_get_contents($argv[1]),true,32,JSON_THROW_ON_ERROR); echo $v["publicKey"];' "$TMP/init.json")"
NONCE="$(php -r '$v=json_decode(file_get_contents($argv[1]),true,32,JSON_THROW_ON_ERROR); echo $v["nonce"];' "$TMP/init.json")"
test -n "$PUBLIC_KEY" -a -n "$NONCE"
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'vf-seo-*.sqlite3' -print -quit | grep -q .

# Seal the registered shared token to the runtime-generated public key.
SEALED="$(php -r '$pk=base64_decode($argv[1],true);$t=getenv("VF_PRIVATE_READ_TOKEN");if(!is_string($pk)||$pk===""||!is_string($t)||$t==="")exit(2);echo base64_encode(sodium_crypto_box_seal($t,$pk));' "$PUBLIC_KEY")"
test -n "$SEALED"

cat > "$TMP/bridge-deliver.php" <<'PHP'
<?php
define('P05_LEGACY_BRIDGE_LIBRARY_MODE', true);
require $argv[1];
$b = new P05LegacyUpdateBridge($argv[2]);
$r = $b->deliver($argv[3], $argv[4]);
file_put_contents($argv[5], json_encode($r, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
PHP
# Deliberately remove the process token: the bridge must succeed from sealed relay only.
env -u VF_PRIVATE_READ_TOKEN APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php "$TMP/bridge-deliver.php" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php" "$SITE" "$NONCE" "$SEALED" "$TMP/ready.json"
php -r '$v=json_decode(file_get_contents($argv[1]),true,32,JSON_THROW_ON_ERROR); if(($v["status"]??"")!=="READY"||($v["targetVersion"]??"")!=="1.2.3") exit(1);' "$TMP/ready.json"

grep -Fqx "VF_PRIVATE_READ_TOKEN=$VF_PRIVATE_READ_TOKEN" "$ENV_FILE"
test "$(stat -c '%a' "$ENV_FILE")" = '600'

# A fresh process with no injected token must discover v1.2.3 from pointer-bound runtime.env.
cat > "$TMP/status.php" <<'PHP'
<?php
require_once $argv[1].'/php/src/RuntimePaths.php';
require_once $argv[1].'/php/src/Config.php';
require_once $argv[1].'/php/src/Database.php';
require_once $argv[1].'/php/src/Security.php';
require_once $argv[1].'/php/src/Backup.php';
require_once $argv[1].'/php/src/SiteInstance.php';
require_once $argv[1].'/php/src/CoreUpdates/UpdateCore.php';
require_once $argv[1].'/php/src/CoreUpdates/GitHubClient.php';
require_once $argv[1].'/php/src/PhpUpdater.php';
$c=VfSeo\PhpRuntime\Config::load($argv[1]);$d=new VfSeo\PhpRuntime\Database($c->sqlitePath,$c->sqliteBusyTimeoutMs);$u=new VfSeo\PhpRuntime\PhpUpdater($c,new VfSeo\PhpRuntime\Backup($d,$c));
$s=$u->status();
if(($s['channel']??'')!=='AVAILABLE'||($s['updaterReady']??false)!==true||(($s['manifest']['targetVersion']??'')!=='1.2.3')) exit(1);
echo "P05_BRIDGE_DISCOVERY_READY=PASS\n";
PHP
env -u VF_PRIVATE_READ_TOKEN APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php "$TMP/status.php" "$SITE" > "$TMP/status.log"
grep -q 'P05_BRIDGE_DISCOVERY_READY=PASS' "$TMP/status.log"

# Source remains byte-identical. Tampering must fail closed.
cat > "$TMP/source-check.php" <<'PHP'
<?php
define('P05_LEGACY_BRIDGE_LIBRARY_MODE', true); require $argv[1]; $b=new P05LegacyUpdateBridge($argv[2]); $b->sourceCheck(); echo "SOURCE_OK\n";
PHP
env -u VF_PRIVATE_READ_TOKEN APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php "$TMP/source-check.php" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php" "$SITE" | grep -q SOURCE_OK
cp "$SITE/php/src/PhpUpdater.php" "$TMP/PhpUpdater.php"
printf '\n// tamper\n' >> "$SITE/php/src/PhpUpdater.php"
set +e
env -u VF_PRIVATE_READ_TOKEN APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php "$TMP/source-check.php" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php" "$SITE" >"$TMP/tamper.log" 2>&1
TAMPER_RC=$?
set -e
test "$TAMPER_RC" -ne 0
cp "$TMP/PhpUpdater.php" "$SITE/php/src/PhpUpdater.php"

cat > "$TMP/cleanup.php" <<'PHP'
<?php
define('P05_LEGACY_BRIDGE_LIBRARY_MODE', true); require $argv[1]; $b=new P05LegacyUpdateBridge($argv[2]); $r=$b->cleanup($argv[3],false); if(($r['status']??'')!=='CLEANED') exit(1);
PHP
env -u VF_PRIVATE_READ_TOKEN APP_ENV=test VF_DATABASE_PROVIDER=sqlite VF_SECURE_COOKIES=false VF_REQUIRE_HTTPS=false \
  php "$TMP/cleanup.php" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php" "$SITE" "$NONCE"

test "$(cat "$SITE/VERSION")" = '1.2.2'
php -r '$pdo=new PDO("sqlite:".$argv[1]);$v=$pdo->query("SELECT schema_version FROM schema_metadata WHERE singleton=1")->fetchColumn();if((int)$v!==1)exit(1);' "$DB_FILE"
! grep -Fq -- "$VF_PRIVATE_READ_TOKEN" "$SITE/P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php"

echo 'P05_BRIDGE_EXACT_V122_SOURCE=PASS'
echo 'P05_BRIDGE_ADMIN_AUTH=PASS'
echo 'P05_BRIDGE_RECOVERY_POINT=PASS'
echo 'P05_BRIDGE_SODIUM_SEALED_RELAY=PASS'
echo 'P05_BRIDGE_BROWSER_SECRET=0'
echo 'P05_BRIDGE_RUNTIME_ENV_0600=PASS'
echo 'P05_BRIDGE_LIVE_PRIVATE_DISCOVERY=PASS'
echo 'P05_BRIDGE_TAMPER_FAIL_CLOSED=PASS'
echo 'P05_BRIDGE_VERSION_UNCHANGED=1.2.2'
echo 'P05_BRIDGE_SCHEMA_UNCHANGED=1'
echo 'P05_BRIDGE_FORMAL_UPGRADE_EXECUTED=0'
echo 'P05_BRIDGE_PRODUCTION_WRITE=0'
