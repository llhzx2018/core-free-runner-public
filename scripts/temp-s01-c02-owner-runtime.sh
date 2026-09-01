#!/usr/bin/env bash
set -Eeuo pipefail

: "${WP_PATH:?}"
: "${WP_URL:?}"
: "${WP_VERSION:?}"
: "${WP_ADMIN_USER:?}"
: "${EVIDENCE_DIR:?}"
: "${OPS_SHA:?}"
: "${M3U8_SHA:?}"
: "${THEME_SHA:?}"

mkdir -p "$EVIDENCE_DIR"

test "$(git -C ops rev-parse HEAD)" = "$OPS_SHA"
test "$(git -C m3u8 rev-parse HEAD)" = "$M3U8_SHA"
test "$(git -C theme rev-parse HEAD)" = "$THEME_SHA"
test "$(tr -d '\r\n' < ops/VERSION)" = '1.21.791'
test "$(tr -d '\r\n' < m3u8/VERSION)" = '1.25.3'
test "$(tr -d '\r\n' < theme/VERSION)" = '1.35.8'
grep -Fq 'vf_ops_s01_tool_workbench_render_v1' ops/includes/s01/tool-workbench.php
grep -Fq "'route'=>'m3u8-download-record'" m3u8/src/includes/first-run.php

cat > "$EVIDENCE_DIR/source.env" <<EOF
OPS_SHA=$OPS_SHA
M3U8_SHA=$M3U8_SHA
THEME_SHA=$THEME_SHA
EXACT_THREE_COMPONENT_SOURCE=PASS
RELEASE_WRITE=NO
TAG_WRITE=NO
CORE_UPDATES_WRITE=NO
PRODUCTION_WRITE=NO
EOF

sudo apt-get update -y
sudo apt-get install -y php-cli php-mysql php-curl php-zip php-mbstring php-xml php-gd unzip curl jq mariadb-client rsync
php -r 'if(PHP_VERSION_ID<80200)exit(1);foreach(["mysqli","curl","zip","json","openssl"] as $e)if(!extension_loaded($e)){fwrite(STDERR,"MISSING:$e\n");exit(1);}'

curl -fsSL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar -o /tmp/wp
chmod +x /tmp/wp
sudo mv /tmp/wp /usr/local/bin/wp
mkdir -p "$WP_PATH"
for i in $(seq 1 30); do
  mariadb-admin ping -h127.0.0.1 -P3306 -uvf -pvf --silent && break
  sleep 1
done
mariadb-admin ping -h127.0.0.1 -P3306 -uvf -pvf --silent
wp core download --path="$WP_PATH" --version="$WP_VERSION" --force
wp config create --path="$WP_PATH" --dbname=vf_s01_owner --dbuser=vf --dbpass=vf --dbhost=127.0.0.1:3306 --skip-check
ADMIN_PASS="$(php -r 'echo bin2hex(random_bytes(24));')"
umask 077
printf '%s' "$ADMIN_PASS" > /tmp/vf-s01-owner-admin.pass
wp core install --path="$WP_PATH" --url="$WP_URL" --title='VF S01 Owner Runtime' --admin_user="$WP_ADMIN_USER" --admin_password="$ADMIN_PASS" --admin_email='owner@example.invalid' --skip-email
{ php -v | head -n1; wp core version --path="$WP_PATH"; mariadb --version; } > "$EVIDENCE_DIR/environment.txt"

mkdir -p "$WP_PATH/wp-content/plugins/vf-ops" "$WP_PATH/wp-content/plugins/vf-tool-m3u8" "$WP_PATH/wp-content/themes/vf-tools-theme"
rsync -a --delete --exclude='.git' ops/ "$WP_PATH/wp-content/plugins/vf-ops/"
rsync -a --delete m3u8/src/ "$WP_PATH/wp-content/plugins/vf-tool-m3u8/"
rsync -a --delete theme/src/ "$WP_PATH/wp-content/themes/vf-tools-theme/"
test -f "$WP_PATH/wp-content/plugins/vf-ops/vf-ops.php"
test -f "$WP_PATH/wp-content/plugins/vf-tool-m3u8/vf-tool-m3u8.php"
test -f "$WP_PATH/wp-content/themes/vf-tools-theme/style.css"
grep -Eq '^ \* Version: 1\.21\.791$' "$WP_PATH/wp-content/plugins/vf-ops/vf-ops.php"
grep -Eq '^ \* Version: 1\.25\.3$' "$WP_PATH/wp-content/plugins/vf-tool-m3u8/vf-tool-m3u8.php"
grep -Eq '^Version:[[:space:]]*1\.35\.8$' "$WP_PATH/wp-content/themes/vf-tools-theme/style.css"

