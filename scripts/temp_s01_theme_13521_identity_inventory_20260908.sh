#!/usr/bin/env bash
set -euo pipefail
: "${READ_TOKEN:?}" "${REPO:?}" "${HEAD_SHA:?}"
echo 'INVENTORY_MODE=READ_ONLY MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO'
rm -rf /tmp/vf-theme-identity-inventory
git clone -q "https://x-access-token:${READ_TOKEN}@github.com/${REPO}.git" /tmp/vf-theme-identity-inventory
cd /tmp/vf-theme-identity-inventory
git checkout -q "$HEAD_SHA"
test "$(git rev-parse HEAD)" = "$HEAD_SHA"
echo 'VERSION_IDENTITY_PATHS_BEGIN'
git grep -l -E '1\.35\.21|V1\.35\.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE' -- ':!docs/**' ':!*.md' | sort
echo 'VERSION_IDENTITY_PATHS_END'
echo 'VERSION_IDENTITY_MATCHES_BEGIN'
git grep -n -E '1\.35\.21|V1\.35\.21_S01_UPDATE_CREDENTIAL_FIRST_CLOSURE' -- ':!docs/**' ':!*.md' || true
echo 'VERSION_IDENTITY_MATCHES_END'
test "$(tr -d '\r\n' < VERSION)" = '1.35.21'
echo 'PASS_S01_C01_13521_IDENTITY_INVENTORY'