#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-design-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli-review.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-cli-review.phar "$WP:/usr/local/bin/wp"
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;echo "opcache.enable=0" > /usr/local/etc/php/conf.d/review.ini;apachectl graceful' >/dev/null
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='M3U8.ONE' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker exec "$WP" mkdir -p /var/www/html/wp-content/themes/vf-tools-theme /var/www/html/wp-content/mu-plugins
docker exec "$WP" rmdir /var/www/html/wp-content/themes/vf-tools-theme
docker cp baseline/src "$WP:/var/www/html/wp-content/themes/vf-tools-theme"
docker cp provider/vf-tools-m3u8_V1.25.94.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/progress-fixture.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
cli theme activate vf-tools-theme >/dev/null
for attempt in 1 2 3; do cli plugin install polylang --version=3.8.10 --activate >/dev/null && break; test "$attempt" -lt 3 || exit 1; sleep 3; done
docker cp lane/languages.php "$WP:/tmp/languages.php";cli eval-file /tmp/languages.php >/dev/null
# Native zh_CN core translations are required for the real CJK word-count mode.
for attempt in 1 2 3; do cli language core install zh_CN >/dev/null && break; test "$attempt" -lt 3 || exit 1; sleep 3; done
# Only initialize the existing admin capability; do not repeat unrelated review-service suites.
cli user add-cap admin vf_manage_theme_profile >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php";cli eval-file /tmp/mount-seed.php > proof/mounts.json
docker cp "control/lanes/$LANE_ID/seed.php" "$WP:/tmp/extra-protected.php";cli eval-file /tmp/extra-protected.php >/dev/null
docker cp lane/snapshot.php "$WP:/tmp/snapshot.php"
docker cp "control/lanes/$LANE_ID/summary-probe.php" "$WP:/var/www/html/wp-content/mu-plugins/summary-probe.php"
cli option update vf_summary_probe_called not-executed >/dev/null
curl -sS http://127.0.0.1:18880/vf-page-check-404/ >/dev/null
docker cp "control/lanes/$LANE_ID/search-seed.php" "$WP:/tmp/search-seed.php";cli eval-file /tmp/search-seed.php > proof/search-fixtures.json
docker cp "control/lanes/$LANE_ID/settings.php" "$WP:/tmp/404-settings.php"
docker cp "control/lanes/$LANE_ID/contracts-snapshot.php" "$WP:/tmp/contracts-snapshot.php"
export WP
NODE_PATH="$PWD/node_modules" node "control/lanes/$LANE_ID/check.cjs" before
cli eval-file /tmp/snapshot.php > proof/state-before.json
cli eval-file /tmp/contracts-snapshot.php > proof/contracts-before.json
docker cp target/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
docker cp "control/lanes/$LANE_ID/hero-check.php" "$WP:/tmp/404-hero-check.php"
cli eval-file /tmp/404-hero-check.php > proof/hero-check.txt
NODE_PATH="$PWD/node_modules" node "control/lanes/$LANE_ID/check.cjs" after
cli eval-file /tmp/404-settings.php restore >/dev/null
cli eval-file /tmp/snapshot.php > proof/state-after.json
cli eval-file /tmp/contracts-snapshot.php > proof/contracts-after.json
cmp proof/state-before.json proof/state-after.json
cmp proof/contracts-before.json proof/contracts-after.json
test "$(cli option get vf_summary_probe_called)" = not-executed
echo PASSIVE_SUMMARIES_NEVER_EXECUTE_SHORTCODE
echo PROTECTED_STATE_AND_NATIVE_REVIEW_NOTES_BYTE_IDENTICAL
