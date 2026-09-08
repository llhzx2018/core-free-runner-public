#!/usr/bin/env bash
set -Eeuo pipefail
: "${READ_TOKEN:?}" "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}" "${UX_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO MIGRATION_USED=NO'
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" repo
cd repo
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$UX_SHA"
test "$(git rev-parse origin/main)" = "$BASE_SHA"
grep -RIl --exclude='CHANGELOG.md' --exclude='README.md' --exclude='GIT_IMPORT_MANIFEST' --exclude='SOURCE_MANIFEST' '1.35.20' VERSION src tests | sort >/tmp/actual_identity
printf '%s\n' VERSION src/style.css tests/update-refresh-policy-contract.php tests/visible-console-v2-contract.php tests/workbench-primary-action-contract.php | sort >/tmp/expected_identity
diff -u /tmp/expected_identity /tmp/actual_identity
python3 - <<'PY'
from pathlib import Path
p=Path('VERSION'); assert p.read_text()=='1.35.20\n'; p.write_text('1.35.21\n')
p=Path('src/style.css'); s=p.read_text(); assert s.count('1.35.20')==2; s=s.replace('1.35.20','1.35.21'); old='V1.35.21_S01_UPDATE_CENTER_ID_CLOSURE'; assert s.count(old)==1; s=s.replace(old,'V1.35.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE',1); p.write_text(s)
for fn in ['tests/update-refresh-policy-contract.php','tests/visible-console-v2-contract.php','tests/workbench-primary-action-contract.php']:
    p=Path(fn); s=p.read_text(); assert '1.35.20' in s; s=s.replace('1.35.20','1.35.21'); old='V1.35.21_S01_UPDATE_CENTER_ID_CLOSURE'; assert old in s; s=s.replace(old,'V1.35.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE'); p.write_text(s)
PY
test "$(cat VERSION)" = '1.35.21'
grep -F 'Version: 1.35.21' src/style.css >/dev/null
grep -F 'V1.35.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE' src/style.css >/dev/null
if grep -RIl --exclude='CHANGELOG.md' --exclude='README.md' --exclude='GIT_IMPORT_MANIFEST' --exclude='SOURCE_MANIFEST' '1.35.20' VERSION src tests | grep -q .; then echo STALE_VERSION_IDENTITY; exit 1; fi
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
php tests/workbench-primary-action-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
grep -F 'if ($credentialConfigured)' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'href="#vf-update-credential-setup"' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'id="vf-update-credential-setup"' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F "submit_button('保存更新凭证', 'primary'" src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
! grep -F '<span class="vf-update-component__id">' src/inc/update/class-vf-wp-update-admin-v1.php
git diff --name-only "$BASE_SHA" | sort >/tmp/actual
printf '%s\n' VERSION src/assets/css/admin/admin-update-center.css src/inc/update/class-vf-wp-update-admin-v1.php src/style.css tests/update-center-human-language-contract.php tests/update-refresh-policy-contract.php tests/visible-console-v2-contract.php tests/workbench-primary-action-contract.php | sort >/tmp/expected
diff -u /tmp/expected /tmp/actual
git diff --check
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add VERSION src/style.css tests/update-refresh-policy-contract.php tests/visible-console-v2-contract.php tests/workbench-primary-action-contract.php
git commit -m 'chore(S01-C01): bump credential-first update UX to 1.35.21'
git push -q origin HEAD:"$BRANCH"
echo "THEME_13521_CANDIDATE_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_13521_BUMP_GATE'
