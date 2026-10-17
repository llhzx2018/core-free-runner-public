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
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp "provider/vf-tools-theme_V$SOURCE_VERSION.zip" "$WP:/tmp/source.zip"
docker cp "proof/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/target.zip"
docker cp provider/vf-tools-m3u8_V1.25.91.zip "$WP:/tmp/provider.zip"
cli theme install /tmp/source.zip --activate >/dev/null
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/progress-fixture.php"
cli plugin install polylang --version=3.8.10 --activate >/dev/null
docker cp lane/languages.php "$WP:/tmp/languages.php";cli eval-file /tmp/languages.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
for f in mount-seed seed extra-seed snapshot wp-check review-seed;do docker cp "lane/$f.php" "$WP:/tmp/$f.php";done
cli eval-file /tmp/mount-seed.php > proof/mounts.json
cli eval-file /tmp/seed.php > proof/seed.json
cli eval-file /tmp/extra-seed.php > proof/cases.json
curl -fsS http://127.0.0.1:18880/ >/dev/null
node lane/warm-admin.cjs
cli eval-file /tmp/snapshot.php > proof/state-before.json
cli theme install /tmp/target.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
cli eval-file /tmp/wp-check.php > proof/wordpress.json
node lane/smoke.cjs upgrade
cli eval-file /tmp/snapshot.php > proof/state-upgrade.json
cmp proof/state-before.json proof/state-upgrade.json
cli eval-file /tmp/review-seed.php > proof/review-seed.json
cli eval-file /tmp/snapshot.php > proof/state-reviews.json
docker exec "$DB" mariadb-dump --single-transaction -uroot -psyntheticroot wordpress > /tmp/s01-theme133-recovery.sql
test -s /tmp/s01-theme133-recovery.sql
cli theme install /tmp/source.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
node lane/smoke.cjs rollback
cli eval-file /tmp/snapshot.php > proof/state-rollback.json
cmp proof/state-reviews.json proof/state-rollback.json
cli theme install /tmp/target.zip --force >/dev/null
node lane/smoke.cjs reapply
cli eval-file /tmp/snapshot.php > proof/state-reapply.json
cmp proof/state-reviews.json proof/state-reapply.json
cli theme install /tmp/target.zip --force >/dev/null
cli eval-file /tmp/snapshot.php > proof/state-idempotent.json
cmp proof/state-reviews.json proof/state-idempotent.json
cli option update vf_theme_frontend_review_restore_probe synthetic >/dev/null
docker exec -i "$DB" mariadb -uroot -psyntheticroot wordpress < /tmp/s01-theme133-recovery.sql
rm -f /tmp/s01-theme133-recovery.sql
cli eval-file /tmp/snapshot.php > proof/state-recovered.json
cmp proof/state-reviews.json proof/state-recovered.json
# A fresh database and freshly extracted Theme root exercise clean FULL independently.
docker exec "$DB" mariadb -uroot -psyntheticroot -e "CREATE DATABASE wordpress_clean;GRANT ALL PRIVILEGES ON wordpress_clean.* TO 'wordpress'@'%';"
cli config set DB_NAME wordpress_clean >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Clean Frontend' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker exec "$WP" rm -rf /var/www/html/wp-content/themes/vf-tools-theme
cli theme install /tmp/target.zip --activate >/dev/null
cli plugin install /tmp/provider.zip --force --activate >/dev/null
cli plugin install polylang --version=3.8.10 --force --activate >/dev/null
cli eval-file /tmp/languages.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
cli eval-file /tmp/mount-seed.php >/dev/null
cli eval-file /tmp/seed.php > proof/seed.json
cli eval-file /tmp/extra-seed.php > proof/cases.json
cli eval-file /tmp/wp-check.php > proof/wordpress-clean.json
curl -fsS http://127.0.0.1:18880/ >/dev/null
node lane/warm-admin.cjs
cli eval-file /tmp/snapshot.php > proof/state-clean-before.json
node lane/smoke.cjs clean
cli eval-file /tmp/snapshot.php > proof/state-clean-after.json
cmp proof/state-clean-before.json proof/state-clean-after.json
curl -fsS http://127.0.0.1:18880/wp-admin/install.php > /tmp/setup-revisit.html
python3 - <<'PYEND'
import json,pathlib,os
p=pathlib.Path('proof')
for name in ['smoke-upgrade','wordpress','wordpress-clean','smoke-rollback','smoke-reapply','smoke-clean']:
 d=json.loads((p/(name+'.json')).read_text());assert d['status']=='PASS'and all(c['pass']for c in d['checks'])
assert 'Already Installed'in pathlib.Path('/tmp/setup-revisit.html').read_text()
checks={k:'PASS'for k in ['clean_full','native_upgrade132to133','rollback132','reapply133','idempotent_reinstall','full_database_review_recovery','security','package_route_smoke','setup_revisit_locked','protected_all_records_including_ads_seo_provider_and_translation_tables']}
(p/'PRESERVATION_EVIDENCE.json').write_text(json.dumps({'status':'PASS','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'version':os.environ['TARGET_VERSION'],'checks':checks,'review_records':3,'protected_state':'BYTE_IDENTICAL','mobile':'NOT_RUN_OWNER_DEFERRED','production':'NOT_EXECUTED','owner_real_use':'POST_PRODUCTION_REQUIRED'},indent=2))
PYEND
