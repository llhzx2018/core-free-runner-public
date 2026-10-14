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
docker exec "$WP" sh -c 'echo "opcache.enable=0" > /usr/local/etc/php/conf.d/s01-reading-no-opcache.ini;apachectl graceful' >/dev/null
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic S01 Tool Regression' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "proof/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/target.zip"
docker cp "provider/vf-tools-theme_V$SOURCE_VERSION.zip" "$WP:/tmp/source.zip"
docker cp "provider/vf-tools-m3u8_V$M3_VERSION.zip" "$WP:/tmp/provider.zip"
docker cp lane/seed.php "$WP:/tmp/seed.php"
docker cp lane/reading-seed.php "$WP:/tmp/reading-seed.php"
docker cp lane/reading-urls.php "$WP:/tmp/reading-urls.php"
docker cp lane/reading-state.php "$WP:/tmp/reading-state.php"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/reading-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/s01-reading-fixture.php"
cli theme install /tmp/source.zip --activate >/dev/null
cli plugin install /tmp/provider.zip --activate >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
seed(){ cli eval-file /tmp/seed.php >/dev/null;cli rewrite structure '/%postname%/' --hard >/dev/null;cli eval-file /tmp/reading-seed.php >/dev/null;cli eval-file /tmp/reading-urls.php > proof/reading-seed.json; }
seed
cli eval 'set_theme_mod("s01_synthetic_keep","retained");' >/dev/null
cli eval-file /tmp/reading-state.php > proof/state-before.json
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
node lane/catalogue-browser.cjs baseline
cli theme install /tmp/target.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
node lane/catalogue-browser.cjs candidate
cli eval-file /tmp/reading-state.php > proof/state-candidate.json
cmp proof/state-before.json proof/state-candidate.json
cli theme install /tmp/source.zip --force >/dev/null
node lane/catalogue-browser.cjs rollback
cli eval-file /tmp/reading-state.php > proof/state-rollback.json
cmp proof/state-before.json proof/state-rollback.json
cli theme install /tmp/target.zip --force >/dev/null
node lane/catalogue-browser.cjs reapply
cli eval-file /tmp/reading-state.php > proof/state-reapply.json
cmp proof/state-before.json proof/state-reapply.json
cli theme install /tmp/target.zip --force >/dev/null
cli eval-file /tmp/reading-state.php > proof/state-idempotent.json
cmp proof/state-before.json proof/state-idempotent.json
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic S01 Clean Catalogue' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli theme install /tmp/target.zip --force --activate >/dev/null
cli plugin install /tmp/provider.zip --force --activate >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
seed
node lane/catalogue-browser.cjs clean
cli eval 'if(wp_get_theme()->get("Version")!=="1.35.118"||VF_TOOL_M3U8_VERSION!=="1.25.91")throw new Exception("installed version mismatch");echo wp_json_encode(["status"=>"PASS","theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION]);' > proof/clean-installed.json
python3 - <<'PYFINAL'
import json,os,pathlib
p=pathlib.Path('proof');checks={n:json.loads((p/(n+'.json')).read_text())['status'] for n in ['copy-zh','copy-en','directory-provider','heading','reading-functions','catalogue-baseline','catalogue-candidate','catalogue-rollback','catalogue-reapply','catalogue-clean','clean-installed']}
assert all(v=='PASS' for v in checks.values())
before=(p/'state-before.json').read_bytes()
assert all((p/('state-'+n+'.json')).read_bytes()==before for n in ['candidate','rollback','reapply','idempotent'])
e={'status':'PASS','theme_source_sha':os.environ['TARGET_SHA'],'theme_source_tree':os.environ['TARGET_TREE'],'theme_version':os.environ['TARGET_VERSION'],'m3_source_sha':os.environ['M3_SHA'],'m3_source_tree':os.environ['M3_TREE'],'checks':checks,'canonical_content_and_layout':'PRESERVED','production':'NOT_EXECUTED','mobile':'NOT_RUN_OWNER_DEFERRED','owner_real_use':'POST_PRODUCTION_REQUIRED','frozen_header_menu_footer':'PRESERVED','unchanged_provider':'1.25.91'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(e,indent=2));print('SAFE_FINAL',json.dumps(e))
PYFINAL
