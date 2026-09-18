#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_ROOT=${TARGET_ROOT:-$PWD/target}
BASELINE_ROOT=${BASELINE_ROOT:-$PWD/baseline}
OLD_HARNESS_ROOT=${OLD_HARNESS_ROOT:-$PWD/old-harness}
PROVEN_ROOT=${PROVEN_ROOT:-$PWD/proven}

TARGET_SHA=21533763cbbf4e1be2b0d69c906c01d1f072eab0
TARGET_TREE=598eaae633ef485dd2eef1330a9370cb46f90506
SOURCE_SHA=e714cfe540ad39202c2cb558e5c0a370ef6d6502
SOURCE_VERSION=2.47.13
TARGET_VERSION=2.47.14
OUT=/tmp/p01-v24714-navigation
BUILD=/tmp/p01-v24714-navigation-builder
FULL=VF-Start-V2.47.14-FULL.zip
UPDATE=VF_Start_V2.47.14_UPDATE.zip
REPAIR=repair-v2.47.14.php

test "$(git -C "$TARGET_ROOT" rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C "$TARGET_ROOT" rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(git -C "$BASELINE_ROOT" rev-parse HEAD)" = "$SOURCE_SHA"

rm -rf "$OUT" "$BUILD" /tmp/p01-r14-*
mkdir -p "$OUT" "$BUILD"
cp "$OLD_HARNESS_ROOT/scripts/p01-v24711-release-gate.py" "$BUILD/gate.py"
cp "$PROVEN_ROOT/scripts/p01-build-release.py" "$BUILD/p01-build-release.py"
cp "$PROVEN_ROOT/scripts/p01-build-release-v2.py" "$BUILD/p01-build-release-v2.py"

python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/p01-v24714-navigation-builder/gate.py')
s=p.read_text(encoding='utf-8')

s=s.replace('VERSION = "2.47.11"', 'VERSION = "2.47.14"', 1)
s=s.replace('SOURCE_VERSION = "2.47.10"', 'SOURCE_VERSION = "2.47.13"', 1)
s=s.replace('BRIDGE_NAME = "P01_V24710_AUTH_BRIDGE.php"\\n', '', 1)

old="    base = load_base(here / 'p01-build-release.py')\n    base.VERSION = VERSION"
new="    base = load_base(here / 'p01-build-release.py')\n    v2 = load_base(here / 'p01-build-release-v2.py')\n    base.VERSION = VERSION"
if old not in s: raise SystemExit('base loader anchor mismatch')
s=s.replace(old,new,1)

# Keep gate-only deployment/docs in FULL, but exclude them from Atomic runtime source verification.
old="""    target = base.collect(candidate)
    source = base.collect(source_root)"""
new="""    target_all = base.collect(candidate)
    source_all = base.collect(source_root)
    gate_only = {'.gitignore','CHANGELOG.md','DEPLOY-HERE.txt','FULL-PACKAGE-NOTES.txt','README.md','UPGRADE-V2.txt','robots.txt'}
    runtime_excluded = gate_only | {'VF-Start-Browser-Extension.zip'}
    target = {k:v for k,v in target_all.items() if k not in runtime_excluded}
    source = {k:v for k,v in source_all.items() if k not in runtime_excluded}"""
if old not in s: raise SystemExit('collect anchor mismatch')
s=s.replace(old,new,1)

# V2.47.13 already contains update authorization recovery, so there is no bridge artifact in V2.47.14.
old="""        'private_data_included': False,
        'update': {
            'from_versions': [SOURCE_VERSION],
            'asset_name': UPDATE_NAME,
            'backup_required': True,
            'rollback_supported': True,
            'bridge': BRIDGE_NAME,
        },"""
new="""        'private_data_included': False,
        'atomic_runtime_excluded_files': sorted(runtime_excluded),
        'update': {
            'from_versions': [SOURCE_VERSION],
            'asset_name': UPDATE_NAME,
            'backup_required': True,
            'rollback_supported': True,
        },"""
