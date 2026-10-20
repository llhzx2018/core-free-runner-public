#!/usr/bin/env bash
set -Eeuo pipefail
DB=s01-admin-release-db;WP=s01-admin-release-wp
cleanup(){ docker rm -f "$WP" "$DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$DB" -e MARIADB_ROOT_PASSWORD=synthetic -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wp -e MARIADB_PASSWORD=synthetic mariadb:11.8.8 >/dev/null
docker run -d --name "$WP" --link "$DB":db -p 18880:80 -e WORDPRESS_DB_HOST=db -e WORDPRESS_DB_USER=wp -e WORDPRESS_DB_PASSWORD=synthetic -e WORDPRESS_DB_NAME=wordpress wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 80);do docker exec "$DB" mariadb-admin ping -uroot -psynthetic --silent >/dev/null 2>&1 && break;sleep 2;done
curl -fsSLo wp.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp wp.phar "$WP:/usr/local/bin/wp"
for i in $(seq 1 80);do docker exec "$WP" sh -c 'test -s /var/www/html/wp-config.php && grep -q "wp-settings.php" /var/www/html/wp-config.php' >/dev/null 2>&1 && break;sleep 2;done
docker exec "$WP" sh -c 'echo "opcache.enable=0" > /usr/local/etc/php/conf.d/release-check.ini;apachectl graceful' >/dev/null
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title=Synthetic --admin_user=admin --admin_password=Synthetic-Only-Update-54! --admin_email=test@example.invalid --skip-email >/dev/null
docker cp "vf-tools-theme_V$SOURCE_VERSION.zip" "$WP:/tmp/old.zip"
docker cp "vf-tools-theme_V$TARGET_VERSION.zip" "$WP:/tmp/new.zip"
docker cp control/lanes/s01-admin-navigation-20261019/release143-snapshot.php "$WP:/tmp/snapshot.php"
cli theme install /tmp/new.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
test "$(cli eval 'echo vf_theme_runtime_version();')" = "$TARGET_VERSION"
base='http://127.0.0.1:18880'
admin="$base/wp-admin/themes.php?page=vf-theme-modules&tab=layout"
curl -fsS "$base/" > /tmp/s01-public.html
curl -fsS "$base/wp-admin/install.php" > /tmp/s01-setup.html
grep -q 'Already Installed' /tmp/s01-setup.html
curl -fsS -c /tmp/s01-cookie "$base/wp-login.php" >/dev/null
curl -fsS -b /tmp/s01-cookie -c /tmp/s01-cookie --data-urlencode log=admin --data-urlencode 'pwd=Synthetic-Only-Update-54!' --data-urlencode "redirect_to=$admin" --data-urlencode testcookie=1 "$base/wp-login.php" >/dev/null
curl -fsS -b /tmp/s01-cookie "$admin" > /tmp/s01-admin.html
grep -q 'data-vf-frontend-pages' /tmp/s01-admin.html
test "$(grep -o 'data-vf-page-context=' /tmp/s01-admin.html | wc -l)" = 20
curl -sS -o /dev/null -w '%{http_code}' "$admin" | grep -qx 302
echo 'CLEAN_INSTALL_FIRST_REQUEST_ADMIN_LOGIN_SETUP_LOCK_AUTH_BOUNDARY=PASS'
cli theme install /tmp/old.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
cli option update s01_preserve_fixture 'original-synthetic-data' >/dev/null
cli option update vf_theme_frontend_review_release_fixture '{"schema":1,"note":"synthetic review record"}' >/dev/null
cli post create --post_type=post --post_status=publish --post_title='Synthetic preserved article' --post_content='Synthetic body must survive upgrade and rollback' >/dev/null
cli term create category SyntheticPreserved --slug=synthetic-preserved >/dev/null
curl -fsS -b /tmp/s01-cookie "$admin" >/dev/null
cli eval-file /tmp/snapshot.php > proof/data-before.json
for step in upgrade rollback reapply idempotent;do
 if [ "$step" = rollback ];then package=/tmp/old.zip;expected="$SOURCE_VERSION";else package=/tmp/new.zip;expected="$TARGET_VERSION";fi
 cli theme install "$package" --force >/dev/null
 test "$(cli theme get vf-tools-theme --field=version)" = "$expected"
 curl -fsS -b /tmp/s01-cookie "$admin" > /tmp/s01-admin.html
 grep -q 'data-vf-frontend-pages' /tmp/s01-admin.html
 cli eval-file /tmp/snapshot.php > "proof/data-$step.json"
 if ! cmp proof/data-before.json "proof/data-$step.json";then diff -u proof/data-before.json "proof/data-$step.json";exit 1;fi
 echo "NATIVE_THEME_${step}_DATA_PRESERVED=PASS"
done
python3 - <<'PY'
import json,os
json.dump({'status':'PASS','source':os.environ['TARGET_SHA'],'from':os.environ['SOURCE_VERSION'],'target':os.environ['TARGET_VERSION'],'clean_install':'PASS','first_http_and_admin_login':'PASS','setup_revisit_locked':'PASS','anonymous_admin_denied':'PASS','upgrade':'PASS','rollback':'PASS','reapply':'PASS','idempotency':'PASS','preserved':'Theme options/mods, synthetic manual review record, full posts/meta and taxonomy rows','production':'UNTOUCHED'},open('proof/upgrade-receipt.json','w'),indent=2)
PY
