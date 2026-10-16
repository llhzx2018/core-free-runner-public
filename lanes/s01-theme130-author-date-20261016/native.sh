#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-frontpages-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli-frontpages.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-cli-frontpages.phar "$WP:/usr/local/bin/wp"
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;echo "opcache.enable=0" > /usr/local/etc/php/conf.d/frontpages.ini;apachectl graceful' >/dev/null
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Frontend Page Directory' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker exec "$WP" mkdir -p /var/www/html/wp-content/themes/vf-tools-theme /var/www/html/wp-content/mu-plugins
docker cp "proof/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/target.zip"
docker cp "provider/vf-tools-theme_V$SOURCE_VERSION.zip" "$WP:/tmp/source.zip"
cli theme install /tmp/source.zip --activate >/dev/null
docker cp provider/vf-tools-m3u8_V1.25.91.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/frontpages-fixture.php"
docker cp lane/languages.php "$WP:/tmp/languages.php";docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php";docker cp lane/seed.php "$WP:/tmp/seed.php";docker cp lane/state.php "$WP:/tmp/state.php"
docker cp target/tests/search-archive-wordpress-check.php "$WP:/tmp/check.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
cli theme activate vf-tools-theme >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
cli eval-file /tmp/languages.php >/dev/null
cli eval-file /tmp/mount-seed.php > proof/mounts.json
cli rewrite structure '/%postname%/' --hard >/dev/null
cli eval-file /tmp/seed.php > proof/seed.json

# Warm lazy WordPress defaults before the readonly browser comparison.
curl -fsS http://127.0.0.1:18880/ >/dev/null
node lane/browser.cjs baseline
cli eval-file /tmp/state.php > proof/state-cold.json
node lane/browser.cjs warm
cli eval-file /tmp/state.php > proof/state-before.json
cli theme install /tmp/target.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
cli eval-file /tmp/check.php > proof/wordpress.json
node lane/browser.cjs candidate
cli eval-file /tmp/state.php > proof/state-candidate.json
cmp proof/state-before.json proof/state-candidate.json
cli theme install /tmp/source.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
node lane/browser.cjs warm
cli eval-file /tmp/state.php > proof/state-rollback.json
cmp proof/state-before.json proof/state-rollback.json
cli theme install /tmp/target.zip --force >/dev/null
node lane/browser.cjs reapply
cli eval-file /tmp/state.php > proof/state-reapply.json
cmp proof/state-before.json proof/state-reapply.json
cli theme install /tmp/target.zip --force >/dev/null
cli eval-file /tmp/state.php > proof/state-idempotent.json
cmp proof/state-before.json proof/state-idempotent.json
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Clean Directory' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli theme install /tmp/target.zip --force --activate >/dev/null
cli plugin install /tmp/provider.zip --force --activate >/dev/null
cli plugin install polylang --version=3.8.10 --force --activate >/dev/null
cli eval-file /tmp/languages.php >/dev/null
cli eval-file /tmp/mount-seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
cli eval-file /tmp/seed.php > proof/seed.json
cli eval-file /tmp/check.php > proof/wordpress-clean.json
node lane/browser.cjs warm
cli eval-file /tmp/state.php > proof/state-clean-before.json
node lane/browser.cjs clean
cli eval-file /tmp/state.php > proof/state-clean-after.json
cmp proof/state-clean-before.json proof/state-clean-after.json
curl -fsS http://127.0.0.1:18880/wp-admin/install.php > /tmp/setup-revisit.html
python3 - <<'PY'
import os,json,pathlib
p=pathlib.Path('proof')
for name in ['wordpress','wordpress-clean','browser-candidate','browser-reapply','browser-clean']:
 f=json.loads((p/(name+'.json')).read_text());assert f['status']=='PASS' and len(f['checks'])>=20 and all(c['pass'] for c in f['checks'])
before=(p/'state-before.json').read_bytes()
for phase in ['candidate','rollback','reapply','idempotent']:assert before==(p/('state-'+phase+'.json')).read_bytes()
assert (p/'state-clean-before.json').read_bytes()==(p/'state-clean-after.json').read_bytes()
assert 'Already Installed' in pathlib.Path('/tmp/setup-revisit.html').read_text()
r={'status':'PASS','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'version':os.environ['TARGET_VERSION'],'protected_configuration_content_translations':'UNCHANGED','shell_header_menu':'UNCHANGED','checks':{'clean_full':'PASS','upgrade129to130':'PASS','rollback129':'PASS','reapply':'PASS','idempotent':'PASS','setup_revisit_locked':'PASS','wordpress':'PASS','browser':'PASS'},'mobile':'NOT_RUN_OWNER_DEFERRED','release':'NOT_EXECUTED','production':'NOT_EXECUTED','owner_real_use':'POST_PRODUCTION_REQUIRED'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
PY
