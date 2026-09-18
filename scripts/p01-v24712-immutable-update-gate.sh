#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_ROOT=${TARGET_ROOT:-$PWD/target}
BASELINE_ROOT=${BASELINE_ROOT:-$PWD/baseline}
OLD_HARNESS_ROOT=${OLD_HARNESS_ROOT:-$PWD/old-harness}
PROVEN_ROOT=${PROVEN_ROOT:-$PWD/proven}
TARGET_SHA=b8b8a4b1effc916083f9ed2966e85ced1d1bf251
TARGET_TREE=4b658772d2b4f2b74ad0784d8b27616f15a50d1b
SOURCE_SHA=972541fd06c66044105ec1b19cf7738c340c90c1
SOURCE_VERSION=2.47.10
TARGET_VERSION=2.47.12
OUT=/tmp/p01-v24712-atomic-r1
BUILD=/tmp/p01-v24712-atomic-r1-builder
FULL=VF-Start-V2.47.12-FULL.zip
UPDATE=VF_Start_V2.47.12_UPDATE.zip
REPAIR=repair-v2.47.12.php

test "$(git -C "$TARGET_ROOT" rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C "$TARGET_ROOT" rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(git -C "$BASELINE_ROOT" rev-parse HEAD)" = "$SOURCE_SHA"
rm -rf "$OUT" "$BUILD" /tmp/p01-r1-*
mkdir -p "$OUT" "$BUILD"
cp "$OLD_HARNESS_ROOT/scripts/p01-v24711-release-gate.py" "$BUILD/gate.py"
cp "$PROVEN_ROOT/scripts/p01-build-release.py" "$BUILD/p01-build-release.py"
cp "$PROVEN_ROOT/scripts/p01-build-release-v2.py" "$BUILD/p01-build-release-v2.py"
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/p01-v24712-atomic-r1-builder/gate.py')
s=p.read_text(encoding='utf-8')
if 'VERSION = "2.47.11"' not in s: raise SystemExit('old harness version anchor mismatch')
s=s.replace('VERSION = "2.47.11"', 'VERSION = "2.47.12"', 1)
s=s.replace('V2.47.11 restores private update authorization recovery and stale-discovery handling.', 'V2.47.12 republishes the proven Atomic recovery as a new immutable patch version.', 1)
old="    base = load_base(here / 'p01-build-release.py')\n    base.VERSION = VERSION"
new="    base = load_base(here / 'p01-build-release.py')\n    v2 = load_base(here / 'p01-build-release-v2.py')\n    base.VERSION = VERSION"
assert old in s
s=s.replace(old,new,1)
old="    repair = base.build_repair(source, target_with, sha256_bytes(target['app/UpdateManager.php']))"
new="""    repair = v2.build_repair(source, target_with, sha256_bytes(target['app/UpdateManager.php']))
    old_constants = \"public const SOURCE_VERSION='2.21.14';\\n    public const TARGET_VERSION='2.21.15';\\n    public const TARGET_SCHEMA='2026080902';\"
    new_constants = \"public const SOURCE_VERSION='2.47.10';\\n    public const TARGET_VERSION='2.47.12';\\n    public const TARGET_SCHEMA='2026090401';\"
    if repair.count(old_constants) != 1: raise SystemExit('proven Atomic version anchor mismatch')
    repair = repair.replace(old_constants, new_constants, 1)"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
PY

build_once(){
  local dest="$1"
  rm -rf "$dest"; mkdir -p "$dest"
  python3 "$BUILD/gate.py" --candidate "$TARGET_ROOT/src" --source "$BASELINE_ROOT/src" --out "$dest" --candidate-commit "$TARGET_SHA" --candidate-tree "$TARGET_TREE" --source-commit "$SOURCE_SHA" >/tmp/p01-r1-build.json
}
build_once "$OUT"
build_once /tmp/p01-v24712-atomic-r1-rebuild
(cd "$OUT" && sha256sum "$FULL" "$UPDATE" "$REPAIR" | sort) >/tmp/p01-r1-a.sum
(cd /tmp/p01-v24712-atomic-r1-rebuild && sha256sum "$FULL" "$UPDATE" "$REPAIR" | sort) >/tmp/p01-r1-b.sum
diff -u /tmp/p01-r1-a.sum /tmp/p01-r1-b.sum

test "$(unzip -Z1 "$OUT/$UPDATE" | wc -l | tr -d ' ')" = 1
unzip -Z1 "$OUT/$UPDATE" | grep -Fxq "$REPAIR"
php "$OUT/$REPAIR" --self-test >/tmp/p01-r1-selftest.json
jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' /tmp/p01-r1-selftest.json >/dev/null
! unzip -Z1 "$OUT/$FULL" | grep -Eq '(^|/)(private|backups|uploads|runtime-data)(/|$)'

setup_site(){
  local root="$1" port="$2" title="$3" evidence="$4"
  mkdir -p "$evidence"
  php -S "127.0.0.1:$port" -t "$root" >"$evidence/server.log" 2>&1 & SITE_PID=$!
  local cookies="$evidence/cookies"
  for _ in $(seq 1 80); do curl -fsS -c "$cookies" -b "$cookies" "http://127.0.0.1:$port/setup.php" -o "$evidence/setup.html" && break; sleep .25; done
  local csrf
  csrf=$(python3 -c "import re; s=open('$evidence/setup.html',encoding='utf-8').read(); m=re.search(r'name=\"setup_csrf\"\\s+value=\"([^\"]+)\"',s); assert m; print(m.group(1))")
  curl -fsS -c "$cookies" -b "$cookies" -X POST "http://127.0.0.1:$port/setup.php" --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=$title" --data-urlencode 'admin_password=vf-atomic-r1-test' --data-urlencode 'admin_password_confirm=vf-atomic-r1-test' -o "$evidence/setup-post.html"
}
stop_site(){ kill "$SITE_PID" 2>/dev/null || true; wait "$SITE_PID" 2>/dev/null || true; }
bridge_state(){
  local root="$1"
  cp "$TARGET_ROOT/src/app/CoreUpdates/GitHubClient.php" "$root/app/CoreUpdates/GitHubClient.php"
  cp "$TARGET_ROOT/src/app/UpdateCredentialStore.php" "$root/app/UpdateCredentialStore.php"
  cp "$TARGET_ROOT/src/update-credential.php" "$root/update-credential.php"
  cp "$OUT/P01_V24710_AUTH_BRIDGE.php" "$root/P01_V24710_AUTH_BRIDGE.php"
  ROOT="$root" php -r '$r=include getenv("ROOT")."/app/.runtime.php"; $d=$r["data_dir"]."/update-auth"; if(!is_dir($d)) mkdir($d,0700,true); file_put_contents($d."/r1-preserve.txt","PRESERVE-R1\n");'
}
assert_marker(){ ROOT="$1" php -r '$r=include getenv("ROOT")."/app/.runtime.php"; if(trim((string)@file_get_contents($r["data_dir"]."/update-auth/r1-preserve.txt"))!=="PRESERVE-R1") exit(1);'; }
seed_business(){ ROOT="$1" php <<'PHP'
<?php
require getenv('ROOT').'/app/FunctionalWorkspaceCore.php';
$db=vf_db(); $repo=new VfRepository($db);
$cat=$repo->createCategory(['name'=>'R1 Preserve','description'=>'Atomic R1','is_private'=>0,'sort_order'=>100]);
$repo->saveLink(null,['title'=>'R1 Preserve Link','url'=>'https://r1-preserve.example/item','surface'=>'start','tags'=>['r1'],'category_id'=>$cat],'manual');
PHP
}
assert_business(){ ROOT="$1" php -r 'require getenv("ROOT")."/app/FunctionalWorkspaceCore.php"; if((int)vf_db()->query("SELECT COUNT(*) FROM links WHERE title=\"R1 Preserve Link\"")->fetchColumn()!==1) exit(1);'; }

FRESH=/tmp/p01-r1-fresh; rm -rf "$FRESH"; mkdir -p "$FRESH"; unzip -q "$OUT/$FULL" -d "$FRESH"
setup_site "$FRESH" 19811 'P01 R1 Fresh' /tmp/p01-r1-fresh-evidence; stop_site
FRESH="$FRESH" php -r 'require getenv("FRESH")."/app/bootstrap.php"; if(VF_VERSION!=="2.47.12") exit(1);'
php "$FRESH/cli/verify.php" | grep -Fx VERIFY_PASS=YES

UP=/tmp/p01-r1-upgrade; rm -rf "$UP"; cp -a "$BASELINE_ROOT/src" "$UP"
setup_site "$UP" 19812 'P01 R1 Upgrade' /tmp/p01-r1-up-evidence; seed_business "$UP"; stop_site; bridge_state "$UP"
php "$OUT/$REPAIR" --verify-source="$UP" | jq -e '.ok==true' >/dev/null
php "$OUT/$REPAIR" --run="$UP" >/tmp/p01-r1-upgrade.json
jq -e '.ok==true and .already_current==false and .schema=="2026090401"' /tmp/p01-r1-upgrade.json >/dev/null
assert_business "$UP"; assert_marker "$UP"; test ! -e "$UP/P01_V24710_AUTH_BRIDGE.php"
php "$UP/cli/verify.php" | grep -Fx VERIFY_PASS=YES

FAIL=/tmp/p01-r1-fail; rm -rf "$FAIL"; cp -a "$BASELINE_ROOT/src" "$FAIL"
setup_site "$FAIL" 19813 'P01 R1 Rollback' /tmp/p01-r1-fail-evidence; seed_business "$FAIL"; stop_site; bridge_state "$FAIL"
set +e; VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$OUT/$REPAIR" --run="$FAIL" >/tmp/p01-r1-fail.out 2>/tmp/p01-r1-fail.err; rc=$?; set -e
test "$rc" -ne 0; test "$(tr -d '\r\n ' < "$FAIL/VERSION.txt")" = "$SOURCE_VERSION"; test -f "$FAIL/P01_V24710_AUTH_BRIDGE.php"
php "$OUT/$REPAIR" --verify-source="$FAIL" | jq -e '.ok==true' >/dev/null
assert_business "$FAIL"; assert_marker "$FAIL"

INT=/tmp/p01-r1-interrupt; rm -rf "$INT"; cp -a "$BASELINE_ROOT/src" "$INT"
setup_site "$INT" 19814 'P01 R1 Interrupt' /tmp/p01-r1-int-evidence; seed_business "$INT"; stop_site; bridge_state "$INT"
set +e; VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$OUT/$REPAIR" --run="$INT" >/tmp/p01-r1-int.out 2>/tmp/p01-r1-int.err; rc=$?; set -e
test "$rc" = 97
php "$OUT/$REPAIR" --run="$INT" >/tmp/p01-r1-int-recover.json
jq -e '.ok==true and .interrupted_recovered==true' /tmp/p01-r1-int-recover.json >/dev/null
assert_business "$INT"; assert_marker "$INT"; test ! -e "$INT/P01_V24710_AUTH_BRIDGE.php"

BAR=/tmp/p01-r1-barrier; rm -rf "$BAR"; cp -a "$BASELINE_ROOT/src" "$BAR"
setup_site "$BAR" 19815 'P01 R1 Barrier' /tmp/p01-r1-bar-evidence; seed_business "$BAR"; stop_site; bridge_state "$BAR"
rm -f /tmp/p01-r1-barrier-ready
ROOT="$BAR" php -r 'require getenv("ROOT")."/app/bootstrap.php"; vf_request_global_barrier_acquire(); file_put_contents("/tmp/p01-r1-barrier-ready","1"); sleep(3);' & holder=$!
for _ in $(seq 1 40); do test -f /tmp/p01-r1-barrier-ready && break; sleep .1; done
test -f /tmp/p01-r1-barrier-ready
start_ns=$(date +%s%N); php "$OUT/$REPAIR" --run="$BAR" >/tmp/p01-r1-barrier.json; end_ns=$(date +%s%N); wait "$holder"
elapsed_ms=$(( (end_ns-start_ns)/1000000 )); test "$elapsed_ms" -ge 2000
jq -e '.ok==true' /tmp/p01-r1-barrier.json >/dev/null; assert_business "$BAR"

FULL_BYTES=$(stat -c '%s' "$OUT/$FULL"); FULL_SHA=$(sha256sum "$OUT/$FULL"|awk '{print $1}')
UPDATE_BYTES=$(stat -c '%s' "$OUT/$UPDATE"); UPDATE_SHA=$(sha256sum "$OUT/$UPDATE"|awk '{print $1}')
printf '%s  %s\n' "$FULL_SHA" "$FULL" >"$OUT/$FULL.sha256"
printf '%s  %s\n' "$UPDATE_SHA" "$UPDATE" >"$OUT/$UPDATE.sha256"
cat >"$OUT/R1_GATE_RECEIPT.txt" <<EOF
P01_EXACT_SOURCE_SHA=$TARGET_SHA
SOURCE_VERSION=$SOURCE_VERSION
TARGET_VERSION=$TARGET_VERSION
SCHEMA=2026090401
MIGRATION=NONE
PROVEN_ATOMIC_PRIMITIVE_REF=0468b28ae57c368f80b03f85060318667bcc5834
GLOBAL_BARRIER=PASS
INTERRUPTION_RECOVERY=PASS
BRIDGED_PRODUCTION_SHAPE_UPGRADE=PASS
DATA_PRESERVATION=PASS
INJECTED_FAILURE_ROLLBACK=PASS
FULL_BYTES=$FULL_BYTES
FULL_SHA256=$FULL_SHA
UPDATE_BYTES=$UPDATE_BYTES
UPDATE_SHA256=$UPDATE_SHA
PRODUCTION=NOT_TESTED
P01_V24712_IMMUTABLE_UPDATE_GATE=PASS
EOF
cat "$OUT/R1_GATE_RECEIPT.txt"