if old not in s: raise SystemExit('release manifest anchor mismatch')
s=s.replace(old,new,1)

old="""    target_with = dict(target)
    target_with['release-manifest.json'] = (json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\\n').encode()

    bridge = build_bridge(source, target)
    bridge_bytes = bridge.encode()
    (out / BRIDGE_NAME).write_bytes(bridge_bytes)

    repair = base.build_repair(source, target_with, sha256_bytes(target['app/UpdateManager.php']))"""
new="""    target_with = dict(target)
    target_with['release-manifest.json'] = (json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\\n').encode()
    full_with = dict(target_all)
    full_with['release-manifest.json'] = target_with['release-manifest.json']

    repair = v2.build_repair(source, target_with, sha256_bytes(target['app/UpdateManager.php']))
    old_constants = "public const SOURCE_VERSION='2.21.14';\\n    public const TARGET_VERSION='2.21.15';\\n    public const TARGET_SCHEMA='2026080902';"
    new_constants = "public const SOURCE_VERSION='2.47.13';\\n    public const TARGET_VERSION='2.47.14';\\n    public const TARGET_SCHEMA='2026090401';"
    if repair.count(old_constants) != 1: raise SystemExit('proven Atomic version anchor mismatch')
    repair = repair.replace(old_constants, new_constants, 1)"""
if old not in s: raise SystemExit('bridge/repair anchor mismatch')
s=s.replace(old,new,1)

old="""    removed = sorted((set(source) - set(target_with)) | {BRIDGE_NAME})"""
new="""    removed = sorted(set(source) - set(target_with))"""
if old not in s: raise SystemExit('removed anchor mismatch')
s=s.replace(old,new,1)

old="""    base.deterministic_zip(out / FULL_NAME, target_with)"""
new="""    base.deterministic_zip(out / FULL_NAME, full_with)"""
if old not in s: raise SystemExit('full zip anchor mismatch')
s=s.replace(old,new,1)

s=s.replace("'released_at': '2026-09-17T00:00:00Z',", "'released_at': '2026-09-18T00:00:00Z',", 1)
s=s.replace("'notes': {'summary': 'V2.47.11 restores private update authorization recovery and stale-discovery handling.'},",
            "'notes': {'summary': 'V2.47.14 fixes logged-out Navigation row layout width while preserving Atomic update safety.'},", 1)

old="""        'bridge_name': BRIDGE_NAME,
        'bridge_bytes': (out / BRIDGE_NAME).stat().st_size,
        'bridge_sha256': sha256_file(out / BRIDGE_NAME),
        'repair_sha256': sha256_file(out / REPAIR_NAME),"""
new="""        'repair_sha256': sha256_file(out / REPAIR_NAME),"""
if old not in s: raise SystemExit('result bridge anchor mismatch')
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
PY

build_once(){
  local dest="$1"
  rm -rf "$dest"; mkdir -p "$dest"
  python3 "$BUILD/gate.py"     --candidate "$TARGET_ROOT/src"     --source "$BASELINE_ROOT/src"     --out "$dest"     --candidate-commit "$TARGET_SHA"     --candidate-tree "$TARGET_TREE"     --source-commit "$SOURCE_SHA"     >/tmp/p01-r14-build.json
}

build_once "$OUT"
build_once /tmp/p01-v24714-navigation-rebuild
(cd "$OUT" && sha256sum "$FULL" "$UPDATE" "$REPAIR" | sort) >/tmp/p01-r14-a.sum
(cd /tmp/p01-v24714-navigation-rebuild && sha256sum "$FULL" "$UPDATE" "$REPAIR" | sort) >/tmp/p01-r14-b.sum
diff -u /tmp/p01-r14-a.sum /tmp/p01-r14-b.sum

