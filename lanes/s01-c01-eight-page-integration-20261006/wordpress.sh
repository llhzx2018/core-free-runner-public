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
docker cp lane/seed.php "$WP:/tmp/integration-seed.php"
seed(){ cli eval-file /tmp/integration-seed.php > proof/seed.json; }
seed
run_check(){
 local key="$1";mkdir -p "checks/$key/proof";ln -sfn ../../lane "checks/$key/lane"
 echo "CHECK_BEGIN=$key"
 if (cd "checks/$key" && node "$TASK_ROOT/lane/$key.js");then code=0;else code=$?;fi
 mkdir -p "proof/$key";cp -a "checks/$key/proof/." "proof/$key/"
 echo "CHECK_END=$key code=$code";return "$code"
}
run_check overview
seed
run_check brand
run_check layout
run_check navigation
mkdir -p checks/render/proof;ln -sfn ../../lane checks/render/lane
(cd checks/render && node "$TASK_ROOT/lane/same-source-reference.js" render)
run_check render
mkdir -p checks/seo/proof;ln -sfn ../../lane checks/seo/lane
(cd checks/seo && node "$TASK_ROOT/lane/same-source-reference.js" seo)
run_check seo
(cd checks/seo && node "$TASK_ROOT/lane/seo-public-output.js")
cli plugin install polylang --activate >/dev/null
docker cp lane/polylang-seed.php "$WP:/tmp/polylang-seed.php";cli eval-file /tmp/polylang-seed.php >/dev/null
(cd checks/seo && node "$TASK_ROOT/lane/seo-paired-output.js")
cli plugin deactivate polylang >/dev/null
cp -a checks/seo/proof/. proof/seo/
seed
run_check preview
run_check recovery
docker cp target/tests/recovery-data-wordpress-check.php "$WP:/tmp/recovery-data-check.php"
cli eval-file /tmp/recovery-data-check.php > proof/recovery-data.json
seed
run_check integration
python3 - <<'PY'
import json,pathlib,os
p=pathlib.Path('proof');identity=json.loads((p/'identity.json').read_text());pages={}
for name in ['overview','brand','layout','navigation','render','seo','preview','recovery']:
 d=json.loads((p/name/'live-browser.json').read_text());assert d['status']=='PASS',name
 assert len(d['checks'])==6 and all(x.get('status','PASS')=='PASS' for x in d['checks']),name
 pages[name]={'status':'PASS','widths':6,'checks':len(d.get('tests',d.get('functional',{}))),'context_count':len(d.get('contexts',[]))}
for name in ['public-output','paired-output']:assert json.loads((p/'seo'/f'{name}.json').read_text())['status']=='PASS'
recovery=json.loads((p/'recovery-data.json').read_text());assert recovery['status']=='PASS' and all(v=='PASS' for v in recovery['checks'].values())
chain=json.loads((p/'integration'/'integration.json').read_text());assert chain['status']=='PASS'
inventory=json.loads(pathlib.Path('lane/inventory.json').read_text());assert len(inventory['canonical'])==8
result={**identity,'status':'PASS','scope':'Theme eight canonical pages plus their declared UI states and frontend/cross-page integration in one synthetic WordPress database','pages':pages,'canonical_page_count':8,'layout_context_count':20,'cross_page_cases':len(chain['cases']),'data_checks':len(recovery['checks']),'production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','real_provider_domain':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID']}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2));(p/'surface-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2));print('VF_INTEGRATION_FINAL_BEGIN');print(json.dumps(result));print('VF_INTEGRATION_FINAL_END')
PY
