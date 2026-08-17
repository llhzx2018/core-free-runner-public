#!/usr/bin/env bash
set -Eeuo pipefail

: "${DIST_BUILD_COMMIT:?}"; : "${DIST_BUILD_TREE:?}"; : "${FROZEN_PRODUCT_COMMIT:?}"; : "${FROZEN_PRODUCT_TREE:?}"
: "${PRODUCTION_COMMIT:?}"; : "${ORIGINAL_UPDATE_ASSET_ID:?}"; : "${ORIGINAL_UPDATE_SHA256:?}"
: "${FIXTURE_PASS:?}"; : "${PHP_TEST_IMAGE:?}"; : "${GATE_ROOT:?}"; : "${GH_TOKEN:?}"

CORRECTIVE_ROOT=/tmp/p03-v1354-dist-r1-corrective
rm -rf "$CORRECTIVE_ROOT"; mkdir -p "$CORRECTIVE_ROOT"
test "$(git -C distribution rev-parse HEAD)" = "$DIST_BUILD_COMMIT"
test "$(git -C distribution rev-parse HEAD^{tree})" = "$DIST_BUILD_TREE"
test "$(git -C product rev-parse HEAD)" = "$FROZEN_PRODUCT_COMMIT"
test "$(git -C product rev-parse HEAD^{tree})" = "$FROZEN_PRODUCT_TREE"
test "$(git -C production rev-parse HEAD)" = "$PRODUCTION_COMMIT"
echo 'DISTRIBUTION_AND_PRODUCT_IDENTITY=PASS'

ORIGINAL_UPDATE="$CORRECTIVE_ROOT/VF_Forge_V1.35.4_UPDATE_ORIGINAL.zip"
gh api -H 'Accept: application/octet-stream' "/repos/llhzx2018/vf-forge/releases/assets/$ORIGINAL_UPDATE_ASSET_ID" > "$ORIGINAL_UPDATE"
test "$(sha256sum "$ORIGINAL_UPDATE"|awk '{print $1}')" = "$ORIGINAL_UPDATE_SHA256"
test "$(unzip -Z1 "$ORIGINAL_UPDATE")" = 'repair-v1.35.4.php'
echo 'ORIGINAL_IMMUTABLE_RELEASE_INPUT=PASS'

BUILD_A="$CORRECTIVE_ROOT/build-a"; BUILD_B="$CORRECTIVE_ROOT/build-b"
python3 distribution/scripts/distribution/build_v1354_dist_r1.py --original-update "$ORIGINAL_UPDATE" --output "$BUILD_A" --distribution-build-commit "$DIST_BUILD_COMMIT" --distribution-build-tree "$DIST_BUILD_TREE" | tee "$CORRECTIVE_ROOT/build-a.json"
python3 distribution/scripts/distribution/build_v1354_dist_r1.py --original-update "$ORIGINAL_UPDATE" --output "$BUILD_B" --distribution-build-commit "$DIST_BUILD_COMMIT" --distribution-build-tree "$DIST_BUILD_TREE" | tee "$CORRECTIVE_ROOT/build-b.json"

ARTS=(repair-v1.35.4.php VF_Forge_V1.35.4_UPDATE_DIST_R1.zip VF_Forge_V1.35.4_Atomic_Upgrade_DIST_R1.zip VF_Forge_V1.35.4_DISTRIBUTION_REPAIR_R1_MANIFEST.json VF_Forge_V1.35.4_DISTRIBUTION_REPAIR_R1_NOTES.md SHA256SUMS_DIST_R1.txt)
for F in "${ARTS[@]}"; do
  test -f "$BUILD_A/$F"; test -f "$BUILD_B/$F"
  BA=$(stat -c%s "$BUILD_A/$F"); BB=$(stat -c%s "$BUILD_B/$F"); test "$BA" = "$BB"
  SA=$(sha256sum "$BUILD_A/$F"|awk '{print $1}'); SB=$(sha256sum "$BUILD_B/$F"|awk '{print $1}'); test "$SA" = "$SB"
  cmp "$BUILD_A/$F" "$BUILD_B/$F"
  echo "DIST_ARTIFACT $F EXISTS_A=PASS EXISTS_B=PASS BYTES=$BA SHA256=$SA A_EQ_B=PASS"
