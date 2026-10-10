#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-embed78-${GITHUB_RUN_ID}";DB="$NET-db";export WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -e CANDIDATE_VERSION="$TARGET_VERSION" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e SOURCE_VERSION="$SOURCE_VERSION" -e TARGET_VERSION="$TARGET_VERSION" -e CANDIDATE_VERSION="$TARGET_VERSION" -e VF_PHASE="${VF_PHASE:-}" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Embed Integration' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "provider/vf-tools-theme_V${THEME_VERSION}.zip" "$WP:/tmp/theme.zip"
cli theme install /tmp/theme.zip --activate >/dev/null
docker cp "provider/vf-tools-m3u8_V${SOURCE_VERSION}.zip" "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
cli plugin install polylang --version="$POLYLANG_VERSION" --activate >/dev/null
docker cp lane/seed.php "$WP:/tmp/seed.php";cli eval-file /tmp/seed.php >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
cli eval 'echo wp_json_encode(["settings"=>vf_tool_m3u8_get_settings(),"engine"=>vf_tool_m3u8_engine_frontend_config()]);' > proof/engine-config.json
node lane/browser.js baseline
docker cp "proof/vf-tools-m3u8_V${TARGET_VERSION}.zip" "$WP:/tmp/candidate.zip"
docker cp proof/synthetic-channel.json "$WP:/tmp/synthetic-channel.json"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp lane/mock-update.php "$WP:/var/www/html/wp-content/mu-plugins/synthetic-update-transport.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/mu-plugins
docker cp lane/phase.php "$WP:/tmp/native-phase.php"
VF_PHASE=seed cli eval-file /tmp/native-phase.php > proof/native-baseline.json
VF_PHASE=negative cli eval-file /tmp/native-phase.php > proof/native-corrupt-negative.json
VF_PHASE=upgrade cli eval-file /tmp/native-phase.php > proof/native-upgrade.json
VF_PHASE=candidate cli eval-file /tmp/native-phase.php > proof/native-candidate.json
node lane/browser.js candidate
VF_PHASE=restore cli eval-file /tmp/native-phase.php > proof/native-source-recovery.json
VF_PHASE=rollback cli eval-file /tmp/native-phase.php > proof/native-rollback.json
node lane/browser.js rollback
VF_PHASE=reapply cli eval-file /tmp/native-phase.php > proof/native-reapply.json
VF_PHASE=candidate cli eval-file /tmp/native-phase.php > proof/native-reapply-readback.json
node lane/browser.js reapply
python3 - <<'PY'
import pathlib,json,os
p=pathlib.Path('proof');identity=json.loads((p/'identity.json').read_text())
names=['native-baseline','native-corrupt-negative','native-upgrade','native-candidate','native-source-recovery','native-rollback','native-reapply','native-reapply-readback','embed-candidate','embed-reapply']
checks={n:json.loads((p/(n+'.json')).read_text())['status'] for n in names}
baseline=json.loads((p/'baseline-direct.json').read_text())['direct'];rollback=json.loads((p/'rollback-direct.json').read_text())['direct']
reproduced=baseline.get('endpoint')!='1' and rollback.get('endpoint')!='1'
result={**identity,'status':'PASS' if all(x=='PASS' for x in checks.values()) and reproduced else 'FAIL','checks':checks,'old_version_failure_reproduced':reproduced,'production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID']}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));assert result['status']=='PASS'
PY
