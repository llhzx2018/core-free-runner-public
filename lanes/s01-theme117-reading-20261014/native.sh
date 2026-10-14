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
docker cp "proof/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/theme107.zip"
docker cp "proof/vf-tools-m3u8_V$M3_VERSION.zip" "$WP:/tmp/m379.zip"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/route-trace.php "$WP:/var/www/html/wp-content/mu-plugins/s01-route-trace.php"
docker cp lane/seed.php "$WP:/tmp/seed.php"
cli theme install /tmp/theme107.zip --activate --force >/dev/null
cli plugin install /tmp/m379.zip --activate --force >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
cli eval-file /tmp/seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php"
cli eval-file /tmp/mount-seed.php > proof/mount-seed-${TARGET_VERSION}.json
docker cp lane/template-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/s01-template-fixture.php"
docker cp lane/template-seed.php "$WP:/tmp/template-seed.php"
cli eval-file /tmp/template-seed.php > proof/template-seed.json
docker cp lane/reading-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/s01-reading-fixture.php"
docker cp lane/reading-seed.php "$WP:/tmp/reading-seed.php"
docker cp lane/reading-urls.php "$WP:/tmp/reading-urls.php"
docker cp lane/reading-state.php "$WP:/tmp/reading-state.php"
cli eval-file /tmp/reading-seed.php >/dev/null
cli eval-file /tmp/reading-urls.php > proof/reading-seed.json

test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_VERSION"
node lane/template-browser.js clean
node lane/reading-browser.cjs clean
cli plugin activate vf-tool-m3u8 >/dev/null
cli eval 'echo wp_json_encode(["status"=>"PASS","theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION]);' > proof/clean-installed.json
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path('proof')
targets=['native-functions','reading-baseline','reading-candidate','reading-rollback','reading-reapply','reading-clean','desktop','public-template-baseline','public-detail-heading','public-template-css','template-candidate','template-reapply','template-clean','next-route-en','next-route-zh','three-tool-recovery','browser-stream-i18n-php','embed-alias-php','attribute-php','state-upgrade','state-rollback','state-reapply','tools-candidate','tools-reapply','tools-clean','clean-installed','state-idempotent']
states={n:json.loads((p/(n+'.json')).read_text())['status'] for n in targets}
assert all(v=='PASS' for v in states.values()),states
e={'status':'PASS','theme_source_sha':os.environ['TARGET_SHA'],'theme_source_tree':os.environ['TARGET_TREE'],'m3_source_sha':os.environ['M3_SHA'],'m3_source_tree':os.environ['M3_TREE'],'theme_version':os.environ['TARGET_VERSION'],'m3_version':os.environ['M3_VERSION'],'checks':states,'canonical_content_and_layout':'PRESERVED','resumed_from_run':38545197983,'resume_basis':'FIRST_FOUR_LIFECYCLE_PHASES_AND_TOOLS_PRESERVED_VERIFIED_PRIOR_ARTIFACT; CLEAN_RETESTED_WITH_MODULE_IDENTITY_ORDER','production':'NOT_EXECUTED','owner_product_pass':'PENDING','mobile':'NOT_RUN_OWNER_DEFERRED','provider_companion':'UNCHANGED_1.25.91'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(e,sort_keys=True,indent=2))
print('SAFE_FINAL',json.dumps(e,sort_keys=True))
PY
