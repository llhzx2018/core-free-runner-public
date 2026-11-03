#!/usr/bin/env bash
set -Eeuo pipefail
WP=/tmp/s01-r8-upgrade-wp
CLI=/tmp/s01-r8-upgrade-wpcli.phar
PLUGIN="$WP/wp-content/plugins/vf-tools-m3u8"
OWNER_HEAD=7a1bca1deaf08148640812c9e465324442767d90
OLD_HEAD=fbe049dc18eb18eab21e9d8c3cededfe55b783e7
test "$(git -C candidate rev-parse HEAD)" = "$OWNER_HEAD"
test "$(git -C legacy rev-parse HEAD)" = "$OLD_HEAD"
curl -fsSLo "$CLI" https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
wp(){ php "$CLI" "$@" --path="$WP"; }
mkdir -p "$WP"
wp core download --skip-content --quiet
wp config create --dbname=wordpress --dbuser=wordpress --dbpass=synthetic-wp --dbhost=127.0.0.1:3306 --skip-check
wp core install --url=http://127.0.0.1:18884 --title=R8-Synthetic-Upgrade --admin_user=synthetic --admin_password=synthetic-only-password --admin_email=synthetic@example.invalid --skip-email
mkdir -p "$WP/wp-content/themes/vf-tools-theme" "$WP/wp-content/plugins/vf-tools-ops" "$PLUGIN"
cp -a theme/src/. "$WP/wp-content/themes/vf-tools-theme/"
cp -a ops/. "$WP/wp-content/plugins/vf-tools-ops/"
cp -a legacy/src/. "$PLUGIN/"
wp theme activate vf-tools-theme
# Prepare a real non-empty legacy migration input before plugin activation.
wp option update vf_tool_m3u8_settings '{"frontend_base_skin":"clean_utility"}' --format=json
wp plugin activate vf-tools-ops/vf-ops.php vf-tools-m3u8/vf-tool-m3u8.php
wp eval '
  update_option("s01_r8_owner_canary",["origin"=>"before-upgrade","keep"=>["list",17]],false);
  $pid=wp_insert_post(["post_type"=>"page","post_status"=>"publish","post_name"=>"s01-r8-owner-data","post_title"=>"Synthetic Owner Data","post_content"=>"Must survive candidate and rollback"]);
  if(!$pid||is_wp_error($pid))throw new Exception("OWNER_FIXTURE_INIT_FAILED");
  update_option("s01_r8_owner_post_id",$pid,false);
  echo "S01_R8_OLD_PLUGIN_FIXTURE=PASS\n";
'
check_owner(){
 wp eval '
  if(get_option("s01_r8_owner_canary")!==["origin"=>"before-upgrade","keep"=>["list",17]])throw new Exception("OWNER_OPTION_CHANGED");
  $post=get_post((int)get_option("s01_r8_owner_post_id"));
  if(!$post||$post->post_content!=="Must survive candidate and rollback")throw new Exception("OWNER_POST_CHANGED");
  global $wpdb;
  if(!$wpdb->get_var($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE ID=%d",$post->ID)))throw new Exception("OWNER_POST_DB_MISSING");
  echo "S01_R8_OWNER_DATA_READBACK=PASS\n";
 '
}
replace_with(){
 wp plugin deactivate vf-tools-m3u8/vf-tool-m3u8.php
 # Read MariaDB after the OLD runtime has deactivated, before any replacement
 # source can run; distinguishes legacy-side drift from new-code writes.
 skin_db inspect
 rm -rf "$PLUGIN"
 mkdir -p "$PLUGIN"
 cp -a "$1/src/." "$PLUGIN/"
 wp plugin activate vf-tools-m3u8/vf-tool-m3u8.php
}
php candidate/tests/skin-migration-snapshot-guard.php
skin_db(){ S01_R8_SKIN_PHASE="$1" wp eval-file control/lanes/s01-r8-upgrade-rollback-20261103/skin-db-parity.php; }
check_owner
skin_db baseline
# Create a complete MariaDB restore point BEFORE source handover in this
# disposable fixture. Code-only ZIP rollback never substitutes for DB restore.
if ! command -v mariadb-dump >/dev/null || ! command -v mariadb >/dev/null; then
 sudo apt-get update -qq
 sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq mariadb-client
fi
DB_DUMP=/tmp/s01-r8-full-wordpress-before-upgrade.sql
MYSQL_PWD=synthetic-wp mariadb-dump --host=127.0.0.1 --port=3306 --user=wordpress \
  --single-transaction --quick --skip-lock-tables wordpress > "$DB_DUMP"
test -s "$DB_DUMP"
DUMP_SHA="$(sha256sum "$DB_DUMP" | cut -d' ' -f1)"
test "${#DUMP_SHA}" = 64
echo S01_R8_FULL_MARIADB_PRE_UPGRADE_BACKUP=PASS
replace_with candidate
wp eval '
  $r=vf_tools_m3u8_runtime_bundle();$m=vf_tools_m3u8_provider_manifest();
  if(($r["version"]??null)!=="1.25.4"||($m["version"]??null)!=="1.25.4")throw new Exception("CANDIDATE_V6_NOT_LOADED");
  if(!hash_equals($r["content_hash"],vf_tools_m3u8_contract_hash($r)))throw new Exception("RUNTIME_HASH_BAD");
  if(!hash_equals($m["content_hash"],vf_tools_m3u8_contract_hash($m)))throw new Exception("MANIFEST_HASH_BAD");
  $check=vf_tools_m3u8_validate_runtime_bundle_contract($r,true);
  if(empty($check["ok"]))throw new Exception("CANDIDATE_ASSETS_BAD");
  echo "S01_R8_CANDIDATE_UPGRADE_V6_1_25_4=PASS\n";
'
check_owner
skin_db verify
echo S01_R8_SYNTHETIC_UPGRADE=PASS
replace_with legacy
check_owner
skin_db inspect
wp eval '
  $r=vf_tools_m3u8_runtime_bundle();
  if(($r["version"]??null)!=="1.25.0")throw new Exception("ROLLBACK_SOURCE_VERSION_BAD");
  echo "S01_R8_PLUGIN_CODE_ROLLBACK=PASS\\n";
'
skin_db inspect
echo S01_R8_LEGACY_CODE_ROLLBACK_DATA_PARITY=NOT_PROVEN
# Full SQL restoration is performed without WordPress executing. Before
# WordPress is loaded again, replace legacy PHP with the fixed candidate.
test "$(sha256sum "$DB_DUMP" | cut -d' ' -f1)" = "$DUMP_SHA"
MYSQL_PWD=synthetic-wp mariadb --host=127.0.0.1 --port=3306 \
  --user=wordpress wordpress < "$DB_DUMP"
rm -rf "$PLUGIN"
mkdir -p "$PLUGIN"
cp -a candidate/src/. "$PLUGIN/"
check_owner
skin_db verify
echo S01_R8_FULL_DATABASE_RESTORE_4_RAW_OPTIONS=PASS
wp eval '
  $r=vf_tools_m3u8_runtime_bundle();$m=vf_tools_m3u8_provider_manifest();
  if(($r["version"]??null)!=="1.25.4"||($m["version"]??null)!=="1.25.4")throw new Exception("REUPGRADE_VERSION_BAD");
  echo "S01_R8_CANDIDATE_REUPGRADE=PASS\n";
'
skin_db guard
echo S01_R8_SKIN_MIGRATION_MARIADB_LIFECYCLE=PASS
echo S01_R8_WP_MARIADB_OLD_CANDIDATE_ROLLBACK_REUPGRADE=PASS
