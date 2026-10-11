#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-tools-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp";export WP
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60); do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break; sleep 2; done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90); do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break; sleep 2; done
curl -fsSLo /tmp/wp-cli-s01.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli-s01.phar "$WP:/usr/local/bin/wp"; docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic S01 Tool Regression' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "provider/vf-tools-theme_V$SOURCE_VERSION.zip" "$WP:/tmp/theme106.zip"
docker cp "provider/vf-tools-m3u8_V$M3_SOURCE_VERSION.zip" "$WP:/tmp/m378.zip"
docker cp "proof/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/theme107.zip"
docker cp "proof/vf-tools-m3u8_V$M3_VERSION.zip" "$WP:/tmp/m379.zip"
cli theme install /tmp/theme106.zip --activate >/dev/null
cli plugin install /tmp/m378.zip --activate >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
docker cp lane/seed.php "$WP:/tmp/seed.php"
cli eval-file /tmp/seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php"
cli eval-file /tmp/mount-seed.php > proof/mount-seed-${TARGET_VERSION}.json
cli eval 'update_option("s01_synthetic_cross_owner_keep",["owner"=>"keep","value"=>1707]);set_theme_mod("s01_synthetic_keep","retained");update_option("s01_synthetic_mount_hash",hash("sha256",serialize(vf_m3u8_mounts_data(true))));echo "OK";' >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_SOURCE_VERSION"
node lane/browser.js baseline
cli theme install /tmp/theme107.zip --force >/dev/null
cli plugin install /tmp/m379.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_VERSION"
cli eval 'if(get_option("s01_synthetic_cross_owner_keep")!==["owner"=>"keep","value"=>1707] || get_theme_mod("s01_synthetic_keep")!=="retained"||get_option("s01_synthetic_mount_hash")!==hash("sha256",serialize(vf_m3u8_mounts_data(true))))throw new Exception("cross owner state lost");echo wp_json_encode(["status"=>"PASS","cross_owner_state"=>"retained","theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION]);' > proof/state-upgrade.json
node lane/browser.js candidate
TARGET_VERSION="$M3_VERSION" SOURCE_VERSION="$M3_SOURCE_VERSION" node lane/embed-browser.js candidate
cli theme install /tmp/theme106.zip --force >/dev/null
cli plugin install /tmp/m378.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_SOURCE_VERSION"
cli eval 'if(get_option("s01_synthetic_cross_owner_keep")!==["owner"=>"keep","value"=>1707]||get_theme_mod("s01_synthetic_keep")!=="retained"||get_option("s01_synthetic_mount_hash")!==hash("sha256",serialize(vf_m3u8_mounts_data(true))))throw new Exception("rollback state lost");echo wp_json_encode(["status"=>"PASS"]);' > proof/state-rollback.json
node lane/browser.js rollback
cli theme install /tmp/theme107.zip --force >/dev/null
cli plugin install /tmp/m379.zip --force >/dev/null
cli eval 'if(get_option("s01_synthetic_cross_owner_keep")!==["owner"=>"keep","value"=>1707]||get_theme_mod("s01_synthetic_keep")!=="retained"||get_option("s01_synthetic_mount_hash")!==hash("sha256",serialize(vf_m3u8_mounts_data(true))))throw new Exception("reapply state lost");echo wp_json_encode(["status"=>"PASS"]);' > proof/state-reapply.json
node lane/browser.js reapply
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic S01 Clean' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli theme install /tmp/theme107.zip --activate --force >/dev/null
cli plugin install /tmp/m379.zip --activate --force >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
cli eval-file /tmp/seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php"
cli eval-file /tmp/mount-seed.php > proof/mount-seed-${TARGET_VERSION}.json
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_VERSION"
node lane/browser.js clean
cli plugin activate vf-tool-m3u8 >/dev/null
cli eval 'echo wp_json_encode(["status"=>"PASS","theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION]);' > proof/clean-installed.json
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path('proof')
targets=['embed-alias-php','attribute-php','state-upgrade','state-rollback','state-reapply','tools-candidate','tools-reapply','tools-clean','embed-candidate','clean-installed']
states={n:json.loads((p/(n+'.json')).read_text())['status'] for n in targets}
assert all(v=='PASS' for v in states.values()),states
e={'status':'PASS','theme_source_sha':os.environ['TARGET_SHA'],'theme_source_tree':os.environ['TARGET_TREE'],'m3_source_sha':os.environ['M3_SHA'],'m3_source_tree':os.environ['M3_TREE'],'theme_version':os.environ['TARGET_VERSION'],'m3_version':os.environ['M3_VERSION'],'checks':states,'production':'NOT_EXECUTED','owner_product_pass':'PENDING'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(e,sort_keys=True,indent=2))
print('SAFE_FINAL',json.dumps(e,sort_keys=True))
PY
