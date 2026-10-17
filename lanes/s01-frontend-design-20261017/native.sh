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
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Frontend Review' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker exec "$WP" mkdir -p /var/www/html/wp-content/themes/vf-tools-theme /var/www/html/wp-content/mu-plugins
docker cp target/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
docker cp provider/vf-tools-m3u8_V1.25.91.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/progress-fixture.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
cli theme activate vf-tools-theme >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
docker cp lane/languages.php "$WP:/tmp/languages.php";cli eval-file /tmp/languages.php >/dev/null
docker cp lane/wp-check.php "$WP:/tmp/wp-check.php";cli eval-file /tmp/wp-check.php > proof/wordpress.json
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php";cli eval-file /tmp/mount-seed.php > proof/mounts.json
docker cp lane/seed.php "$WP:/tmp/seed.php";cli eval-file /tmp/seed.php > proof/seed.json
docker cp lane/extra-seed.php "$WP:/tmp/extra-seed.php";cli eval-file /tmp/extra-seed.php > proof/cases.json
docker cp lane/snapshot.php "$WP:/tmp/snapshot.php"
# Warm only public read-only boot paths before protected-state comparison.
curl -fsS http://127.0.0.1:18880/ >/dev/null
curl -fsS http://127.0.0.1:18880/m3u8-playlist-checker/ >/dev/null
cli eval-file /tmp/snapshot.php > proof/state-before.sha256
if [ "${VF_REVIEW_ONLY_STATE:-0}" = "1" ];then node lane/state-browser.cjs;elif [ "${VF_REVIEW_ONLY_SHELL:-0}" = "1" ];then node lane/shell-browser.cjs;else node lane/public-browser.cjs;fi
cli eval-file /tmp/snapshot.php > proof/state-after.sha256
cmp proof/state-before.sha256 proof/state-after.sha256
python3 - <<'PY'
import json,pathlib,os
for name in ['wordpress','state-browser'if os.environ.get('VF_REVIEW_ONLY_STATE')=='1'else'shell-result'if os.environ.get('VF_REVIEW_ONLY_SHELL')=='1'else'public-browser']:
 data=json.loads(pathlib.Path('proof',name+'.json').read_text());assert data['status']=='PASS' and all(c['pass'] for c in data['checks'])
print('Exact-source WordPress/MariaDB and browser checks passed.')
PY
