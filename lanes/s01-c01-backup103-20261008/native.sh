#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-backup-${GITHUB_RUN_ID}"; DB="$NET-db"; export WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; rm -rf /tmp/backup-theme.zip /tmp/backup-provider.zip /tmp/backup-wp-cli.phar; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/backup-wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/backup-wp-cli.phar "$WP:/usr/local/bin/wp"
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Theme Backup Verification' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp provider/theme.zip "$WP:/tmp/theme.zip"
cli theme install /tmp/theme.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
docker cp provider/provider.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$PROVIDER_VERSION"
docker cp lane/seed.php "$WP:/tmp/seed.php"
cli eval-file /tmp/seed.php > proof/seed.json
python3 - <<'PY'
import json,pathlib
assert json.loads(pathlib.Path('proof/seed.json').read_text())['consumer_ok'] is True
PY
cli eval 'echo wp_json_encode(VF_Theme_Runtime_Authority_V1::snapshot(get_template_directory()));' > proof/installed-runtime.json
cli eval 'echo wp_json_encode(["status"=>"PASS","wordpress"=>get_bloginfo("version"),"theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION]);' > proof/installed-versions.json
python3 - <<'PY'
import json,pathlib,os
r=json.loads(pathlib.Path('proof/installed-runtime.json').read_text());assert r['file_count']==467 and r['fingerprint_sha256']==os.environ['RUNTIME_FINGERPRINT']
PY
node lane/browser.js
docker cp target/tests/recovery-data-wordpress-check.php "$WP:/tmp/recovery-data.php"
cli eval-file /tmp/recovery-data.php > proof/backup-state-wordpress.json
python3 - <<'PY'
import json,pathlib,os
p=pathlib.Path('proof')
files=['backup-controls.json','backup-request-failures.json','backup-workflow.json','backup-browser-errors.json','backup-state-wordpress.json','installed-versions.json']
for f in files:assert json.loads((p/f).read_text())['status']=='PASS',f
controls=json.loads((p/'backup-controls.json').read_text());assert [r['width'] for r in controls['rows']]==[1920,1440,1319,1024,768,390]
r={'status':'PASS','scope':'THM-BACKUP-001','version':os.environ['TARGET_VERSION'],'source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'formal_source_sha':os.environ['FORMAL_SHA'],'asset_bytes':int(os.environ['ASSET_BYTES']),'asset_sha256':os.environ['ASSET_SHA256'],'runtime_files':467,'runtime_fingerprint':os.environ['RUNTIME_FINGERPRINT'],'controls_widths':6,'workflow_cases':len(json.loads((p/'backup-workflow.json').read_text())['cases']),'state_checks':len(json.loads((p/'backup-state-wordpress.json').read_text())['checks']),'production':'NOT_EXECUTED','owner_real_use':'NOT_INFERRED_FROM_SCREENSHOT','source_change':'NONE'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(r,indent=2))
PY
