#!/usr/bin/env bash
set -euo pipefail

: "${P05_EXACT_SOURCE:?}"
test "$(git rev-parse HEAD)" = "$P05_EXACT_SOURCE"
test "$(cat VERSION)" = '1.1.10'
test ! -e VF_INSTALL_INSTANCE.json
test ! -e .vf-seo-site-instance.json
node - <<'NODE'
const p=require('./package.json'), l=require('./package-lock.json');
if(p.version!=='1.1.10'||l.version!=='1.1.10'||l.packages[''].version!=='1.1.10') process.exit(1);
NODE
python3 - <<'PY'
import json
d=json.load(open('VF_PROJECT.json'))
assert d['version']==d['target_version']==d['working_version']=='1.1.10'
assert d['status'].startswith('V1.1.10_RELEASE_CANDIDATE')
assert d['formal_release']=='v1.1.9'
x=d['v1_1_10_runtime_pointer_install_fix']
assert x['mechanism_gate']=='PASS'
assert x['pointer_created']=='AFTER_SUCCESSFUL_SETUP_ONLY'
assert x['private_state_isolation']=='POINTER_BOUND_RANDOM_SIBLING'
assert x['fresh_install_uses_home'] is False
assert x['fresh_install_uses_environment_storage_paths'] is False
assert d['production_deployment']=='NOT_DEPLOYED' and d['production_write']==0
PY
grep -Fq 'FINAL_EXACT_SOURCE_GATE_PENDING' docs/authority/RELEASE_V1.1.10_CANDIDATE.md
grep -Fq 'write pointer last' php/README.md

npm ci
npm run lint
npm run typecheck
npm run test:unit
npm run test:contract
npm run test:integration
npm run build

php -l php/src/SiteInstance.php
php -l php/src/RuntimePaths.php
php -l php/src/Config.php
php -l php/src/Installer.php
php -l php/src/setup-bootstrap.php
php -l php/src/bootstrap.php
test ! -e php/src/FreshInstallRecovery.php
bash php/tests/cloudpanel-fpm-home-cache-smoke.sh

npm run build:php-release
npm run php:release:gate
STAGING=build/vf-seo-php-release
test ! -e "$STAGING/VF_INSTALL_INSTANCE.json"
test ! -e "$STAGING/.vf-seo-site-instance.json"
test ! -e "$STAGING/.vf-seo-installing.lock"
test -z "$(find "$STAGING" \( -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name '*.wal' -o -name '*.shm' -o -name 'runtime.env' -o -name 'setup.lock.json' -o -name '.vfseo-data-*' \) -print -quit)"
find "$STAGING" -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/staging-before.sha

VF_INSTALL_ROOT="$STAGING" bash php/tests/browser-install-smoke.sh
VF_INSTALL_ROOT="$STAGING" bash php/tests/cloudpanel-fpm-real-install-smoke.sh
google-chrome --version
"$CHROMEWEBDRIVER/chromedriver" --version
VF_INSTALL_ROOT="$STAGING" python3 php/tests/browser-install-e2e.py

find "$STAGING" -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/staging-after.sha
cmp /tmp/staging-before.sha /tmp/staging-after.sha
test ! -e "$STAGING/VF_INSTALL_INSTANCE.json"
test -z "$(find "$STAGING" \( -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name 'runtime.env' -o -name 'setup.lock.json' -o -name '.vfseo-data-*' \) -print -quit)"

rm -rf "$STAGING"
npm run build:php-release
npm run php:release:gate
test ! -e "$STAGING/VF_INSTALL_INSTANCE.json"
test -z "$(find "$STAGING" \( -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name 'runtime.env' -o -name 'setup.lock.json' -o -name '.vfseo-data-*' \) -print -quit)"
(
  cd build
  rm -f VF_SEO_V1.1.10_FULL_CANDIDATE.zip
  zip -qr VF_SEO_V1.1.10_FULL_CANDIDATE.zip vf-seo-php-release
  sha256sum VF_SEO_V1.1.10_FULL_CANDIDATE.zip | tee /tmp/candidate-zip.sha256
  test -s VF_SEO_V1.1.10_FULL_CANDIDATE.zip
)

cat /tmp/candidate-zip.sha256
echo 'P05_V1110_FINAL_EXACT_SOURCE=PASS'
echo "EXACT_SOURCE=$P05_EXACT_SOURCE"
echo 'ENGINEERING_REGRESSION=PASS'
echo 'PHP_PACKAGE_GATE=PASS'
echo 'POINTER_LAST_BROWSER_SETUP=PASS'
echo 'DIRTY_STATE_FULL_DELETE_REINSTALL=PASS'
echo 'POISONED_HOME_ENV_ISOLATION=PASS'
echo 'GOOGLE_CHROME_E2E=PASS'
echo 'FORMAL_STAGING_IMMUTABLE=PASS'
echo 'PRISTINE_POST_TEST_REBUILD=PASS'
echo 'RELEASE_WRITE=0'
echo 'PRODUCTION_WRITE=0'