test "$(unzip -Z1 "$OUT/$UPDATE" | wc -l | tr -d ' ')" = 1
unzip -Z1 "$OUT/$UPDATE" | grep -Fxq "$REPAIR"
php "$OUT/$REPAIR" --self-test >/tmp/p01-r14-selftest.json
jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' /tmp/p01-r14-selftest.json >/dev/null
! unzip -Z1 "$OUT/$FULL" | grep -Eq '(^|/)(private|backups|uploads|runtime-data)(/|$)'

setup_site(){
  local root="$1" port="$2" title="$3" evidence="$4"
  mkdir -p "$evidence"
  php -S "127.0.0.1:$port" -t "$root" >"$evidence/server.log" 2>&1 & SITE_PID=$!
  local cookies="$evidence/cookies"
  for _ in $(seq 1 80); do
    curl -fsS -c "$cookies" -b "$cookies" "http://127.0.0.1:$port/setup.php" -o "$evidence/setup.html" && break
    sleep .25
  done
  local csrf
  csrf=$(python3 -c "import re; s=open('$evidence/setup.html',encoding='utf-8').read(); m=re.search(r'name=\"setup_csrf\"\\s+value=\"([^\"]+)\"',s); assert m; print(m.group(1))")
  curl -fsS -c "$cookies" -b "$cookies" -X POST "http://127.0.0.1:$port/setup.php"     --data-urlencode "setup_csrf=$csrf"     --data-urlencode "site_title=$title"     --data-urlencode 'admin_password=vf-atomic-r14-test'     --data-urlencode 'admin_password_confirm=vf-atomic-r14-test'     -o "$evidence/setup-post.html"
  curl -fsS -c "$cookies" -b "$cookies" -H 'Content-Type: application/json'     --data '{"password":"vf-atomic-r14-test"}'     "http://127.0.0.1:$port/api.php?action=login" -o "$evidence/login.json"
  jq -e '.ok==true and (.csrf|type=="string") and (.csrf|length>10)' "$evidence/login.json" >/dev/null
  local code
  code=$(curl -sS -o "$evidence/setup-revisit.html" -w '%{http_code}' -c "$cookies" -b "$cookies" "http://127.0.0.1:$port/setup.php")
  test "$code" = "200"
}
stop_site(){ kill "$SITE_PID" 2>/dev/null || true; wait "$SITE_PID" 2>/dev/null || true; }

seed_business(){
  ROOT="$1" php <<'PHP'
<?php
require getenv('ROOT').'/app/FunctionalWorkspaceCore.php';
$db=vf_db(); $repo=new VfRepository($db);
$cat=$repo->createCategory(['name'=>'R14 Preserve','description'=>'Atomic R14','is_private'=>0,'sort_order'=>100]);
$repo->saveLink(null,['title'=>'R14 Preserve Link','url'=>'https://r14-preserve.example/item','surface'=>'start','tags'=>['r14'],'category_id'=>$cat],'manual');
PHP
}
assert_business(){
  ROOT="$1" php -r 'require getenv("ROOT")."/app/FunctionalWorkspaceCore.php"; if((int)vf_db()->query("SELECT COUNT(*) FROM links WHERE title=\"R14 Preserve Link\"")->fetchColumn()!==1) exit(1);'
}

preserve_state(){
  ROOT="$1" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
require $root.'/app/bootstrap.php';
require_once $root.'/app/UpdateCredentialStore.php';
$runtime=include $root.'/app/.runtime.php';
$private=(string)$runtime['data_dir'];
$store=new VfUpdateCredentialStore($private);
$store->save('github_pat_SYNTHETIC_R14_READ_ONLY_0123456789');
$dir=$private.'/update-auth';
file_put_contents($dir.'/r14-preserve.txt',"PRESERVE-R14\n");
chmod($dir.'/r14-preserve.txt',0600);
PHP
}

