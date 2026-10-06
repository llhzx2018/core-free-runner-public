#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-v8-${GITHUB_RUN_ID}";DB="$NET-db";export WP="$NET-wp"
TASK_ROOT="$PWD"
cleanup(){ docker rm -f "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e TARGET_VERSION="$TARGET_VERSION" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Theme Integration' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "proof/vf-tools-theme_V${TARGET_VERSION}.zip" "$WP:/tmp/theme.zip"
cli theme install /tmp/theme.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/vf-render-fixture.php"
docker cp lane/vf-render-fixture.js "$WP:/var/www/html/wp-content/mu-plugins/vf-render-fixture.js"
docker cp lane/vf-render-module.js "$WP:/var/www/html/wp-content/mu-plugins/vf-render-module.js"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/mu-plugins
docker cp lane/seed.php "$WP:/tmp/integration-seed.php"
seed(){ cli eval-file /tmp/integration-seed.php > proof/seed.json; }
seed
run_check(){
 local key="$1";mkdir -p "checks/$key/proof";ln -sfn ../../lane "checks/$key/lane"
 echo "CHECK_BEGIN=$key"
 if (cd "checks/$key" && node "$TASK_ROOT/lane/$key.js");then code=0;else code=$?;fi
 mkdir -p "proof/$key";cp -a "checks/$key/proof/." "proof/$key/"
 echo "CHECK_END=$key code=$code";printf "%s %s\n" "$key" "$code" >> proof/check-exit-codes.txt;return "$code"
}
run_check integration
python3 - <<'PYFINAL'
import json,pathlib,os
p=pathlib.Path('proof');identity=json.loads((p/'identity.json').read_text());chain=json.loads((p/'integration/integration.json').read_text());assert chain['status']=='PASS'
result={**identity,'status':'PASS','scope':'continuous cross-page UI saves actual frontend and recovery in one synthetic WordPress database','canonical_reachable':8,'cross_page_cases':len(chain['cases']),'run_id':os.environ['GITHUB_RUN_ID'],'page_control_suite':'SEPARATE_EXACT_SOURCE_RUN','production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2));print('VF_CHAIN_FINAL_BEGIN');print(json.dumps(result));print('VF_CHAIN_FINAL_END')
PYFINAL
