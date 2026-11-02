#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-r2-$GITHUB_RUN_ID"
DB="$NET-db"
WP="$NET-wp"
cleanup() { docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
READY=0
for i in $(seq 1 70); do if docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1; then READY=1; break; fi; sleep 2; done
test "$READY" = 1
docker run -d --name "$WP" --network "$NET" -p 18883:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
READY=0
for i in $(seq 1 90); do if docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18883/wp-admin/install.php >/dev/null; then READY=1; break; fi; sleep 2; done
test "$READY" = 1
curl -fsSLo /tmp/s01-r2-wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/s01-r2-wp-cli.phar "$WP:/usr/local/bin/wp"
cli() { docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18883 --title='S01 R2 Synthetic Site' --admin_user=admin --admin_password='Synthetic-Only-R2!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp target/src/includes/skin-seasonal.php "$WP:/tmp/r2-skin-seasonal.php"
docker cp target/tests/seasonal-empty-retry-wordpress.php "$WP:/tmp/r2-wordpress-fixture.php"
docker cp control/lanes/s01-r2-m3u8-20261102/wordpress-fixture.php "$WP:/tmp/r2-entry.php"
cli eval-file /tmp/r2-entry.php
echo S01_R2_NATIVE_WORDPRESS_MARIADB=PASS
