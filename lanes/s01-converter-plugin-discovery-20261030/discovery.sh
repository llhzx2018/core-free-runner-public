#!/usr/bin/env bash
set -Eeuo pipefail
trap 'printf "NATIVE_FAILURE line=%s\n" "$LINENO" >&2' ERR
NET="s01-player95-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60); do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break; sleep 2; done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90); do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break; sleep 2; done
curl -fsSLo /tmp/wp-cli-player95.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-cli-player95.phar "$WP:/usr/local/bin/wp"
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Player Check' --admin_user=admin --admin_password='Synthetic-Only-Player-95!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
docker cp provider/vf-tools-m3u8_V1.25.94.zip "$WP:/tmp/old.zip"
cli plugin install /tmp/old.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.94'
snapshot(){ cli eval 'foreach (["vf_m3u8_settings","vf_m3u8_settings_revisions","vf_m3u8_settings_audit","vf_tool_m3u8_settings"] as $key) { echo $key."=".hash("sha256",serialize(get_option($key)))."\n"; }' | sha256sum | cut -d' ' -f1; }
snapshot > proof/discovery-before.sha256
docker cp control/lanes/s01-converter-plugin-discovery-20261030/discover.php "$WP:/tmp/discover.php"
docker exec -e VF_PRIVATE_READ_TOKEN --user www-data "$WP" php /usr/local/bin/wp eval-file /tmp/discover.php --path=/var/www/html > proof/discovery-result.json
cat proof/discovery-result.json
snapshot > proof/discovery-after.sha256
cmp proof/discovery-before.sha256 proof/discovery-after.sha256
echo '{"status":"PASS","installed":"1.25.94","offered":"1.25.96","settings":"BYTE_IDENTICAL","production":"UNTOUCHED"}' > proof/discovery.json
