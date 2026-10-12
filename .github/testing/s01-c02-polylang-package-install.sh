#!/usr/bin/env bash
set -Eeuo pipefail
test -n "$GITHUB_RUN_ID" && test -n "$RUNNER_TEMP"
BUNDLE_DIR="$RUNNER_TEMP/s01-build"
test -f "$BUNDLE_DIR/first.zip"
test -f "$BUNDLE_DIR/vf-tools-ops_V1.21.1096.zip"
test -f "$BUNDLE_DIR/install-contract.json"
NETWORK="vf-s01-install-$GITHUB_RUN_ID"
DB="$NETWORK-db"
WP="$NETWORK-wp"
cleanup(){
 docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true
 docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$NETWORK" >/dev/null
docker run -d --name "$DB" --network "$NETWORK" \
 -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress \
 -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for _ in $(seq 1 60); do
 if docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1;then break;fi
 sleep 2
done
docker run -d --name "$WP" --network "$NETWORK" -p 127.0.0.1:18884:80 -p 127.0.0.1:80:80 \
 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress \
 -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb \
 wordpress:7.1.2-php8.3-apache >/dev/null
for _ in $(seq 1 90); do
 if docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18884/wp-admin/install.php >/dev/null;then break;fi
 sleep 2
done
test -f /tmp/s01-pll-wp-cli.phar
docker cp /tmp/s01-pll-wp-cli.phar "$WP:/usr/local/bin/wp"
docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18884 --title='S01 Synthetic Package Lifecycle' \
 --admin_user=admin --admin_password='S01-Synthetic-Install-Only!' \
 --admin_email=runner@example.invalid --skip-email >/dev/null
cli plugin install polylang --activate >/dev/null
cli option update home "http://$WP" >/dev/null
cli option update siteurl "http://$WP" >/dev/null
cli rewrite structure '/%postname%/' >/dev/null
cli rewrite flush --hard >/dev/null
docker cp runner/.github/testing/s01-c02-polylang-package-install.php "$WP:/tmp/s01-install.php"
docker cp "$BUNDLE_DIR/install-contract.json" "$WP:/tmp/s01-install-contract.json"
docker cp "$BUNDLE_DIR/vf-tools-ops_V1.21.1096.zip" "$WP:/tmp/s01-baseline.zip"
docker cp "$BUNDLE_DIR/first.zip" "$WP:/tmp/s01-candidate.zip"
cli eval-file /tmp/s01-install.php setup > /tmp/s01-install-setup.log
cli plugin install /tmp/s01-baseline.zip --activate > /tmp/s01-baseline-install.log
cli plugin is-active vf-ops >/dev/null
cli eval-file /tmp/s01-install.php baseline > /tmp/s01-baseline-readback.log
cli plugin install /tmp/s01-candidate.zip --force --activate > /tmp/s01-candidate-install.log
cli plugin is-active vf-ops >/dev/null
cli eval-file /tmp/s01-install.php candidate > /tmp/s01-candidate-readback.log
# Test host exists only in this disposable WP filesystem.
cli user update s01-synthetic-editor --user_pass='S01-Synthetic-Editor-Only!' >/dev/null
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
docker cp runner/.github/testing/s01-c02-polylang-browser-host.php "$WP:/var/www/html/wp-content/mu-plugins/s01-browser-host.php"
printf '127.0.0.1 %s\n' "$WP" | sudo tee -a /etc/hosts >/dev/null
S01_BROWSER_BASE_URL="http://$WP" S01_BROWSER_NODE_MODULES="$RUNNER_TEMP/s01-browser/node_modules" \
 timeout --signal=TERM --kill-after=5s 240s node runner/.github/testing/s01-c02-polylang-browser-http.cjs
docker exec "$WP" rm -f /var/www/html/wp-content/mu-plugins/s01-browser-host.php
cli plugin install /tmp/s01-baseline.zip --force --activate > /tmp/s01-rollback-install.log
cli plugin is-active vf-ops >/dev/null
cli eval-file /tmp/s01-install.php rollback > /tmp/s01-rollback-readback.log
grep -q S01_C02_PACKAGE_LIFECYCLE_PHASE_PASS /tmp/s01-baseline-readback.log
grep -q S01_C02_REAL_ENDPOINT_SECURITY_PASS /tmp/s01-candidate-readback.log
grep -q S01_C02_PACKAGE_LIFECYCLE_PHASE_PASS /tmp/s01-rollback-readback.log
mkdir -p proof
python3 - <<'PY'
import json,os,pathlib
rows=[]
for name in ['baseline','candidate','rollback']:
    for line in pathlib.Path('/tmp/s01-'+name+'-readback.log').read_text().splitlines():
        if line.startswith('S01_C02_PACKAGE_LIFECYCLE_PHASE_PASS '):
            rows.append(json.loads(line.split(' ',1)[1]))
if len(rows)!=3 or [x['phase'] for x in rows]!=['baseline','candidate','rollback']:
    raise SystemExit('Missing exact lifecycle phase evidence')
candidate=rows[1]
if candidate.get('endpoint_rejection_cases')!=11 or candidate.get('rejected_endpoint_sql_writes')!=0:
    raise SystemExit('Incomplete actual endpoint security evidence')
receipt={'status':'PASS','candidate_sha':os.environ['PRODUCT_SHA'],
    'scope':'isolated native ZIP install, version-identified replacement, baseline rollback and real endpoint rejection',
    'phases':rows,'production_mutated':False,'polylang_pro_gate':'NOT_EXECUTED',
    'formal_update_discovery_tested':False,'release_ready':False}
pathlib.Path('proof/INSTALL_REPLACE_ROLLBACK.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('S01_C02_INSTALL_REPLACE_ROLLBACK_PASS',json.dumps(receipt))
PY
