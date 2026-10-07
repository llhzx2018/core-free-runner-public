#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-v8-${GITHUB_RUN_ID}";DB="$NET-db";export WP="$NET-wp"
TASK_ROOT="$PWD"
cleanup(){ docker rm -f "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -e CANDIDATE_VERSION="$TARGET_VERSION" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e TARGET_VERSION="$TARGET_VERSION" -e CANDIDATE_VERSION="$TARGET_VERSION" -e VF_PHASE="${VF_PHASE:-}" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Theme Integration' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "provider/vf-tools-theme_V${THEME_VERSION}.zip" "$WP:/tmp/theme.zip"
cli theme install /tmp/theme.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$THEME_VERSION"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/vf-render-fixture.php"
docker cp lane/vf-render-fixture.js "$WP:/var/www/html/wp-content/mu-plugins/vf-render-fixture.js"
docker cp lane/vf-render-module.js "$WP:/var/www/html/wp-content/mu-plugins/vf-render-module.js"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/mu-plugins
docker cp lane/seed.php "$WP:/tmp/integration-seed.php"
seed(){ cli eval-file /tmp/integration-seed.php > proof/seed.json; }
seed

docker cp provider/vf-tools-m3u8_V${SOURCE_VERSION}.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate > /tmp/provider-install.txt
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$SOURCE_VERSION"
docker cp "proof/vf-tools-m3u8_V${TARGET_VERSION}.zip" "$WP:/tmp/candidate.zip"
docker cp proof/synthetic-channel.json "$WP:/tmp/synthetic-channel.json"
docker cp lane/mock-update.php "$WP:/var/www/html/wp-content/mu-plugins/synthetic-update-transport.php"
docker cp lane/phase.php "$WP:/tmp/widget-native-phase.php"
docker cp lane/dependency-seed.php "$WP:/tmp/dependency-seed.php"
docker cp lane/dependency-head-proof.php "$WP:/tmp/dependency-head-proof.php"
cli eval-file /tmp/dependency-seed.php > proof/dependency-seed.json
cli eval-file /tmp/dependency-head-proof.php > proof/dependency-head-proof.json
mkdir -p checks/baseline/proof checks/candidate/proof
cp proof/dependency-head-proof.json checks/baseline/proof/
cp proof/dependency-head-proof.json checks/candidate/proof/
VF_PHASE=baseline node lane/widget-regression.js > /tmp/baseline-browser.txt 2>&1 || { tail -c 12000 /tmp/baseline-browser.txt;exit 1; }
cp -a proof/. checks/baseline/proof/
VF_PHASE=seed cli eval-file /tmp/widget-native-phase.php > proof/native-baseline.json
VF_PHASE=negative cli eval-file /tmp/widget-native-phase.php > proof/native-corrupt-negative.json
VF_PHASE=upgrade cli eval-file /tmp/widget-native-phase.php > proof/native-upgrade.json
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$TARGET_VERSION"
VF_PHASE=candidate cli eval-file /tmp/widget-native-phase.php > proof/native-candidate.json
VF_PHASE=candidate node lane/widget-regression.js > /tmp/candidate-browser.txt 2>&1 || { tail -c 12000 /tmp/candidate-browser.txt;exit 1; }
cat /tmp/candidate-browser.txt
cp -a proof/. checks/candidate/proof/
VF_PHASE=restore cli eval-file /tmp/widget-native-phase.php > proof/native-source-recovery.json
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$SOURCE_VERSION"
VF_PHASE=rollback cli eval-file /tmp/widget-native-phase.php > proof/native-rollback.json
VF_PHASE=rollback node lane/widget-regression.js > /tmp/rollback-browser.txt 2>&1 || { tail -c 12000 /tmp/rollback-browser.txt;exit 1; }
VF_PHASE=reapply cli eval-file /tmp/widget-native-phase.php > proof/native-reapply.json
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$TARGET_VERSION"
VF_PHASE=candidate cli eval-file /tmp/widget-native-phase.php > proof/native-reapply-readback.json
VF_PHASE=reapply node lane/widget-regression.js > /tmp/reapply-browser.txt 2>&1 || { tail -c 12000 /tmp/reapply-browser.txt;exit 1; }
# Same real C03-candidate WP instance: canonical eight Theme pages and their
# sixteen actual saves/front-end/recovery interactions, without resetting DB.
mkdir -p checks/integration/proof;ln -sfn ../../lane checks/integration/lane
(cd checks/integration && node "$TASK_ROOT/lane/integration.js")
cp -a checks/integration/proof/. proof/integration/
# Real clean database, leaving previous-state preservation evidence intact.
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Clean Widget' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli theme activate vf-tools-theme >/dev/null
# Empty DB has no active plugins; discard only disposable runtime files and
# install exact candidate ZIP through native WordPress into clean database.
docker exec "$WP" rm -rf /var/www/html/wp-content/plugins/vf-tool-m3u8
cli plugin install /tmp/candidate.zip --activate >/dev/null
seed
cli eval-file /tmp/dependency-seed.php > proof/clean-seed.json
cli eval 'require_once ABSPATH."wp-admin/includes/plugin.php";$s=VF_M3U8_Runtime_Authority_V1::stored();if(VF_TOOL_M3U8_VERSION!==getenv("CANDIDATE_VERSION")||!is_plugin_active("vf-tool-m3u8/vf-tool-m3u8.php")||$s["file_count"]!==567||is_wp_error(VF_M3U8_Runtime_Authority_V1::verify(getenv("CANDIDATE_VERSION"),WP_PLUGIN_DIR."/vf-tool-m3u8"))){throw new Exception("clean install failed");}echo wp_json_encode(["status"=>"PASS","version"=>VF_TOOL_M3U8_VERSION,"runtime"=>$s,"provider_state"=>VF_M3U8_Update_State_V1::snapshot()]);' > proof/clean-install.json
cli eval-file /tmp/dependency-head-proof.php > proof/dependency-head-proof.json
VF_PHASE=clean node lane/widget-regression.js > /tmp/clean-browser.txt 2>&1 || { tail -c 12000 /tmp/clean-browser.txt;exit 1; }
curl -fsS http://127.0.0.1:18880/m3u8-player/ > /tmp/clean-tool.html
! grep -Ei 'Fatal error|critical error|Parse error' /tmp/clean-tool.html
python3 - <<'PYFINAL'
import pathlib,json,os
p=pathlib.Path('proof');identity=json.loads((p/'identity.json').read_text());base=json.loads(pathlib.Path('checks/baseline/proof/widget-result.json').read_text());candidate=json.loads(pathlib.Path('checks/candidate/proof/widget-result.json').read_text());assert base['issue_count']==4 and candidate['issue_count']==0
for name in ['native-baseline','native-corrupt-negative','native-upgrade','native-candidate','native-source-recovery','native-rollback','native-reapply','native-reapply-readback','clean-install','widget-quick-rollback','widget-quick-reapply','widget-quick-clean']:
 assert json.loads((p/(name+'.json')).read_text())['status']=='PASS',name
for name in ['native-candidate','native-reapply-readback','clean-install']:
 r=json.loads((p/(name+'.json')).read_text())['runtime'];assert r['fingerprint_sha256']==identity['runtime_fingerprint'] and r['file_count']==567 and r['version']==os.environ['TARGET_VERSION'],name
integration=json.loads((p/'integration/integration.json').read_text());assert integration['status']=='PASS'
r={**identity,'status':'PASS','baseline_engine_issues':4,'candidate_engine_issues':0,'baseline_engine_status':base['engine_status'],'candidate_engine_status':candidate['engine_status'],'native_upgrade':'PASS','source_state_recovery':'PASS','native_reapply':'PASS','clean_install':'PASS','corrupt_asset_guard':'PASS','cross_page_cases':len(integration['cases']),'canonical_pages':8,'theme_version':os.environ['THEME_VERSION'],'meaning':'BOUNDED_WIDGET_HOST_FIX_AND_SHARED_THEME_CONFIGURATION_CHECKS','production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID']}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(r,indent=2));print('VF_CHAIN_FINAL_BEGIN');print(json.dumps(r));print('VF_CHAIN_FINAL_END')
PYFINAL
