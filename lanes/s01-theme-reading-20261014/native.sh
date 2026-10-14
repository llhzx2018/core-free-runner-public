#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-tools-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp";export WP
cleanup(){ docker logs "$WP" 2>&1 | grep 'module render skipped' | tail -12 || true; docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
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
docker cp baseline/src "$WP:/var/www/html/wp-content/themes/vf-tools-theme"
docker cp provider/vf-tools-m3u8_V1.25.91.zip "$WP:/tmp/provider.zip"
cli theme activate vf-tools-theme >/dev/null
cli plugin install /tmp/provider.zip --activate >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/seed.php "$WP:/tmp/seed.php"
cli eval-file /tmp/seed.php > proof/seed.json
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/urls.php "$WP:/tmp/urls.php"
cli eval-file /tmp/urls.php > proof/seed.json
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/template-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/s01-template-fixture.php"
docker cp lane/state.php "$WP:/tmp/state.php"
cli eval-file /tmp/state.php > proof/state-before.json
node lane/reading-browser.cjs baseline
docker cp target/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
node lane/reading-browser.cjs candidate
cli eval-file /tmp/state.php > proof/state-after.json
cmp proof/state-before.json proof/state-after.json
docker cp baseline/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
node lane/reading-browser.cjs rollback
cli eval-file /tmp/state.php > proof/state-rollback.json
cmp proof/state-before.json proof/state-rollback.json
python3 - <<'PYFINAL'
import json,os,pathlib
p=pathlib.Path('proof')
e={'status':'PASS','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'base_sha':os.environ['BASE_SHA'],'production':'NOT_EXECUTED','mobile':'NOT_RUN_OWNER_DEFERRED','formal_release':'NOT_EXECUTED','provider':'UNCHANGED_1.25.91','canonical_content_and_layout':'PRESERVED','checks':{x:json.loads((p/(x+'.json')).read_text())['status'] for x in ['native-functions','reading-baseline','reading-candidate','reading-rollback']}}
assert all(v=='PASS' for v in e['checks'].values())
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(e,indent=2))
print('SAFE_FINAL',json.dumps(e))
PYFINAL
