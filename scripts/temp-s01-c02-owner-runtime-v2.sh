#!/usr/bin/env bash
set -Eeuo pipefail

: "${WP_PATH:?}"
: "${WP_URL:?}"
: "${WP_VERSION:?}"
: "${WP_ADMIN_USER:?}"
: "${EVIDENCE_DIR:?}"
: "${OPS_SHA:?}"
: "${M3U8_SHA:?}"
: "${M3U8_LEGACY_SHA:?}"
: "${THEME_SHA:?}"

mkdir -p "$EVIDENCE_DIR"

test "$(git -C ops rev-parse HEAD)" = "$OPS_SHA"
test "$(git -C m3u8 rev-parse HEAD)" = "$M3U8_SHA"
test "$(git -C m3u8-legacy rev-parse HEAD)" = "$M3U8_LEGACY_SHA"
test "$(git -C theme rev-parse HEAD)" = "$THEME_SHA"
test "$(tr -d '\r\n' < ops/VERSION)" = '1.21.791'
test "$(tr -d '\r\n' < m3u8/VERSION)" = '1.25.3'
test "$(tr -d '\r\n' < m3u8-legacy/VERSION)" = '1.25.3'
test "$(tr -d '\r\n' < theme/VERSION)" = '1.35.8'
grep -Fq 'vf_ops_s01_tool_workbench_render_v1' ops/includes/s01/tool-workbench.php
grep -Fq "'route'=>'m3u8-download-record'" m3u8/src/includes/first-run.php
grep -Fq "return '1.3.0'" m3u8/src/includes/v6-provider-schema.php
grep -Fq "vf_m3u8_capabilities" m3u8/src/includes/v6-provider-schema.php
grep -Fq "legacySchemaCompatible" m3u8/src/includes/v6-provider-schema.php

cat > "$EVIDENCE_DIR/source.env" <<EOF
OPS_SHA=$OPS_SHA
M3U8_SHA=$M3U8_SHA
M3U8_LEGACY_SHA=$M3U8_LEGACY_SHA
THEME_SHA=$THEME_SHA
EXACT_CHECKOUT_SOURCE=PASS
M3U8_RUNTIME_MODE=C03_PRIVATE_SCHEMA_RECOVERY_SOURCE
M3U8_EPHEMERAL_PATCH=NO
M3U8_GIT_WRITE=RECOVERY_BRANCH_ONLY
RELEASE_WRITE=NO
TAG_WRITE=NO
CORE_UPDATES_WRITE=NO
PRODUCTION_WRITE=NO
EOF

sudo apt-get update -y
sudo apt-get install -y php-cli php-mysql php-curl php-zip php-mbstring php-xml php-gd unzip curl jq mariadb-client rsync
php -r 'if(PHP_VERSION_ID<80200)exit(1);foreach(["mysqli","curl","zip","json","openssl"] as $e)if(!extension_loaded($e)){fwrite(STDERR,"MISSING:$e\n");exit(1);}'
find m3u8/src -type f -name '*.php' -print0 | sort -z | xargs -0 -n1 php -l > "$EVIDENCE_DIR/m3u8-recovery-php-lint.txt"

curl -fsSL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar -o /tmp/wp
chmod +x /tmp/wp
sudo mv /tmp/wp /usr/local/bin/wp

# First prove real legacy shared-schema state migrates losslessly and
# idempotently before exercising the three-component fresh co-install path.
bash "$GITHUB_WORKSPACE/runner/scripts/temp-s01-c03-private-schema-migration.sh"

mkdir -p "$WP_PATH"
for i in $(seq 1 30); do
  mariadb-admin ping -h127.0.0.1 -P3306 -uvf -pvf --silent && break
  sleep 1