assert_state(){
  ROOT="$1" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
require $root.'/app/bootstrap.php';
require_once $root.'/app/UpdateCredentialStore.php';
$runtime=include $root.'/app/.runtime.php';
$private=(string)$runtime['data_dir'];
$store=new VfUpdateCredentialStore($private);
if($store->managedToken()!=='github_pat_SYNTHETIC_R14_READ_ONLY_0123456789') exit(1);
$token=$private.'/update-auth/github-read-token';
clearstatcache(true,$token);
if(is_link($token) || !is_file($token)) exit(2);
if((fileperms($token)&0777)!==0600) exit(3);
if(trim((string)@file_get_contents($private.'/update-auth/r14-preserve.txt'))!=='PRESERVE-R14') exit(4);
PHP
}

# Public-authority focused contracts on exact source.
php "$TARGET_ROOT/tests/unit/navigation_public_row_layout_contract.php" | grep -Fx P01_NAVIGATION_PUBLIC_ROW_LAYOUT_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_authority_contract.php" >/tmp/p01-r14-nav-search.log
php "$TARGET_ROOT/tests/unit/navigation_search_context_contract.php" >/tmp/p01-r14-nav-context.log
php "$TARGET_ROOT/tests/unit/uxui_round7_navigation_home_identity_contract.php" | grep -Fx UXUI_ROUND7_NAVIGATION_HOME_IDENTITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/update_recovery_contract.php" >/tmp/p01-r14-update-recovery.log
php "$TARGET_ROOT/tests/unit/update_csrf_recovery_contract.php" >/tmp/p01-r14-update-csrf.log

# INSTALL: clean FULL -> setup -> admin login -> setup revisit -> verify.
FRESH=/tmp/p01-r14-fresh
rm -rf "$FRESH"; mkdir -p "$FRESH"; unzip -q "$OUT/$FULL" -d "$FRESH"
setup_site "$FRESH" 19821 'P01 R14 Fresh' /tmp/p01-r14-fresh-evidence
stop_site
FRESH="$FRESH" php -r 'require getenv("FRESH")."/app/bootstrap.php"; if(VF_VERSION!=="2.47.14") exit(1);'
php "$FRESH/cli/verify.php" | grep -Fx VERIFY_PASS=YES

# UI regression on a real public render from the clean target install.
seed_business "$FRESH"
php -S 127.0.0.1:19826 -t "$FRESH" >/tmp/p01-r14-public-ui-server.log 2>&1 & UI_PID=$!
for _ in $(seq 1 80); do
  curl -fsS "http://127.0.0.1:19826/start.php" -o /tmp/p01-r14-public-navigation.html && break
  sleep .2
done
kill "$UI_PID" 2>/dev/null || true; wait "$UI_PID" 2>/dev/null || true
grep -F 'R14 Preserve Link' /tmp/p01-r14-public-navigation.html >/dev/null
grep -F 'class="vf-asset-row"' /tmp/p01-r14-public-navigation.html >/dev/null
! grep -F 'class="vf-asset-select"' /tmp/p01-r14-public-navigation.html >/dev/null
grep -F 'grid-template-columns:36px minmax(0,1fr) auto;' "$FRESH/assets/workspace-domain-nav.css" >/dev/null

# UPGRADE: exact released V2.47.13 -> V2.47.14, with user data + managed read credential preserved.
UP=/tmp/p01-r14-upgrade
rm -rf "$UP"; cp -a "$BASELINE_ROOT/src" "$UP"
setup_site "$UP" 19822 'P01 R14 Upgrade' /tmp/p01-r14-up-evidence
seed_business "$UP"; stop_site; preserve_state "$UP"
for f in .gitignore CHANGELOG.md DEPLOY-HERE.txt FULL-PACKAGE-NOTES.txt README.md UPGRADE-V2.txt robots.txt; do
  printf 'OWNER-PRODUCTION-GATE-ONLY-DRIFT:%s\n' "$f" >"$UP/$f"
