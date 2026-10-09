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
docker cp lane/phase.php "$WP:/tmp/widget-native-phase.php"
VF_PHASE=seed cli eval-file /tmp/widget-native-phase.php > proof/native-baseline.json
docker cp target/tests/unit/provider-runtime-wordpress-fixture.php "$WP:/tmp/runtime-fixture.php"
node lane/click.js