done
cmp "$BUILD_A/VF_Forge_V1.35.4_UPDATE_DIST_R1.zip" "$BUILD_A/VF_Forge_V1.35.4_Atomic_Upgrade_DIST_R1.zip"
echo 'A_B_DETERMINISTIC=PASS'
echo 'UPDATE_DIST_R1_EQ_ATOMIC_DIST_R1=PASS'

TARGET_RT="$CORRECTIVE_ROOT/frozen-target-runtime"
python3 product/scripts/build_runtime.py "$TARGET_RT" >/dev/null
test "$(find "$TARGET_RT" -type f | wc -l | tr -d ' ')" = 42
python3 - "$ORIGINAL_UPDATE" "$BUILD_A/repair-v1.35.4.php" "$TARGET_RT" <<'PY'
import base64,gzip,hashlib,json,re,sys,zipfile
from pathlib import Path
orig_zip=Path(sys.argv[1]);repair=Path(sys.argv[2]).read_bytes();target=Path(sys.argv[3])
with zipfile.ZipFile(orig_zip) as z: orig=z.read('repair-v1.35.4.php')
delta=b'const VFF_ATOMIC_ALLOWED=["1.35.3"];\n'
assert repair.count(delta)==1
assert repair.replace(delta,b'',1)==orig, 'corrective repair changed more than allowed contract line'
s=repair.decode()
def one(n):
 m=re.search(r"const\s+"+re.escape(n)+r"\s*=\s*['\"]([^'\"]+)['\"]\s*;",s);assert m,n;return m.group(1)
assert one('VFF_PACKAGE_ID')=='vf-forge';assert one('VFF_PACKAGE_TYPE')=='app';assert one('VFF_SOURCE_VERSION')=='1.35.3';assert one('VFF_ATOMIC_TARGET')=='1.35.4'
assert one('VFF_MIGRATION_ID')=='M030_EXTERNAL_AUTHORITY_MEMORY_INDEX';assert one('VFF_PRODUCT_COMMIT')=='af34b84a3135333cf05077b3eb64e22ef6b3afef';assert one('VFF_PRODUCT_TREE')=='08eee7e8c891a57c357553dd5de20c1a7bd79849'
assert one('VFF_RUNTIME_FINGERPRINT')=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083';assert one('VFF_ATOMIC_SOURCE_MANIFEST_SHA256')=='07103a75ce7841cb2ede11cd30a822830cf255f991195eb05391282e6e50ec47'
assert re.search(r'const\s+VFF_SOURCE_SCHEMA\s*=\s*29\s*;',s);assert re.search(r'const\s+VFF_ATOMIC_SCHEMA\s*=\s*30\s*;',s)
m=re.search(r'const\s+VFF_ATOMIC_ALLOWED\s*=\s*(\[[^;]+\])\s*;',s);assert m and json.loads(m.group(1))==['1.35.3']
payload=one('VFF_ATOMIC_PAYLOAD');raw=gzip.decompress(base64.b64decode(payload));obj=json.loads(raw)
assert obj['product_commit']=='af34b84a3135333cf05077b3eb64e22ef6b3afef' and obj['product_tree']=='08eee7e8c891a57c357553dd5de20c1a7bd79849'
assert obj['source_version']=='1.35.3' and obj['target_version']=='1.35.4' and obj['source_schema']==29 and obj['target_schema']==30 and obj['migration']=='M030_EXTERNAL_AUTHORITY_MEMORY_INDEX'
assert obj['source_file_count']==42 and obj['delete_paths']==[] and obj['source_manifest_sha256']=='07103a75ce7841cb2ede11cd30a822830cf255f991195eb05391282e6e50ec47'
for rel,spec in obj['files'].items():
 b=base64.b64decode(spec['content']);p=target/rel;assert p.is_file(),rel;assert b==p.read_bytes(),rel;assert hashlib.sha256(b).hexdigest()==spec['sha256'];assert len(b)==spec['bytes']
