#!/usr/bin/env bash
set -Eeuo pipefail
repo="$(realpath "$1")"
lane="$(realpath "$2")"
proof="$(realpath -m "$3")"
: "$TARGET_SHA" "$TARGET_VERSION" "$POLYLANG_PRO_ZIP_PATH" "$MARIADB_ROOT_PASSWORD"
test "$(git -C "$repo" rev-parse HEAD)" = "$TARGET_SHA"
test -f "$POLYLANG_PRO_ZIP_PATH"
export S01_SLUG_ISOLATED=1
mkdir -p "$proof/browser"
mysql --protocol=tcp -h127.0.0.1 -uroot -p"$MARIADB_ROOT_PASSWORD" -e "CREATE DATABASE vf_ops_slug_coverage CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON vf_ops_slug_coverage.* TO 'vf'@'%';"
scope_wp="$RUNNER_TEMP/s01-slug-coverage-wp"
mkdir -p "$scope_wp"
wp core download --path="$scope_wp" --version=7.0.2 >/dev/null
wp config create --path="$scope_wp" --dbname=vf_ops_slug_coverage --dbuser=vf --dbpass=vf --dbhost=127.0.0.1:3306 --skip-check >/dev/null
wp core install --path="$scope_wp" --url=http://127.0.0.1:18106 --title='Synthetic Slug Coverage' --admin_user=admin --admin_password='S01-Synthetic-Install-Only!' --admin_email=runner@example.invalid --skip-email >/dev/null
wp plugin install "$POLYLANG_PRO_ZIP_PATH" --path="$scope_wp" --activate >/dev/null
wp plugin install "$proof/vf-tools-ops_V$TARGET_VERSION.zip" --path="$scope_wp" --activate >/dev/null
wp eval --path="$scope_wp" 'do_action("admin_init");' >/dev/null
mkdir -p "$scope_wp/wp-content/mu-plugins"
cp "$lane/browser-host.php" "$scope_wp/wp-content/mu-plugins/s01-browser-host.php"
wp eval-file "$lane/coverage-fixture.php" coverage --path="$scope_wp" | tee "$proof/SLUG_NATIVE.txt"
grep -q S01_NATIVE_SLUG_COVERAGE_PASS "$proof/SLUG_NATIVE.txt"
php -S 127.0.0.1:18106 -t "$scope_wp" > "$RUNNER_TEMP/s01-slug-php-server.log" 2>&1 &
scope_server_pid=$!
cleanup(){ kill "$scope_server_pid" 2>/dev/null || true; rm -rf "$scope_wp"; }
trap cleanup EXIT
for _ in $(seq 1 30); do
 if curl -fsS http://127.0.0.1:18106/wp-login.php >/dev/null; then break; fi
 sleep 1
done
scope_node="$RUNNER_TEMP/s01-slug-browser"
mkdir -p "$scope_node"
npm install --prefix "$scope_node" --no-package-lock --no-audit --no-fund playwright@1.56.1 >/dev/null
"$scope_node/node_modules/.bin/playwright" install --with-deps chromium >/dev/null
export S01_BROWSER_NODE_MODULES="$scope_node/node_modules" S01_BROWSER_BASE_URL=http://127.0.0.1:18106
S01_COVERAGE_PHASE=clean timeout --signal=TERM --kill-after=5s 240s node "$lane/coverage-browser.cjs" "$proof"
wp eval-file "$lane/coverage-fixture.php" issue --path="$scope_wp" | tee -a "$proof/SLUG_NATIVE.txt"
S01_COVERAGE_PHASE=issue timeout --signal=TERM --kill-after=5s 240s node "$lane/coverage-browser.cjs" "$proof"
python3 - "$proof" <<'PY'
import json,pathlib,sys,os
p=pathlib.Path(sys.argv[1]);log=(p/'SLUG_NATIVE.txt').read_text()
assert 'S01_NATIVE_SLUG_COVERAGE_PASS' in log
for phase in ['clean','issue']:
 r=json.loads((p/('SLUG_BROWSER_'+phase+'.json')).read_text())
 assert r['result']=='PASS' and r['candidate_sha']==os.environ['TARGET_SHA']
 assert [x['width'] for x in r['widths']]==[1440,1024,768,390]
result={'result':'PASS','candidate_sha':os.environ['TARGET_SHA'],'version':os.environ['TARGET_VERSION'],
 'native_inventory':3001,'native_budget_coverage':'PASS','zero_page_writes':'PASS','licensed_pro':'3.8.2',
 'clean_and_issue_responsive_browser':'PASS','real_authenticated_post_guards':'PASS','production_write':False,
 'owner_product_acceptance':'PENDING'}
(p/'SLUG_COVERAGE.json').write_text(json.dumps(result,indent=2)+'\n')
print('S01_SLUG_REAL_WP_BROWSER_PASS')
PY
