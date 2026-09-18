#!/usr/bin/env bash
set -Eeuo pipefail
: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"

CORE_ROOT="${CORE_ROOT:-$PWD/core}"
EXACT_CORE_SHA="0f054443ff838ecb9bc49ac5ed111424d6c9e743"
P01_EXACT_SOURCE="252ca51215e7e4411741e2f53d0bcc68f37614f2"
RELEASE_ID="390634431"
UPDATE_NAME="VF_Start_V2.47.11_UPDATE.zip"
UPDATE_BYTES="1883052"
UPDATE_SHA="5b6d843a734280de22d22a447b105b1ecd07144bffee46ad36c50f1e7988ae95"

test "$(git -C "$CORE_ROOT" rev-parse HEAD)" = "$EXACT_CORE_SHA"
(
  cd "$CORE_ROOT"
  python3 scripts/check_manifest_contract.py
  find update-core/php -name '*.php' -print0 | xargs -0 -n1 php -l >/tmp/p01-core-php-lint.log
  php update-core/php/tests/run.php
  python3 - <<'PY'
import json
p=json.load(open('projects/P01.json',encoding='utf-8'))
assert p['schema_version']=='1.0'
assert p['project_id']=='P01' and p['component_id']=='APP'
assert p['enabled'] is True
assert p['current_version']=='2.47.10'
assert p['target_version']=='2.47.11'
assert p['update_type']=='ATOMIC'
assert p['from_versions']==['2.47.10']
assert p['schema_from']==p['schema_to']=='2026090401'
assert p['repository']=='llhzx2018/vf-start'
assert p['release_tag']=='v2.47.11'
assert p['release_id']==390634431
assert p['product_identity']=='252ca51215e7e4411741e2f53d0bcc68f37614f2'
assert p['asset_name']=='VF_Start_V2.47.11_UPDATE.zip'
assert p['asset_bytes']==1883052
assert p['asset_sha256']=='5b6d843a734280de22d22a447b105b1ecd07144bffee46ad36c50f1e7988ae95'
assert p['backup_required'] is True and p['rollback_supported'] is True
print('P01_CHANNEL_MANIFEST_CONTRACT=PASS')
PY
)

REL="$(GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh api repos/llhzx2018/vf-start/releases/tags/v2.47.11)"
test "$(jq -r '.id' <<<"$REL")" = "$RELEASE_ID"
test "$(jq -r '.target_commitish' <<<"$REL")" = "$P01_EXACT_SOURCE"
test "$(jq -r '.draft' <<<"$REL")" = "false"
test "$(jq -r '.prerelease' <<<"$REL")" = "false"
ASSET="$(jq -c --arg n "$UPDATE_NAME" '[.assets[]|select(.name==$n)] | if length==1 then .[0] else empty end' <<<"$REL")"
test -n "$ASSET"
test "$(jq -r '.size' <<<"$ASSET")" = "$UPDATE_BYTES"
test "$(jq -r '.digest' <<<"$ASSET")" = "sha256:$UPDATE_SHA"

mkdir -p evidence/runner
cat >evidence/runner/P01_V24711_CHANNEL_HOTFIX_R1_GATE.txt <<EOF
CORE_UPDATES_EXACT_SHA=$EXACT_CORE_SHA
P01_EXACT_SOURCE_SHA=$P01_EXACT_SOURCE
CURRENT_VERSION=2.47.10
TARGET_VERSION=2.47.11
SCHEMA=2026090401
MIGRATION=NONE
RELEASE_ID=$RELEASE_ID
UPDATE_NAME=$UPDATE_NAME
UPDATE_BYTES=$UPDATE_BYTES
UPDATE_SHA256=$UPDATE_SHA
MANIFEST_CONTRACT=PASS
PHP_LINT=PASS
UPDATE_CORE_REGRESSION=PASS
REMOTE_RELEASE_ASSET_IDENTITY=PASS
PRODUCTION=NOT_TESTED
P01_V24711_CHANNEL_HOTFIX_R1_GATE=PASS
EOF
cat evidence/runner/P01_V24711_CHANNEL_HOTFIX_R1_GATE.txt
