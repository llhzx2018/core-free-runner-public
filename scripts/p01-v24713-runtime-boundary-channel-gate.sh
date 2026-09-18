#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"

CORE_ROOT="${CORE_ROOT:-$PWD/core}"
P01_ROOT="${P01_ROOT:-$PWD/p01}"
CORE_SHA="103933f3ef611f1308867718da7e4a05fec73266"
P01_SHA="e714cfe540ad39202c2cb558e5c0a370ef6d6502"
RELEASE_ID="391440404"
UPDATE_NAME="VF_Start_V2.47.13_UPDATE.zip"
UPDATE_BYTES="1852330"
UPDATE_SHA="e8094c52f5ef2c3973a08cfcd845ec6d99096ee46d03e02a3fa8fa11211fd3b4"

test "$(git -C "$CORE_ROOT" rev-parse HEAD)" = "$CORE_SHA"
test "$(git -C "$P01_ROOT" rev-parse HEAD)" = "$P01_SHA"

(
  cd "$CORE_ROOT"
  python3 scripts/check_manifest_contract.py
  find update-core/php -name '*.php' -print0 | xargs -0 -n1 php -l >/tmp/p01-v24713-core-php-lint.log
  php update-core/php/tests/run.php
  python3 - <<'PY'
import json
p=json.load(open('projects/P01.json',encoding='utf-8'))
assert p['schema_version']=='1.0'
assert p['project_id']=='P01' and p['component_id']=='APP'
assert p['enabled'] is True
assert p['current_version']=='2.47.10'
assert p['target_version']=='2.47.13'
assert p['update_type']=='ATOMIC'
assert p['from_versions']==['2.47.10']
assert p['schema_from']==p['schema_to']=='2026090401'
assert p['repository']=='llhzx2018/vf-start'
assert p['release_tag']=='v2.47.13'
assert p['release_id']==391440404
assert p['product_identity']=='e714cfe540ad39202c2cb558e5c0a370ef6d6502'
assert p['asset_name']=='VF_Start_V2.47.13_UPDATE.zip'
assert p['asset_bytes']==1852330
assert p['asset_sha256']=='e8094c52f5ef2c3973a08cfcd845ec6d99096ee46d03e02a3fa8fa11211fd3b4'
assert p['backup_required'] is True and p['rollback_supported'] is True
assert p['minimum_php']=='8.0.0'
print('P01_V24713_CHANNEL_MANIFEST_CONTRACT=PASS')
PY
)

REL="$(GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh api repos/llhzx2018/vf-start/releases/tags/v2.47.13)"
test "$(jq -r '.id' <<<"$REL")" = "$RELEASE_ID"
test "$(jq -r '.target_commitish' <<<"$REL")" = "$P01_SHA"
test "$(jq -r '.draft' <<<"$REL")" = "false"
test "$(jq -r '.prerelease' <<<"$REL")" = "false"
ASSET="$(jq -c --arg n "$UPDATE_NAME" '[.assets[]|select(.name==$n)] | if length==1 then .[0] else empty end' <<<"$REL")"
test -n "$ASSET"
test "$(jq -r '.size' <<<"$ASSET")" = "$UPDATE_BYTES"
test "$(jq -r '.digest' <<<"$ASSET")" = "sha256:$UPDATE_SHA"

P01_ROOT="$P01_ROOT" php <<'PHP'
<?php
declare(strict_types=1);
function vf_write_storage_guards(string $dir): void {}
require getenv('P01_ROOT') . '/src/app/UpdateManager.php';

$db = new PDO('sqlite::memory:');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->exec('CREATE TABLE update_state (state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL, updated_at TEXT NOT NULL)');

$private = sys_get_temp_dir() . '/p01-v24713-freshness-' . bin2hex(random_bytes(4));
$root = getenv('P01_ROOT') . '/src';
$manager = new VfUpdateManager($db, [
    'root' => $root,
    'private_root' => $private,
    'current_version' => '2.47.10',
    'manifest_fetcher' => static fn(): array => [],
]);

$db->prepare('INSERT INTO update_state(state_key,state_value,updated_at) VALUES(?,?,?)')->execute([
    'highest_verified_release_version', '2.47.12', gmdate('c')
]);
$db->prepare('INSERT INTO update_state(state_key,state_value,updated_at) VALUES(?,?,?)')->execute([
    'highest_verified_release_manifest_sha256', str_repeat('a',64), gmdate('c')
]);

$ref = new ReflectionClass(VfUpdateManager::class);
$m = $ref->getMethod('assertReleaseFreshness');
$m->setAccessible(true);

$m->invoke($manager, ['target_version'=>'2.47.13'], str_repeat('b',64));
echo "STRICTLY_NEWER_THAN_OBSERVED_24712=PASS\n";

$blocked = false;
try {
    $m->invoke($manager, ['target_version'=>'2.47.12'], str_repeat('b',64));
} catch (Throwable $e) {
    $blocked = str_contains($e->getMessage(), '同一正式版本的 Core Update Manifest 内容发生变化');
}
if (!$blocked) {
    fwrite(STDERR, "same-version anti-replay guard did not block\n");
    exit(1);
}
echo "SAME_VERSION_SILENT_REPLACEMENT_GUARD=PASS\n";

$it = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator($private, FilesystemIterator::SKIP_DOTS),
    RecursiveIteratorIterator::CHILD_FIRST
);
foreach ($it as $f) { $f->isDir() ? @rmdir($f->getPathname()) : @unlink($f->getPathname()); }
@rmdir($private);
PHP

mkdir -p evidence/runner
cat >evidence/runner/P01_V24713_RUNTIME_BOUNDARY_CHANNEL_GATE.txt <<EOF
CORE_UPDATES_EXACT_SHA=$CORE_SHA
P01_EXACT_SOURCE_SHA=$P01_SHA
CURRENT_VERSION=2.47.10
PREVIOUS_OBSERVED_TARGET=2.47.12
TARGET_VERSION=2.47.13
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
STRICTLY_NEWER_THAN_OBSERVED_24712=PASS
SAME_VERSION_SILENT_REPLACEMENT_GUARD=PRESERVED
PRODUCTION=NOT_TESTED
P01_V24713_RUNTIME_BOUNDARY_CHANNEL_GATE=PASS
EOF
cat evidence/runner/P01_V24713_RUNTIME_BOUNDARY_CHANNEL_GATE.txt
