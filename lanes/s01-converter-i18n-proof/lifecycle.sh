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
docker exec "$WP" rmdir /var/www/html/wp-content/themes/vf-tools-theme
for pkg in provider/*.zip; do docker cp "$pkg" "$WP:/tmp/$(basename "$pkg")"; done
cli theme install /tmp/vf-tools-theme_V1.35.220.zip >/dev/null
cli plugin install /tmp/vf-tools-m3u8_V1.25.96.zip --activate >/dev/null
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
docker cp control/lanes/s01-converter-i18n-proof/plugin-snapshot.php "$WP:/tmp/plugin-snapshot.php"
# Warm only public read-only boot paths before protected-state comparison.
curl -fsS http://127.0.0.1:18880/ >/dev/null
curl -fsS http://127.0.0.1:18880/m3u8-playlist-checker/ >/dev/null
cli eval-file /tmp/snapshot.php > proof/bootstrap-before.json
node lane/warm-admin.cjs
cli eval-file /tmp/snapshot.php > proof/bootstrap-after.json
python3 - <<'PYBOOT'
import json,pathlib
r=pathlib.Path('proof');a=json.loads((r/'bootstrap-before.json').read_text());b=json.loads((r/'bootstrap-after.json').read_text());changed=[k for k in a['sections']if a['sections'][k]!=b['sections'][k]]
assert set(changed)<= {'vf_theme_brand','vf_theme_tokens','vf_theme_navigation'}
assert all(not a['option_presence'][k]and b['option_presence'][k]for k in changed)
(r/'bootstrap.json').write_text(json.dumps({'status':'PASS','created_missing_options':changed,'existing_protected_records':'BYTE_IDENTICAL','scope':'fresh isolated installation initialization before review baseline'}))
PYBOOT
cli eval-file /tmp/snapshot.php > proof/state-before.sha256
node control/lanes/s01-converter-i18n-proof/check.cjs
docker cp control/lanes/s01-converter-i18n-proof/seasonal-guard.php "$WP:/tmp/seasonal-guard.php"
cli eval-file /tmp/seasonal-guard.php > proof/seasonal-guard.json
cat proof/seasonal-guard.json
cli eval-file /tmp/plugin-snapshot.php > proof/plugin-options-before.json
cli eval-file /tmp/plugin-snapshot.php > proof/plugin-options-repeat-before-install.json
tv(){ test "$(cli theme get vf-tools-theme --field=version)" = "$1"; }
pv(){ test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$1"; }
tv 1.35.220; pv 1.25.96
for old in 1.35.219 1.35.216; do
  cli theme install "/tmp/vf-tools-theme_V$old.zip" --force >/dev/null; tv "$old"
  cli theme install /tmp/vf-tools-theme_V1.35.220.zip --force >/dev/null; tv 1.35.220
done
cli theme install /tmp/vf-tools-theme_V1.35.220.zip --force >/dev/null; tv 1.35.220
for old in 1.25.95 1.25.94; do
  cli plugin install "/tmp/vf-tools-m3u8_V$old.zip" --force >/dev/null; pv "$old"; cli eval-file /tmp/plugin-snapshot.php > "proof/plugin-after-old-$old.json"
  cli plugin install /tmp/vf-tools-m3u8_V1.25.96.zip --force >/dev/null; pv 1.25.96; cli eval-file /tmp/plugin-snapshot.php > "proof/plugin-after-new-$old.json"
done
cli plugin install /tmp/vf-tools-m3u8_V1.25.96.zip --force >/dev/null; pv 1.25.96
cli eval-file /tmp/plugin-snapshot.php > proof/plugin-options-after.json
python3 - <<'PYPLUGIN'
import json,pathlib
a=json.loads(pathlib.Path('proof/plugin-options-before.json').read_text())
b=json.loads(pathlib.Path('proof/plugin-options-after.json').read_text())
changed=[k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]
print('PLUGIN_CHANGED_OPTION_NAMES',changed)
assert not changed
PYPLUGIN
echo NATIVE_INSTALL_UPGRADE_ROLLBACK_REINSTALL_PLUGIN_OPTIONS_PASS
cli eval-file /tmp/snapshot.php > proof/state-after.sha256
cmp proof/state-before.sha256 proof/state-after.sha256
echo DOWNLOADER_DATA_PROTECTION_PASS