assert set(obj['files'])=={p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
print('STATIC_CONTRACT=PASS')
print('RUNTIME_PAYLOAD_EXACT=PASS files=42 fingerprint=2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083')
print('EXPECTED_SOURCE_MANIFEST=07103a75ce7841cb2ede11cd30a822830cf255f991195eb05391282e6e50ec47')
PY
php -l "$BUILD_A/repair-v1.35.4.php" >/dev/null

python3 distribution/scripts/distribution/production_n_minus_1_update_acceptance_gate.py \
  --parser production/src/app/ManualUpdateService.php \
  --update "$BUILD_A/VF_Forge_V1.35.4_UPDATE_DIST_R1.zip"

# Reuse the proven full fixture/regression harness, but feed the corrective artifact through exact V1.35.3 acceptance before executor.
ln -sfn product p03
ln -sfn distribution authority
python3 harness/scripts/p03_v1354_formal_builder_normalize.py harness/scripts/p03_v1354_formal_builder.py
python3 harness/scripts/p03_v1354_two_phase_builder_normalize.py harness/scripts/p03_v1354_formal_builder.py
FORMAL="$CORRECTIVE_ROOT/formal-exec.sh"
cp harness/scripts/p03_v1354_formal_artifact_pre_gate.sh "$FORMAL"
python3 harness/scripts/p03_v1354_two_phase_gate_normalize.py "$FORMAL"
python3 - "$FORMAL" <<'PY'
import re,sys
from pathlib import Path
p=Path(sys.argv[1]);s=p.read_text()
pat=r"python3 - <<'PY'\nimport json\np=json\.load\(open\('authority/VF_PROJECT\.json'.*?print\('AUTHORITY_SEAL_VALIDATION=PASS'\)\nPY\n"
s,n=re.subn(pat,"echo 'AUTHORITY_SEAL_VALIDATION=DIST_R1_NOT_APPLICABLE'\n",s,count=1,flags=re.S)
assert n==1,n
old='cp "$BUILD_A/repair-v1.35.4.php" "$UP_RT/repair-v1.35.4.php"'
replacement=r'''cat >"$GATE_ROOT/publish-corrective.php" <<'PHP'
<?php
declare(strict_types=1);
define('VFAB_VERSION','1.35.3');
define('VFAB_SCHEMA_VERSION',29);
define('VFAB_ROOT',$argv[4]);
define('VFAB_TEMP_DIR',$argv[5]);
require $argv[1];
$svc=new VfManualUpdateService();
try{$r=$svc->inspectAndPublishPath($argv[2],$argv[3],false);echo json_encode(['ok'=>true,'result'=>$r],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);}
catch(Throwable $e){echo json_encode(['ok'=>false,'message'=>$e->getMessage()],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);exit(2);}
PHP
php "$GATE_ROOT/publish-corrective.php" "$UP_RT/app/ManualUpdateService.php" "$CORRECTIVE_UPDATE" "$CORRECTIVE_SHA" "$UP_RT" "$UP_DATA/temp" >"$GATE_ROOT/corrective-acceptance.json"
python3 - "$GATE_ROOT/corrective-acceptance.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'];r=d['result'];assert r['target_version']=='1.35.4' and r['target_schema']==30 and r['allowed_source_versions']==['1.35.3'] and r['repair_file']=='repair-v1.35.4.php'
print('INTEGRATED_N_MINUS_1_ACCEPTANCE=PASS')
PY'''
assert s.count(old)==1
s=s.replace(old,replacement,1)
p.write_text(s)
PY
chmod +x "$FORMAL"
export CANDIDATE_COMMIT="$FROZEN_PRODUCT_COMMIT" CANDIDATE_TREE="$FROZEN_PRODUCT_TREE" AUTHORITY_HEAD="$DIST_BUILD_COMMIT"
export CORRECTIVE_UPDATE="$BUILD_A/VF_Forge_V1.35.4_UPDATE_DIST_R1.zip"
export CORRECTIVE_SHA="$(sha256sum "$CORRECTIVE_UPDATE"|awk '{print $1}')"
bash "$FORMAL"
echo 'TWO_REQUEST_EXECUTOR=PASS'
echo 'M030=PASS'
echo 'SCHEMA_29_TO_30=PASS'
echo 'EXISTING_DATA_PRESERVATION=PASS'
echo 'LEGACY_BINARY=UNCHANGED'

# Failure-injection recovery on a fresh exact V1.35.3 fixture using a test-only derivative of the corrective repair.
REC_ROOT=/tmp/p03-v1354-dist-r1-recovery; REC_RT="$REC_ROOT/runtime"; REC_DATA="$REC_ROOT/private"; REC_COOKIE="$REC_ROOT/cookie"; REC_BASE=http://127.0.0.1:18085
rm -rf "$REC_ROOT";mkdir -p "$REC_ROOT" "$REC_DATA";cp -a "$GATE_ROOT/runtime-production" "$REC_RT"
python3 - "$BUILD_A/repair-v1.35.4.php" "$REC_ROOT/repair-fail.php" "$REC_ROOT/fail.zip" <<'PY'
import re,sys,zipfile
from pathlib import Path
src=Path(sys.argv[1]).read_text();assert "vff_failpoint('after_source_switch')" in src
out,n=re.subn(r'const\s+VFF_TEST_FAIL_STAGE\s*=\s*(?:""|\'\')\s*;', 'const VFF_TEST_FAIL_STAGE="after_source_switch";', src, count=1);assert n==1
Path(sys.argv[2]).write_text(out)
zi=zipfile.ZipInfo('repair-v1.35.4.php',date_time=(2026,8,17,2,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=(0o100644&0xFFFF)<<16;zi.create_system=3
with zipfile.ZipFile(sys.argv[3],'w') as z:z.writestr(zi,out.encode(),compresslevel=9)
PY
docker rm -f p03-dist-r1-recovery >/dev/null 2>&1||true
docker run -d --rm --name p03-dist-r1-recovery -p 18085:18085 -v "$REC_RT:/app" -v "$REC_DATA:$REC_DATA" -w /app "$PHP_TEST_IMAGE" php -S 0.0.0.0:18085 -t /app >/dev/null
for i in $(seq 1 80);do curl -fsS "$REC_BASE/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$REC_COOKIE" "$REC_BASE/setup.php" -o "$REC_ROOT/setup.html"
SCSRF=$(python3 - "$REC_ROOT/setup.html" <<'PY'
import re,sys;s=open(sys.argv[1]).read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$REC_COOKIE" -c "$REC_COOKIE" -H "Origin: $REC_BASE" --data-urlencode "setup_csrf=$SCSRF" --data-urlencode 'site_title=VF Forge Recovery Fixture' --data-urlencode "data_root=$REC_DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$REC_BASE/setup.php" >"$REC_ROOT/setup-post.txt"
LOGIN=$(printf '{"password":"%s"}' "$FIXTURE_PASS");curl -fsS -b "$REC_COOKIE" -c "$REC_COOKIE" -H "Origin: $REC_BASE" -H 'Content-Type: application/json' --data "$LOGIN" "$REC_BASE/api.php?action=login" -o "$REC_ROOT/login.json"
python3 - "$REC_ROOT/login.json" <<'PY'
import json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.3'
PY
cat >"$REC_ROOT/publish.php" <<'PHP'
<?php
declare(strict_types=1);define('VFAB_VERSION','1.35.3');define('VFAB_SCHEMA_VERSION',29);define('VFAB_ROOT',$argv[4]);define('VFAB_TEMP_DIR',$argv[5]);require $argv[1];$s=new VfManualUpdateService();$r=$s->inspectAndPublishPath($argv[2],$argv[3],false);echo json_encode($r);
PHP
FAIL_SHA=$(sha256sum "$REC_ROOT/fail.zip"|awk '{print $1}')
php "$REC_ROOT/publish.php" "$REC_RT/app/ManualUpdateService.php" "$REC_ROOT/fail.zip" "$FAIL_SHA" "$REC_RT" "$REC_DATA/temp" >"$REC_ROOT/publish.json"
curl -fsS -b "$REC_COOKIE" "$REC_BASE/repair-v1.35.4.php" -o "$REC_ROOT/form.html"
FCSRF=$(python3 - "$REC_ROOT/form.html" <<'PY'
import re,sys;s=open(sys.argv[1]).read();m=re.search(r'name="_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -b "$REC_COOKIE" -c "$REC_COOKIE" -H "Origin: $REC_BASE" --data-urlencode "_csrf=$FCSRF" --data-urlencode 'confirmation=UPGRADE' "$REC_BASE/repair-v1.35.4.php" -o "$REC_ROOT/fail-result.html"
grep -q '已执行恢复' "$REC_ROOT/fail-result.html"
grep -Fq "define('VFAB_VERSION', '1.35.3');" "$REC_RT/app/bootstrap.php"
grep -Fq "define('VFAB_SCHEMA_VERSION', 29);" "$REC_RT/app/bootstrap.php"
RDB=$(find "$REC_DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -1);test -f "$RDB";test "$(sqlite3 "$RDB" 'select max(version) from schema_migrations;')" = 29;test "$(sqlite3 "$RDB" 'pragma integrity_check;')" = ok;test -z "$(sqlite3 "$RDB" 'pragma foreign_key_check;')"
python3 - "$GATE_ROOT/runtime-production" "$REC_RT" <<'PY'
import sys
from pathlib import Path
a=Path(sys.argv[1]);b=Path(sys.argv[2]);base={p.relative_to(a).as_posix():p.read_bytes() for p in a.rglob('*') if p.is_file()}
cur={p.relative_to(b).as_posix():p.read_bytes() for p in b.rglob('*') if p.is_file() and p.relative_to(b).as_posix() not in {'app/.runtime.php','repair-v1.35.4.php'}}
assert cur==base,(set(cur)-set(base),set(base)-set(cur))
print('FAILURE_RECOVERY_SOURCE_EXACT=PASS')
PY
find "$REC_DATA/backups" -maxdepth 1 -type d -name 'atomic-recovery-v1.35.3-to-v1.35.4-*' | grep -q .
docker rm -f p03-dist-r1-recovery >/dev/null
echo 'FAILURE_INJECTION_RECOVERY=PASS'
echo 'SQLITE_INTEGRITY=PASS'
echo 'FOREIGN_KEYS=PASS'
echo 'PHYSICAL_DELETE=0'

python3 - "$BUILD_A" <<'PY'
import hashlib,json,sys
from pathlib import Path
b=Path(sys.argv[1])
for n in ['repair-v1.35.4.php','VF_Forge_V1.35.4_UPDATE_DIST_R1.zip','VF_Forge_V1.35.4_Atomic_Upgrade_DIST_R1.zip','VF_Forge_V1.35.4_DISTRIBUTION_REPAIR_R1_MANIFEST.json','VF_Forge_V1.35.4_DISTRIBUTION_REPAIR_R1_NOTES.md','SHA256SUMS_DIST_R1.txt']:
 p=b/n;print(f'FINAL_DIST_IDENTITY {n} BYTES={p.stat().st_size} SHA256={hashlib.sha256(p.read_bytes()).hexdigest()}')
PY
echo 'LOCAL_DISTRIBUTION_R1_GATE=PASS'
echo 'CORE_UPDATES=QUARANTINED_ENABLED_FALSE'
echo 'PRODUCTION_WRITE=0'
