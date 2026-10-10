#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-embed78-${GITHUB_RUN_ID}";DB="$NET-db";export WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -e CANDIDATE_VERSION="$TARGET_VERSION" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e SOURCE_VERSION="$SOURCE_VERSION" -e TARGET_VERSION="$TARGET_VERSION" -e CANDIDATE_VERSION="$TARGET_VERSION" -e VF_PHASE="${VF_PHASE:-}" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Embed Integration' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "provider/vf-tools-theme_V${THEME_VERSION}.zip" "$WP:/tmp/theme.zip"
cli theme install /tmp/theme.zip --activate >/dev/null
docker cp "provider/vf-tools-m3u8_V${SOURCE_VERSION}.zip" "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
cli plugin install polylang --version="$POLYLANG_VERSION" --activate >/dev/null
docker cp lane/seed.php "$WP:/tmp/seed.php";cli eval-file /tmp/seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
node lane/browser.js baseline
for route in '' en zh m3u8-player embed m3u8-browser-stream-test m3u8-playlist-checker m3u8-segment-viewer m3u8-encryption-detector m3u8-downloader m3u8-to-mp4 iptv-manager m3u8-test-links m3u8-backup-restore;do curl -fsSL "http://127.0.0.1:18880/$route/" >/dev/null;done
docker cp "proof/vf-tools-m3u8_V${TARGET_VERSION}.zip" "$WP:/tmp/candidate.zip"
docker cp proof/synthetic-channel.json "$WP:/tmp/synthetic-channel.json"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/mock-update.php "$WP:/var/www/html/wp-content/mu-plugins/synthetic-update-transport.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/mu-plugins
docker cp lane/phase.php "$WP:/tmp/native-phase.php"
VF_PHASE=seed cli eval-file /tmp/native-phase.php > proof/native-baseline.json
VF_PHASE=negative cli eval-file /tmp/native-phase.php > proof/native-corrupt-negative.json
VF_PHASE=upgrade cli eval-file /tmp/native-phase.php > proof/native-upgrade.json
VF_PHASE=candidate cli eval-file /tmp/native-phase.php > proof/native-candidate.json
node lane/browser.js candidate
VF_PHASE=restore cli eval-file /tmp/native-phase.php > proof/native-source-recovery.json
VF_PHASE=rollback cli eval-file /tmp/native-phase.php > proof/native-rollback.json
node lane/browser.js rollback
VF_PHASE=reapply cli eval-file /tmp/native-phase.php > proof/native-reapply.json
VF_PHASE=candidate cli eval-file /tmp/native-phase.php > proof/native-reapply-readback.json
node lane/browser.js reapply
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Clean Embed' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli theme activate vf-tools-theme >/dev/null
docker exec "$WP" rm -rf /var/www/html/wp-content/plugins/vf-tool-m3u8
cli plugin install /tmp/candidate.zip --activate >/dev/null
cli plugin activate polylang >/dev/null
cli eval-file /tmp/seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
cli eval 'require_once ABSPATH."wp-admin/includes/plugin.php";$s=VF_M3U8_Runtime_Authority_V1::stored();if(VF_TOOL_M3U8_VERSION!==getenv("CANDIDATE_VERSION")||!is_plugin_active("vf-tool-m3u8/vf-tool-m3u8.php")||$s["file_count"]!==568||is_wp_error(VF_M3U8_Runtime_Authority_V1::verify(getenv("CANDIDATE_VERSION"),WP_PLUGIN_DIR."/vf-tool-m3u8")))throw new Exception("clean install failed");echo wp_json_encode(["status"=>"PASS","version"=>VF_TOOL_M3U8_VERSION,"runtime"=>$s,"state"=>VF_M3U8_Update_State_V1::snapshot()]);' > proof/clean-install.json
node lane/browser.js clean
docker cp proof/clean-install.json "$WP:/tmp/clean-before.json"
cli plugin activate vf-tool-m3u8 >/dev/null
cli eval 'if(!VF_M3U8_Update_State_V1::equivalent(json_decode(file_get_contents("/tmp/clean-before.json"),true)["state"],VF_M3U8_Update_State_V1::snapshot()))throw new Exception("repeat activation changed owned state");echo wp_json_encode(["status"=>"PASS"]);' > proof/repeat-activation.json
python3 - <<'PY'
import pathlib,json,os
p=pathlib.Path('proof');identity=json.loads((p/'identity.json').read_text())
names=['native-baseline','native-corrupt-negative','native-upgrade','native-candidate','native-source-recovery','native-rollback','native-reapply','native-reapply-readback','embed-candidate','embed-reapply','clean-install','repeat-activation','embed-clean']
checks={n:json.loads((p/(n+'.json')).read_text())['status'] for n in names}
baseline=json.loads((p/'embed-baseline.json').read_text())['toolPath'];rollback=json.loads((p/'embed-rollback.json').read_text())['toolPath']
reproduced=baseline.get('endpoint')!='1' and rollback.get('endpoint')!='1'
assert json.loads((p/'embed-baseline.json').read_text())['status']=='OBSERVED' and json.loads((p/'embed-rollback.json').read_text())['status']=='OBSERVED'
result={**identity,'status':'PASS' if all(x=='PASS' for x in checks.values()) and reproduced else 'FAIL','checks':checks,'old_version_failure_reproduced':reproduced,'production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID']}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));assert result['status']=='PASS'
PY