wp plugin install simply-static --path="$WP_PATH" --activate
wp plugin activate vf-ops --path="$WP_PATH"
wp eval --path="$WP_PATH" 'if(!defined("VF_OPS_VERSION")||VF_OPS_VERSION!=="1.21.791")exit(2);echo "OPS_ONLY=PASS\n";' > "$EVIDENCE_DIR/ops-only.txt"
nohup wp server --path="$WP_PATH" --host=127.0.0.1 --port=8080 > "$EVIDENCE_DIR/wp-server.log" 2>&1 &
for i in $(seq 1 30); do
  curl -fsS "$WP_URL/wp-login.php" >/dev/null && break
  sleep 1
done
curl -fsS "$WP_URL/wp-login.php" >/dev/null

mkdir -p /tmp/vf-s01-owner-playwright
cd /tmp/vf-s01-owner-playwright
npm init -y >/dev/null 2>&1
npm install --no-save playwright@1.58.2 >/dev/null
npx playwright install --with-deps chromium >/dev/null

export WP_ADMIN_PASSWORD_FILE=/tmp/vf-s01-owner-admin.pass
node "$GITHUB_WORKSPACE/runner/scripts/temp-s01-c02-owner-browser.js"
jq -e '.result=="PASS" and .opsOnlyProviderMissing=="PASS" and .ownerRepairPostRedirectReadback=="PASS" and .sameProductObjectLinks=="PASS" and .publicShortcodeRuntime=="PASS" and .admin390Usability=="PASS"' "$EVIDENCE_DIR/owner-browser-gate.json" >/dev/null

wp eval --path="$WP_PATH" 'echo json_encode(["ops"=>defined("VF_OPS_VERSION")?VF_OPS_VERSION:"","m3u8"=>defined("VF_TOOL_M3U8_VERSION")?VF_TOOL_M3U8_VERSION:"","theme"=>wp_get_theme()->get("Version"),"readiness"=>function_exists("vf_m3u8_first_run_readiness")?vf_m3u8_first_run_readiness():[],"ownerState"=>function_exists("vf_ops_s01_m3u8_owner_state_v1")?vf_ops_s01_m3u8_owner_state_v1():[]],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);' > "$EVIDENCE_DIR/final-runtime-readback.json"
jq -e '.ops=="1.21.791" and .m3u8=="1.25.3" and .theme=="1.35.8" and .readiness.status=="PASS" and .ownerState.status=="PASS"' "$EVIDENCE_DIR/final-runtime-readback.json" >/dev/null

cat > "$EVIDENCE_DIR/S01_C02_OWNER_WORDPRESS_RUNTIME_GATE.txt" <<EOF
S01_C02_OWNER_WORDPRESS_RUNTIME_GATE=PASS
OPS_SHA=$OPS_SHA
M3U8_SHA=$M3U8_SHA
THEME_SHA=$THEME_SHA
WORDPRESS=$WP_VERSION
MARIADB=11.4
OPS_ONLY_PROVIDER_MISSING=PASS
THREE_COMPONENT_RUNTIME=PASS
OWNER_REPAIR_POST_REDIRECT_READBACK=PASS
SAME_PRODUCT_OBJECT_LINKS=PASS
PUBLIC_DOWNLOADER_SHORTCODE_RUNTIME=PASS
ADMIN_390_USABILITY=PASS
RELEASE_WRITE=NO
TAG_WRITE=NO
CORE_UPDATES_WRITE=NO
PRODUCTION_WRITE=NO
PRIVATE_SOURCE_PERSISTED=NO
OWNER_HUMAN_ACCEPTANCE=PENDING
EOF

rm -f /tmp/vf-s01-owner-admin.pass
