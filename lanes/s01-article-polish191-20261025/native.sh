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
docker cp "provider/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/clean-theme.zip"
cli theme install /tmp/clean-theme.zip >/dev/null
docker cp provider/vf-tools-m3u8_V1.25.94.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/progress-fixture.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
cli theme activate vf-tools-theme >/dev/null
for attempt in 1 2 3; do cli plugin install polylang --version=3.8.10 --activate >/dev/null && break; test "$attempt" -lt 3 || exit 1; sleep 3; done
docker cp lane/languages.php "$WP:/tmp/languages.php";cli eval-file /tmp/languages.php >/dev/null
# Only initialize the existing admin capability; do not repeat unrelated review-service suites.
cli user add-cap admin vf_manage_theme_profile >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php";cli eval-file /tmp/mount-seed.php > proof/mounts.json
docker cp "control/lanes/$LANE_ID/seed.php" "$WP:/tmp/extra-protected.php";cli eval-file /tmp/extra-protected.php >/dev/null
docker cp target/tests/article-reference-seed.php "$WP:/tmp/seed-blog.php";cli eval-file /tmp/seed-blog.php > proof/article-fixtures.json
docker cp target/tests/article-reference-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/article-review-fixture.php"

docker cp "control/lanes/$LANE_ID/adjacent-seed.php" "$WP:/tmp/adjacent-seed.php";cli eval-file /tmp/adjacent-seed.php >/dev/null
docker cp lane/snapshot.php "$WP:/tmp/snapshot.php"
# Warm only public read-only boot paths before protected-state comparison.
curl -fsS http://127.0.0.1:18880/ >/dev/null
curl -fsS http://127.0.0.1:18880/m3u8-playlist-checker/ >/dev/null
cli eval-file /tmp/snapshot.php > proof/bootstrap-before.json
cli option get vf_theme_layout --format=json > proof/bootstrap-layout-before.json
node lane/warm-admin.cjs
cli eval-file /tmp/snapshot.php > proof/bootstrap-after.json
cli option get vf_theme_layout --format=json > proof/bootstrap-layout-after.json
python3 - <<'PYBOOT'
import json,pathlib
r=pathlib.Path('proof');a=json.loads((r/'bootstrap-before.json').read_text());b=json.loads((r/'bootstrap-after.json').read_text());changed=[k for k in a['sections']if a['sections'][k]!=b['sections'][k]]
assert set(changed)<= {'vf_theme_brand','vf_theme_tokens','vf_theme_navigation','vf_theme_layout'}
created=[k for k in changed if k!='vf_theme_layout']
assert all(not a['option_presence'][k]and b['option_presence'][k]for k in created)
# This fixture deliberately seeds a partial layout on a new installation.
# Existing install-migration fills missing fields on first privileged admin visit.
# Verify every authored leaf survives; never waive mutation of an existing value.
x=json.loads((r/'bootstrap-layout-before.json').read_text());y=json.loads((r/'bootstrap-layout-after.json').read_text())
def preserved(before,after,path='layout'):
    if isinstance(before,dict):
        assert isinstance(after,dict),path
        for k,v in before.items():
            assert k in after,path+'.'+k
            preserved(v,after[k],path+'.'+k)
    else: assert before==after,(path,before,after)
preserved(x,y)
assert len(y['modules'])==20 and len(y['templates'])==20

(r/'bootstrap.json').write_text(json.dumps({'status':'PASS','created_missing_options':created,'partial_layout_initialization':'ALL_AUTHORED_LEAVES_PRESERVED_20_CONTEXTS','other_existing_protected_records':'BYTE_IDENTICAL','scope':'fresh isolated installation initialization before review baseline'}))
PYBOOT
# Activate the SEO integration after clean admin intake, before all Head/lifecycle baselines.
for attempt in 1 2 3; do cli plugin install seo-by-rank-math --version=1.0.280 --activate >/dev/null && break; test "$attempt" -lt 3 || exit 1; sleep 3; done
# Match the plugin's documented account-connection skip in this isolated fixture.
cli option update rank_math_registration_skip 1 >/dev/null
curl -fsS http://127.0.0.1:18880/m3u8-player/ >/dev/null
# Install the public-only ad double after clean admin initialization.
docker cp target/tests/article-ad-layout-fixture.php "$WP:/var/www/html/wp-content/mu-plugins/article-ad-review-fixture.php"
cli eval-file /tmp/snapshot.php > proof/state-before.sha256
docker cp "control/lanes/$LANE_ID/contracts-snapshot.php" "$WP:/tmp/contracts-snapshot.php"
cli eval-file /tmp/contracts-snapshot.php > proof/contracts-before.json
docker cp "provider/vf-tools-theme_V$SOURCE_VERSION.zip" "$WP:/tmp/theme-old.zip"
docker cp "provider/vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/theme-new.zip"
version_check(){ test "$(cli theme get vf-tools-theme --field=version)" = "$1"; test "$(cli plugin get vf-tool-m3u8 --field=version)" = "1.25.94"; echo INSTALLED_VERSION_PASS="$1"; }
version_check "$TARGET_VERSION"
cli theme install /tmp/theme-old.zip --force >/dev/null
version_check "$SOURCE_VERSION"
NODE_PATH="$PWD/node_modules" node target/tests/article-polish-browser-check.cjs --phase=before
cli theme install /tmp/theme-new.zip --force >/dev/null
version_check "$TARGET_VERSION"
NODE_PATH="$PWD/node_modules" node target/tests/article-polish-browser-check.cjs --phase=after
cli theme install /tmp/theme-old.zip --force >/dev/null
version_check "$SOURCE_VERSION"
NODE_PATH="$PWD/node_modules" node target/tests/article-polish-browser-check.cjs --phase=smoke
cli theme install /tmp/theme-new.zip --force >/dev/null
version_check "$TARGET_VERSION"
cli theme install /tmp/theme-new.zip --force >/dev/null
version_check "$TARGET_VERSION"
cli eval-file /tmp/snapshot.php > proof/state-after.sha256
cmp proof/state-before.sha256 proof/state-after.sha256
cli eval-file /tmp/contracts-snapshot.php > proof/contracts-after.json
cmp proof/contracts-before.json proof/contracts-after.json
echo ARTICLE_POLISH_UPGRADE_ROLLBACK_REPEAT_PROTECTED_DATA_PASS