done
printf 'OWNER-PRODUCTION-BROWSER-EXTENSION-DRIFT\n' >"$UP/VF-Start-Browser-Extension.zip"
php "$OUT/$REPAIR" --verify-source="$UP" | jq -e '.ok==true' >/dev/null
php "$OUT/$REPAIR" --run="$UP" >/tmp/p01-r14-upgrade.json
jq -e '.ok==true and .already_current==false and .schema=="2026090401"' /tmp/p01-r14-upgrade.json >/dev/null
test "$(tr -d '\r\n ' < "$UP/VERSION.txt")" = "$TARGET_VERSION"
assert_business "$UP"; assert_state "$UP"
grep -Fx 'OWNER-PRODUCTION-GATE-ONLY-DRIFT:CHANGELOG.md' "$UP/CHANGELOG.md" >/dev/null
grep -Fx 'OWNER-PRODUCTION-GATE-ONLY-DRIFT:DEPLOY-HERE.txt' "$UP/DEPLOY-HERE.txt" >/dev/null
php "$UP/cli/verify.php" | grep -Fx VERIFY_PASS=YES

# SECURITY: real runtime source tamper must still fail source verification.
TAMPER=/tmp/p01-r14-runtime-tamper
rm -rf "$TAMPER"; cp -a "$BASELINE_ROOT/src" "$TAMPER"
printf '\n/* runtime tamper probe */\n' >>"$TAMPER/app/bootstrap.php"
set +e
php "$OUT/$REPAIR" --verify-source="$TAMPER" >/tmp/p01-r14-runtime-tamper.json
tamper_rc=$?
set -e
test "$tamper_rc" -ne 0
jq -e '.ok==false and (.errors|index("app/bootstrap.php:sha")!=null)' /tmp/p01-r14-runtime-tamper.json >/dev/null

# ROLLBACK: injected post-apply failure must restore source, user data and managed credential.
FAIL=/tmp/p01-r14-fail
rm -rf "$FAIL"; cp -a "$BASELINE_ROOT/src" "$FAIL"
setup_site "$FAIL" 19823 'P01 R14 Rollback' /tmp/p01-r14-fail-evidence
seed_business "$FAIL"; stop_site; preserve_state "$FAIL"
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$OUT/$REPAIR" --run="$FAIL" >/tmp/p01-r14-fail.out 2>/tmp/p01-r14-fail.err
rc=$?
set -e
test "$rc" -ne 0
test "$(tr -d '\r\n ' < "$FAIL/VERSION.txt")" = "$SOURCE_VERSION"
php "$OUT/$REPAIR" --verify-source="$FAIL" | jq -e '.ok==true' >/dev/null
assert_business "$FAIL"; assert_state "$FAIL"

# HARD INTERRUPTION recovery.
INT=/tmp/p01-r14-interrupt
rm -rf "$INT"; cp -a "$BASELINE_ROOT/src" "$INT"
setup_site "$INT" 19824 'P01 R14 Interrupt' /tmp/p01-r14-int-evidence
seed_business "$INT"; stop_site; preserve_state "$INT"
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$OUT/$REPAIR" --run="$INT" >/tmp/p01-r14-int.out 2>/tmp/p01-r14-int.err
rc=$?
set -e
test "$rc" = 97
php "$OUT/$REPAIR" --run="$INT" >/tmp/p01-r14-int-recover.json
jq -e '.ok==true and .interrupted_recovered==true' /tmp/p01-r14-int-recover.json >/dev/null
assert_business "$INT"; assert_state "$INT"

