#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-compatibility-${GITHUB_RUN_ID}";DB="$NET-db";export WP="$NET-wp"
cleanup(){ docker rm -f "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -e CANDIDATE_VERSION="$TARGET_VERSION" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \\*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e SOURCE_VERSION="$SOURCE_VERSION" -e TARGET_VERSION="$TARGET_VERSION" -e CANDIDATE_VERSION="$TARGET_VERSION" -e VF_PHASE="${VF_PHASE:-}" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic M3U8 Overview' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/context.php "$WP:/var/www/html/wp-content/mu-plugins/synthetic-overview-context.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/mu-plugins
docker cp "provider/vf-tools-ops_V${OPS_VERSION}.zip" "$WP:/tmp/ops.zip"
cli plugin install /tmp/ops.zip --activate >/dev/null
test "$(cli plugin get vf-ops --field=version)" = "$OPS_VERSION"
docker cp provider/vf-tools-m3u8_V${SOURCE_VERSION}.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$SOURCE_VERSION"
cli user create restricted restricted@example.invalid --role=subscriber --user_pass='Synthetic-Only-Update-54!' >/dev/null
VF_PHASE=baseline node lane/quick.js
docker cp target/tests/unit/provider-capability-wordpress-fixture.php "$WP:/tmp/capability-fixture.php"
docker cp target/tests/unit/provider-pipeline-wordpress-fixture.php "$WP:/tmp/pipeline-fixture.php"
docker cp target/tests/unit/provider-fixture-wordpress-fixture.php "$WP:/tmp/fixture-fixture.php"
unzip -p "provider/vf-tools-m3u8_V${SOURCE_VERSION}.zip" vf-tool-m3u8/admin/ui-v4/pages/v6-playground.js > /tmp/playground-baseline.js
node target/tests/unit/provider-playground-session-contract.js /tmp/playground-baseline.js --baseline > proof/playground-baseline-session.json
VF_PLAYGROUND_BASELINE=1 node target/tests/unit/provider-playground-wordpress-browser.js
docker cp "proof/vf-tools-m3u8_V${TARGET_VERSION}.zip" "$WP:/tmp/candidate.zip"
docker cp proof/synthetic-channel.json "$WP:/tmp/synthetic-channel.json"
docker cp lane/mock-update.php "$WP:/var/www/html/wp-content/mu-plugins/synthetic-update-transport.php"
docker cp lane/phase.php "$WP:/tmp/widget-native-phase.php"
docker cp target/tests/unit/provider-overview-wordpress-fixture.php "$WP:/tmp/overview-fixture.php"
docker cp target/tests/unit/provider-compatibility-wordpress-fixture.php "$WP:/tmp/health-fixture.php"
VF_PHASE=seed cli eval-file /tmp/widget-native-phase.php > proof/native-baseline.json
VF_PHASE=negative cli eval-file /tmp/widget-native-phase.php > proof/native-corrupt-negative.json
VF_PHASE=upgrade cli eval-file /tmp/widget-native-phase.php > proof/native-upgrade.json
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$TARGET_VERSION"
VF_PHASE=candidate cli eval-file /tmp/widget-native-phase.php > proof/native-candidate.json
if test "${VF_REAPPLY_DEBUG:-0}" = 1;then
 VF_PHASE=restore cli eval-file /tmp/widget-native-phase.php > proof/debug-recovery.json
 VF_PHASE=rollback cli eval-file /tmp/widget-native-phase.php > proof/debug-rollback.json
 VF_PHASE=rollback node lane/quick.js
 VF_PHASE=reapply cli eval-file /tmp/widget-native-phase.php > proof/debug-reapply.json
 VF_PHASE=reapply-readback cli eval-file /tmp/widget-native-phase.php > proof/debug-after.json || true
 docker cp "$WP:/tmp/candidate-options.json" proof/debug-original-option-hashes.json
 docker cp "$WP:/tmp/reapply-before.json" proof/debug-before.json
 docker cp "$WP:/tmp/reapply-after.json" proof/debug-current.json
 exit 0
fi
docker cp target/tests/unit/provider-runtime-wordpress-fixture.php "$WP:/tmp/runtime-fixture.php"
node target/tests/unit/provider-playground-wordpress-browser.js
node target/tests/unit/provider-fixture-wordpress-browser.js
node target/tests/unit/provider-capability-wordpress-browser.js
node target/tests/unit/provider-pipeline-wordpress-browser.js
node target/tests/unit/provider-runtime-wordpress-browser.js
node target/tests/unit/provider-overview-wordpress-browser.js
node target/tests/unit/provider-diagnostics-wordpress-browser.js
git -C target show "99c507e72bec9e96b7db6e753ec1b51f73d01985:src/includes/v6-provider-post-migration-readonly.php" > /tmp/prior-readonly.php
docker cp /tmp/prior-readonly.php "$WP:/tmp/prior-readonly.php"
docker cp target/tests/unit/provider-migration-readonly-wordpress.php "$WP:/tmp/migration-readonly-fixture.php"
cli eval-file /tmp/migration-readonly-fixture.php > proof/migration-readonly-native.json
node target/tests/unit/provider-compatibility-wordpress-browser.js
docker cp target/tests/unit/provider-compatibility-wordpress-dependency.php "$WP:/tmp/compatibility-dependency.php"
cli eval-file /tmp/compatibility-dependency.php > proof/compatibility-dependency-native.json
git -C target show "284dfd9ab24af4b77c99014aca5fa05343e7f503:src/includes/v6-provider-operations-service.php" > /tmp/backup-prior-service.php
docker cp /tmp/backup-prior-service.php "$WP:/tmp/backup-prior-service.php"
docker cp target/tests/unit/provider-backup-wordpress-fixture.php "$WP:/tmp/backup-fixture.php"
node target/tests/unit/provider-backup-wordpress-browser.js
VF_PHASE=restore cli eval-file /tmp/widget-native-phase.php > proof/native-source-recovery.json
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$SOURCE_VERSION"
VF_PHASE=rollback cli eval-file /tmp/widget-native-phase.php > proof/native-rollback.json
VF_PHASE=rollback node lane/quick.js
VF_PHASE=reapply cli eval-file /tmp/widget-native-phase.php > proof/native-reapply.json
VF_PHASE=reapply-readback cli eval-file /tmp/widget-native-phase.php > proof/native-reapply-readback.json || { docker cp "$WP:/tmp/candidate-options.json" proof/reapply-original-option-hashes.json;docker cp "$WP:/tmp/reapply-before.json" proof/reapply-before.json;docker cp "$WP:/tmp/reapply-after.json" proof/reapply-after.json;exit 1; }
docker cp "$WP:/tmp/reapply-before.json" proof/reapply-before.json
docker cp "$WP:/tmp/reapply-after.json" proof/reapply-after.json
VF_PHASE=reapply node lane/quick.js
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Clean Overview' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli plugin activate vf-ops >/dev/null
docker exec "$WP" rm -rf /var/www/html/wp-content/plugins/vf-tool-m3u8
cli plugin install /tmp/candidate.zip --activate >/dev/null
cli eval 'require_once ABSPATH."wp-admin/includes/plugin.php";$s=VF_M3U8_Runtime_Authority_V1::stored();if(VF_TOOL_M3U8_VERSION!==getenv("CANDIDATE_VERSION")||!is_plugin_active("vf-tool-m3u8/vf-tool-m3u8.php")||$s["file_count"]!==568||is_wp_error(VF_M3U8_Runtime_Authority_V1::verify(getenv("CANDIDATE_VERSION"),WP_PLUGIN_DIR."/vf-tool-m3u8"))){throw new Exception("clean install failed");}echo wp_json_encode(["status"=>"PASS","version"=>VF_TOOL_M3U8_VERSION,"runtime"=>$s,"state"=>VF_M3U8_Update_State_V1::snapshot(),"self"=>vf_tools_m3u8_provider_self_check()]);' > proof/clean-install.json
VF_PHASE=clean node lane/quick.js
docker cp proof/clean-install.json "$WP:/tmp/clean-install-before.json"
cli plugin activate vf-tool-m3u8 >/dev/null
cli eval 'require_once ABSPATH."wp-admin/includes/plugin.php";if(!is_plugin_active("vf-tool-m3u8/vf-tool-m3u8.php")||!VF_M3U8_Update_State_V1::equivalent(json_decode(file_get_contents("/tmp/clean-install-before.json"),true)["state"],VF_M3U8_Update_State_V1::snapshot()))throw new Exception("repeat activation changed owned state");echo wp_json_encode(["status"=>"PASS","version"=>VF_TOOL_M3U8_VERSION,"state"=>VF_M3U8_Update_State_V1::snapshot()]);' > proof/repeat-activation.json
python3 - <<'PYFINAL'
import pathlib,json,os
p=pathlib.Path('proof');identity=json.loads((p/'identity.json').read_text())
for name in ['native-baseline','native-corrupt-negative','native-upgrade','native-candidate','native-source-recovery','native-rollback','native-reapply','native-reapply-readback','clean-install','repeat-activation','overview-browser','overview-unit','diagnostic-unit','performance-unit','diagnostics-browser','compatibility-unit','compatibility-browser','compatibility-dependency-native','compatibility-quick-baseline','compatibility-quick-rollback','compatibility-quick-reapply','compatibility-quick-clean','migration-readonly-native','backup-browser','backup-integrity-native','runtime-browser','runtime-native','playground-baseline-session','playground-baseline-browser','playground-session','playground-browser','fixture-browser','fixture-native','pipeline-browser','pipeline-native','capability-browser','capability-native']:
 assert json.loads((p/(name+'.json')).read_text())['status']=='PASS',name
for name in ['native-candidate','native-reapply-readback','clean-install']:
 r=json.loads((p/(name+'.json')).read_text())['runtime'];assert r['fingerprint_sha256']==identity['runtime_fingerprint'] and r['file_count']==568 and r['version']==os.environ['TARGET_VERSION'],name
browser=json.loads((p/'overview-browser.json').read_text());unit=json.loads((p/'overview-unit.json').read_text())
r={**identity,'status':'PASS','native_upgrade':'PASS','source_state_recovery':'PASS','native_reapply':'PASS','clean_install':'PASS','corrupt_asset_guard':'PASS','overview_browser_cases':len(browser['cases']),'overview_unit_cases':len(unit['cases']),'diagnostic_unit_cases':len(json.loads((p/'diagnostic-unit.json').read_text())['cases']),'compatibility_browser_cases':len(json.loads((p/'compatibility-browser.json').read_text())['cases']),'compatibility_unit_cases':len(json.loads((p/'compatibility-unit.json').read_text())['cases']),'compatibility_dependency_native_cases':len(json.loads((p/'compatibility-dependency-native.json').read_text())['cases']),'performance_unit_cases':len(json.loads((p/'performance-unit.json').read_text())['cases']),'diagnostics_browser_cases':len(json.loads((p/'diagnostics-browser.json').read_text())['cases']),'migration_readonly_native_cases':len(json.loads((p/'migration-readonly-native.json').read_text())['cases']),'backup_browser_cases':len(json.loads((p/'backup-browser.json').read_text())['cases']),'backup_integrity_native_cases':len(json.loads((p/'backup-integrity-native.json').read_text())['cases']),'runtime_browser_cases':len(json.loads((p/'runtime-browser.json').read_text())['cases']),'runtime_native_cases':len(json.loads((p/'runtime-native.json').read_text())['cases']),'capability_browser_cases':len(json.loads((p/'capability-browser.json').read_text())['cases']),'capability_native_cases':len(json.loads((p/'capability-native.json').read_text())['cases']),'pipeline_browser_cases':len(json.loads((p/'pipeline-browser.json').read_text())['cases']),'pipeline_native_cases':len(json.loads((p/'pipeline-native.json').read_text())['cases']),'fixture_browser_cases':len(json.loads((p/'fixture-browser.json').read_text())['cases']),'fixture_native_cases':len(json.loads((p/'fixture-native.json').read_text())['cases']),'playground_browser_cases':len(json.loads((p/'playground-browser.json').read_text())['cases']),'playground_session_cases':len(json.loads((p/'playground-session.json').read_text())['cases']),'meaning':'BOUNDED_PLAYGROUND_REAL_EXECUTION_CONTROLS_AND_UX_UI','production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID']}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(r,indent=2));print('VF_CHAIN_FINAL_BEGIN');print(json.dumps(r));print('VF_CHAIN_FINAL_END')
PYFINAL


