#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-home-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
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
mkdir baseline
cp -a target/src baseline/src
python3 - <<'PYBASE'
import json,pathlib,subprocess,os
for rel in json.loads(pathlib.Path('lane/source-meta.json').read_text())['changed_files']:
 pathlib.Path('baseline',rel).write_bytes(subprocess.check_output(['git','-C','target','show',os.environ['BASE_SHA']+':'+rel]))
PYBASE
docker cp baseline/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
docker cp provider/vf-tools-m3u8_V1.25.91.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/progress-fixture.php"
docker cp lane/home-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/home-fixture.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
cli theme activate vf-tools-theme >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
docker cp lane/languages.php "$WP:/tmp/languages.php";cli eval-file /tmp/languages.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php";cli eval-file /tmp/mount-seed.php > proof/mounts.json
docker cp lane/seed.php "$WP:/tmp/seed.php";cli eval-file /tmp/seed.php > proof/seed.json
docker cp lane/extra-seed.php "$WP:/tmp/extra-seed.php";cli eval-file /tmp/extra-seed.php > proof/cases.json
docker cp lane/snapshot.php "$WP:/tmp/snapshot.php"
# Warm only public read-only boot paths before protected-state comparison.
curl -fsS http://127.0.0.1:18880/ >/dev/null
curl -fsS http://127.0.0.1:18880/m3u8-playlist-checker/ >/dev/null
cli eval-file /tmp/snapshot.php > proof/bootstrap-before.json
node lane/warm-admin.cjs
cli eval-file /tmp/snapshot.php > proof/bootstrap-after.json
python3 - <<'PYBOOT'
import json,pathlib
r=pathlib.Path('proof');a=json.loads((r/'bootstrap-before.json').read_text());b=json.loads((r/'bootstrap-after.json').read_text());changed=[k for k in a['sections']if a['sections'][k]!=b['sections'][k]]
assert set(changed)<= {'vf_theme_brand','vf_theme_tokens','vf_theme_navigation','vf_theme_ads','vf_theme_seo'}
assert all(not a['option_presence'][k]and b['option_presence'][k]for k in changed)
(r/'bootstrap.json').write_text(json.dumps({'status':'PASS','created_missing_options':changed,'existing_protected_records':'BYTE_IDENTICAL','scope':'fresh isolated installation initialization before review baseline'}))
PYBOOT
cli eval-file /tmp/snapshot.php > proof/state-before.json
node lane/browser.cjs baseline
docker cp target/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
docker cp lane/priority-check.php "$WP:/tmp/priority-check.php";cli eval-file /tmp/priority-check.php > proof/priority.json
node lane/browser.cjs candidate
cli eval-file /tmp/snapshot.php > proof/state-after.json
cmp proof/state-before.json proof/state-after.json
python3 - <<'PY'
import json,pathlib,os,hashlib
r=pathlib.Path('proof');b=json.loads((r/'browser.json').read_text());p=json.loads((r/'priority.json').read_text())
assert b['status']==p['status']=='PASS'
assert all(c['pass']for c in b['checks']+p['checks'])
(r/'FINAL_EVIDENCE.json').write_text(json.dumps({'status':'PASS','target_sha':os.environ['TARGET_SHA'],'target_tree':os.environ['TARGET_TREE'],'base_sha':os.environ['BASE_SHA'],'browser_checks':len(b['checks']),'priority_checks':len(p['checks']),'protected_state':'BYTE_IDENTICAL','state_sha256':hashlib.sha256((r/'state-before.json').read_bytes()).hexdigest(),'mobile':'OWNER_DEFERRED_NOT_TESTED','production':'NOT_EXECUTED','scope':'focused home presentation, real isolated WordPress and bilingual desktop browser'},indent=2))
PY
rm -rf baseline