# GLOBAL barrier: update waits until in-flight request barrier is released.
BAR=/tmp/p01-r14-barrier
rm -rf "$BAR"; cp -a "$BASELINE_ROOT/src" "$BAR"
setup_site "$BAR" 19825 'P01 R14 Barrier' /tmp/p01-r14-bar-evidence
seed_business "$BAR"; stop_site; preserve_state "$BAR"
rm -f /tmp/p01-r14-barrier-ready
ROOT="$BAR" php -r 'require getenv("ROOT")."/app/bootstrap.php"; vf_request_global_barrier_acquire(); file_put_contents("/tmp/p01-r14-barrier-ready","1"); sleep(3);' & holder=$!
for _ in $(seq 1 40); do test -f /tmp/p01-r14-barrier-ready && break; sleep .1; done
test -f /tmp/p01-r14-barrier-ready
start_ns=$(date +%s%N)
php "$OUT/$REPAIR" --run="$BAR" >/tmp/p01-r14-barrier.json
end_ns=$(date +%s%N)
wait "$holder"
elapsed_ms=$(( (end_ns-start_ns)/1000000 ))
test "$elapsed_ms" -ge 2000
jq -e '.ok==true' /tmp/p01-r14-barrier.json >/dev/null
assert_business "$BAR"; assert_state "$BAR"

FULL_BYTES=$(stat -c '%s' "$OUT/$FULL")
FULL_SHA=$(sha256sum "$OUT/$FULL"|awk '{print $1}')
UPDATE_BYTES=$(stat -c '%s' "$OUT/$UPDATE")
UPDATE_SHA=$(sha256sum "$OUT/$UPDATE"|awk '{print $1}')
printf '%s  %s\n' "$FULL_SHA" "$FULL" >"$OUT/$FULL.sha256"
printf '%s  %s\n' "$UPDATE_SHA" "$UPDATE" >"$OUT/$UPDATE.sha256"

cat >"$OUT/R14_GATE_RECEIPT.txt" <<EOF
P01_EXACT_SOURCE_SHA=$TARGET_SHA
P01_EXACT_SOURCE_TREE=$TARGET_TREE
SOURCE_VERSION=$SOURCE_VERSION
TARGET_VERSION=$TARGET_VERSION
SCHEMA=2026090401
MIGRATION=NONE
PUBLIC_AUTHORITY_INSTALL=PASS
PUBLIC_AUTHORITY_SECURITY=PASS
PUBLIC_AUTHORITY_TESTING=PASS
PUBLIC_AUTHORITY_UPGRADE=PASS
PUBLIC_AUTHORITY_DATA_SCHEMA=PASS
PUBLIC_AUTHORITY_GIT=PASS
PUBLIC_AUTHORITY_UA_UI=PASS
OWNER_PREVIEW_RUNTIME_APPLICABILITY=N_A
OWNER_PREVIEW_RUNTIME_REASON=bounded corrective layout bug; no new product shape or interaction contract
CLEAN_FULL_INSTALL=PASS
INSTALL_ADMIN_LOGIN=PASS
INSTALL_SETUP_REVISIT=PASS
PUBLIC_NAVIGATION_ROW_RENDER=PASS
UI_PUBLIC_ROW_LAYOUT_CONTRACT=PASS
V24713_TO_V24714_ATOMIC_UPGRADE=PASS
DATA_PRESERVATION=PASS
MANAGED_UPDATE_CREDENTIAL_PRESERVATION=PASS
MANAGED_CREDENTIAL_MODE_0600=PASS
GATE_ONLY_DRIFT_ACCEPTED=PASS
RUNTIME_TAMPER_REJECTED=PASS
INJECTED_FAILURE_ROLLBACK=PASS
INTERRUPTION_RECOVERY=PASS
GLOBAL_BARRIER=PASS
DETERMINISTIC_PACKAGE_IDENTITY=PASS
FULL_BYTES=$FULL_BYTES
FULL_SHA256=$FULL_SHA
UPDATE_BYTES=$UPDATE_BYTES
UPDATE_SHA256=$UPDATE_SHA
PRODUCTION=NOT_WRITTEN
P01_V24714_NAVIGATION_ROW_RELEASE_GATE=PASS
EOF
cat "$OUT/R14_GATE_RECEIPT.txt"