done
mariadb-admin ping -h127.0.0.1 -P3306 -uvf -pvf --silent
wp core download --path="$WP_PATH" --version="$WP_VERSION" --force
wp config create --path="$WP_PATH" --dbname=vf_s01_owner --dbuser=vf --dbpass=vf --dbhost=127.0.0.1:3306 --skip-check
wp config set WP_DEBUG true --raw --path="$WP_PATH"
wp config set WP_DEBUG_LOG true --raw --path="$WP_PATH"
wp config set WP_DEBUG_DISPLAY false --raw --path="$WP_PATH"
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
grep -Fq "vf_m3u8_capabilities" "$WP_PATH/wp-content/plugins/vf-tool-m3u8/includes/v6-provider-schema.php"

wp plugin install simply-static --path="$WP_PATH" --activate
wp plugin activate vf-ops --path="$WP_PATH" > "$EVIDENCE_DIR/ops-activation.log" 2>&1
wp eval --path="$WP_PATH" 'if(!defined("VF_OPS_VERSION")||VF_OPS_VERSION!=="1.21.791")exit(2);echo "OPS_ONLY=PASS\n";' > "$EVIDENCE_DIR/ops-only.txt"

# Prove the unnamespaced platform tables exist before M3U8 activation. These
# are Ops/platform tables and must not be mistaken for historical C03 schema.
mariadb -h127.0.0.1 -P3306 -uvf -pvf vf_s01_owner -N -e "SHOW TABLES LIKE 'wp_vf_%';" | sort > "$EVIDENCE_DIR/ops-platform-tables-before-m3u8.txt"
for table in wp_vf_capabilities wp_vf_capability_contracts wp_vf_pipelines wp_vf_pipeline_revisions wp_vf_pipeline_steps wp_vf_pipeline_edges wp_vf_runtime_bundles wp_vf_runtime_bundle_assets; do
  grep -Fxq "$table" "$EVIDENCE_DIR/ops-platform-tables-before-m3u8.txt"
done
mariadb -h127.0.0.1 -P3306 -uvf -pvf vf_s01_owner -N -e "SHOW COLUMNS FROM wp_vf_capabilities; SHOW COLUMNS FROM wp_vf_pipelines;" > "$EVIDENCE_DIR/ops-overlap-schema-before-m3u8.txt"

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
NODE_PATH=/tmp/vf-s01-owner-playwright/node_modules node "$GITHUB_WORKSPACE/runner/scripts/temp-s01-c02-owner-browser-v2.js"
jq -e '.result=="PASS" and .opsOnlyProviderMissing=="PASS" and .m3u8ActivationSchemaCollision=="ABSENT_WITH_C03_PRIVATE_SCHEMA" and .schemaVersion=="1.3.0" and .migrationSourceMode=="INCOMPATIBLE_SHARED_PLATFORM_TABLES_IGNORED" and .ownerRepairPostRedirectReadback=="PASS" and .sameProductObjectLinks=="PASS" and .publicShortcodeRuntime=="PASS" and .admin390Usability=="PASS"' "$EVIDENCE_DIR/owner-browser-gate.json" >/dev/null

# Verify all Provider tables coexist with the existing Ops/platform tables.
mariadb -h127.0.0.1 -P3306 -uvf -pvf vf_s01_owner -N -e "SHOW TABLES LIKE 'wp_vf_%';" | sort > "$EVIDENCE_DIR/all-vf-tables-after-m3u8.txt"
for table in wp_vf_m3u8_capabilities wp_vf_m3u8_capability_contracts wp_vf_m3u8_pipelines wp_vf_m3u8_pipeline_revisions wp_vf_m3u8_pipeline_steps wp_vf_m3u8_pipeline_edges wp_vf_m3u8_provider_fixtures wp_vf_m3u8_provider_fixture_revisions wp_vf_m3u8_provider_fixture_runs wp_vf_m3u8_runtime_bundles wp_vf_m3u8_runtime_bundle_assets wp_vf_m3u8_provider_operation_runs wp_vf_m3u8_provider_snapshots wp_vf_m3u8_provider_snapshot_items; do
  grep -Fxq "$table" "$EVIDENCE_DIR/all-vf-tables-after-m3u8.txt"
done
mariadb -h127.0.0.1 -P3306 -uvf -pvf vf_s01_owner -N -e "SHOW COLUMNS FROM wp_vf_capabilities; SHOW COLUMNS FROM wp_vf_pipelines;" > "$EVIDENCE_DIR/ops-overlap-schema-after-m3u8.txt"
cmp "$EVIDENCE_DIR/ops-overlap-schema-before-m3u8.txt" "$EVIDENCE_DIR/ops-overlap-schema-after-m3u8.txt"

# WP-CLI has no S01 page/action request context, so explicitly load the lightweight
# workbench before final owner-state readback. This does not alter product runtime.
wp eval --path="$WP_PATH" 'require_once VF_OPS_SERVICE_DIR . "s01/tool-workbench.php"; echo json_encode(["ops"=>defined("VF_OPS_VERSION")?VF_OPS_VERSION:"","m3u8"=>defined("VF_TOOL_M3U8_VERSION")?VF_TOOL_M3U8_VERSION:"","theme"=>wp_get_theme()->get("Version"),"schema"=>function_exists("vf_tools_m3u8_v6_schema_version")?vf_tools_m3u8_v6_schema_version():"","migration"=>function_exists("vf_tools_m3u8_v6_private_schema_migration_option")?get_option(vf_tools_m3u8_v6_private_schema_migration_option(),[]):[],"readiness"=>function_exists("vf_m3u8_first_run_readiness")?vf_m3u8_first_run_readiness():[],"ownerState"=>function_exists("vf_ops_s01_m3u8_owner_state_v1")?vf_ops_s01_m3u8_owner_state_v1():[]],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);' > "$EVIDENCE_DIR/final-runtime-readback.json"
jq -e '.ops=="1.21.791" and .m3u8=="1.25.3" and .theme=="1.35.8" and .schema=="1.3.0" and .migration.status=="PASS" and .migration.sourceMode=="INCOMPATIBLE_SHARED_PLATFORM_TABLES_IGNORED" and .readiness.status=="PASS" and .ownerState.status=="PASS"' "$EVIDENCE_DIR/final-runtime-readback.json" >/dev/null

if [ -f "$WP_PATH/wp-content/debug.log" ]; then
  cp "$WP_PATH/wp-content/debug.log" "$EVIDENCE_DIR/wordpress-debug.log"
fi

cat > "$EVIDENCE_DIR/S01_C02_OWNER_WORDPRESS_RUNTIME_DIAGNOSTIC_V2.txt" <<EOF
S01_C02_OWNER_WORDPRESS_RUNTIME_DIAGNOSTIC_V2=PASS
OPS_SHA=$OPS_SHA
M3U8_SHA=$M3U8_SHA
M3U8_LEGACY_SHA=$M3U8_LEGACY_SHA
THEME_SHA=$THEME_SHA
WORDPRESS=$WP_VERSION
MARIADB=11.4
M3U8_EPHEMERAL_NAMESPACE_PATCH=NO
M3U8_PRIVATE_SCHEMA_SOURCE=YES
M3U8_SCHEMA=1.3.0
LEGACY_SCHEMA_MIGRATION=PASS
LEGACY_SHARED_TABLES_MUTATED=0
FOREIGN_PROVIDER_ROWS_MIGRATED=0
MIGRATION_IDEMPOTENCE=PASS
OPS_PLATFORM_SCHEMA_PRESERVED=PASS
OPS_ONLY_PROVIDER_MISSING=PASS
M3U8_SCHEMA_COLLISION=ABSENT
OWNER_REPAIR_POST_REDIRECT_READBACK=PASS
SAME_PRODUCT_OBJECT_LINKS=PASS
PUBLIC_DOWNLOADER_SHORTCODE_RUNTIME=PASS
ADMIN_390_USABILITY=PASS
RELEASE_WRITE=NO
TAG_WRITE=NO
CORE_UPDATES_WRITE=NO
PRODUCTION_WRITE=NO
PRIVATE_SOURCE_PERSISTED=NO
FORMAL_RUNTIME_GATE=NO_DIAGNOSTIC_ONLY
OWNER_HUMAN_ACCEPTANCE=PENDING
EOF

rm -f /tmp/vf-s01-owner-admin.pass
