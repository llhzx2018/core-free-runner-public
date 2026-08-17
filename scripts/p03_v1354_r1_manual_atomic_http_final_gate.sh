#!/usr/bin/env bash
set -Eeuo pipefail

: "${UPDATE_ASSET_ID:?}"
: "${UPDATE_BYTES:?}"
: "${UPDATE_SHA256:?}"
: "${ORIGINAL_UPDATE_ASSET_ID:?}"
: "${ORIGINAL_UPDATE_SHA256:?}"
: "${GATE_ROOT:?}"
: "${GH_TOKEN:?}"

BASE_GATE="harness/scripts/p03_v1354_dist_r1_local_gate.sh"
PATCHED_GATE="$RUNNER_TEMP/p03_v1354_r1_manual_http_patched_gate.sh"
cp "$BASE_GATE" "$PATCHED_GATE"

python3 - "$PATCHED_GATE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')

marker="echo 'ORIGINAL_IMMUTABLE_RELEASE_INPUT=PASS'\n"
assert s.count(marker)==1
remote=r'''echo 'ORIGINAL_IMMUTABLE_RELEASE_INPUT=PASS'
REMOTE_UPDATE="$CORRECTIVE_ROOT/VF_Forge_V1.35.4_UPDATE_DIST_R1_REMOTE.zip"
gh api -H 'Accept: application/octet-stream' "/repos/llhzx2018/vf-forge/releases/assets/$UPDATE_ASSET_ID" > "$REMOTE_UPDATE"
test "$(stat -c%s "$REMOTE_UPDATE")" = "$UPDATE_BYTES"
test "$(sha256sum "$REMOTE_UPDATE"|awk '{print $1}')" = "$UPDATE_SHA256"
unzip -t "$REMOTE_UPDATE" >/dev/null
test "$(unzip -Z1 "$REMOTE_UPDATE")" = 'repair-v1.35.4.php'
echo "REMOTE_R1_ASSET=PASS id=$UPDATE_ASSET_ID bytes=$(stat -c%s "$REMOTE_UPDATE") sha256=$(sha256sum "$REMOTE_UPDATE"|awk '{print $1}')"
'''
s=s.replace(marker,remote,1)

cmp_marker="echo 'UPDATE_DIST_R1_EQ_ATOMIC_DIST_R1=PASS'\n"
assert s.count(cmp_marker)==1
s=s.replace(cmp_marker,cmp_marker+'''cmp "$REMOTE_UPDATE" "$BUILD_A/VF_Forge_V1.35.4_UPDATE_DIST_R1.zip"\necho 'REMOTE_R1_EQ_DETERMINISTIC_BUILD=PASS'\n''',1)

start=s.index("replacement=r'''cat >\"$GATE_ROOT/publish-corrective.php\"")
end_marker="print('INTEGRATED_N_MINUS_1_ACCEPTANCE=PASS')\nPY'''"
end=s.index(end_marker,start)+len(end_marker)
http_replacement=r"""replacement=r'''echo 'MANUAL_HTTP_BRIDGE_BEGIN'
# The login immediately above this insertion is the exact V1.35.3 HTTP admin login.
echo 'HTTP_ADMIN_AUTH=PASS'

# Unauthenticated multipart upload must be denied before business processing.
curl -sS -i -H "Origin: $UP_BASE" \
  -F "_csrf=anonymous" -F "expected_sha256=$CORRECTIVE_SHA" \
  -F "atomic_zip=@$CORRECTIVE_UPDATE;filename=VF_Forge_V1.35.4_UPDATE_DIST_R1.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-unauth.txt"
grep -Eq '^HTTP/.* 401' "$GATE_ROOT/http-neg-unauth.txt"
grep -q 'AUTH_REQUIRED' "$GATE_ROOT/http-neg-unauth.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_UNAUTHENTICATED_UPLOAD=DENY_PASS'

# Authenticated GET proves the real maintenance UI and supplies its real form CSRF.
curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" "$UP_BASE/maintenance.php" -o "$GATE_ROOT/http-maintenance-get.html"
grep -q '系统维护' "$GATE_ROOT/http-maintenance-get.html"
grep -q 'VF Forge V1.35.3 · Schema 29' "$GATE_ROOT/http-maintenance-get.html"
MCSRF=$(python3 - "$GATE_ROOT/http-maintenance-get.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
test -n "$MCSRF"
echo 'HTTP_CSRF_FORM=PASS'

# Missing CSRF must be rejected with 419.
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "expected_sha256=$CORRECTIVE_SHA" \
  -F "atomic_zip=@$CORRECTIVE_UPDATE;filename=VF_Forge_V1.35.4_UPDATE_DIST_R1.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-csrf.txt"
grep -Eq '^HTTP/.* 419' "$GATE_ROOT/http-neg-csrf.txt"
grep -q 'CSRF_FAILED' "$GATE_ROOT/http-neg-csrf.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_MISSING_CSRF=DENY_PASS'

# Wrong expected SHA must fail closed.
BADSHA=$(printf '0%.0s' $(seq 1 64))
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "_csrf=$MCSRF" -F "expected_sha256=$BADSHA" \
  -F "atomic_zip=@$CORRECTIVE_UPDATE;filename=VF_Forge_V1.35.4_UPDATE_DIST_R1.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-sha.txt"
grep -q 'Atomic ZIP SHA-256 与输入值不一致，已拒绝执行。' "$GATE_ROOT/http-neg-sha.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_WRONG_SHA=DENY_PASS'

# The immutable original broken V1.35.4 UPDATE must be rejected for its exact compatibility defect.
ORIGINAL_SHA=$(sha256sum "$ORIGINAL_UPDATE"|awk '{print $1}')
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "_csrf=$MCSRF" -F "expected_sha256=$ORIGINAL_SHA" \
  -F "atomic_zip=@$ORIGINAL_UPDATE;filename=VF_Forge_V1.35.4_UPDATE.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-original.txt"
grep -q 'Atomic repair 缺少 VFF_ATOMIC_ALLOWED。' "$GATE_ROOT/http-neg-original.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_ORIGINAL_BROKEN_UPDATE=DENY_PASS exact=VFF_ATOMIC_ALLOWED_MISSING'

# Build test-only negative derivatives from the downloaded R1 repair.
unzip -p "$CORRECTIVE_UPDATE" repair-v1.35.4.php >"$GATE_ROOT/r1-repair.php"
python3 - "$GATE_ROOT/r1-repair.php" "$GATE_ROOT/wrong-source.zip" "$GATE_ROOT/unsafe.zip" <<'PY'
from pathlib import Path
import sys,zipfile
src=Path(sys.argv[1]).read_text(encoding='utf-8')
old='const VFF_ATOMIC_ALLOWED=["1.35.3"];'
assert src.count(old)==1
wrong=src.replace(old,'const VFF_ATOMIC_ALLOWED=["1.35.2"];',1).encode()
with zipfile.ZipFile(sys.argv[2],'w',zipfile.ZIP_DEFLATED) as z:z.writestr('repair-v1.35.4.php',wrong)
with zipfile.ZipFile(sys.argv[3],'w',zipfile.ZIP_DEFLATED) as z:z.writestr('../repair-v1.35.4.php',src.encode())
PY
WRONG_SOURCE_SHA=$(sha256sum "$GATE_ROOT/wrong-source.zip"|awk '{print $1}')
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "_csrf=$MCSRF" -F "expected_sha256=$WRONG_SOURCE_SHA" \
  -F "atomic_zip=@$GATE_ROOT/wrong-source.zip;filename=wrong-source.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-source.txt"
grep -q '当前版本不在 Atomic allowed source versions。' "$GATE_ROOT/http-neg-source.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_WRONG_SOURCE_VERSION=DENY_PASS'

printf 'not-a-zip\n' >"$GATE_ROOT/malformed.zip"
MALFORMED_SHA=$(sha256sum "$GATE_ROOT/malformed.zip"|awk '{print $1}')
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "_csrf=$MCSRF" -F "expected_sha256=$MALFORMED_SHA" \
  -F "atomic_zip=@$GATE_ROOT/malformed.zip;filename=malformed.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-malformed.txt"
grep -q '无法打开 Atomic ZIP。' "$GATE_ROOT/http-neg-malformed.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_MALFORMED_ZIP=DENY_PASS'

UNSAFE_SHA=$(sha256sum "$GATE_ROOT/unsafe.zip"|awk '{print $1}')
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "_csrf=$MCSRF" -F "expected_sha256=$UNSAFE_SHA" \
  -F "atomic_zip=@$GATE_ROOT/unsafe.zip;filename=unsafe.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-neg-unsafe.txt"
grep -q 'Atomic ZIP 包含不安全路径。' "$GATE_ROOT/http-neg-unsafe.txt"
test ! -e "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_NEG_UNSAFE_ZIP=DENY_PASS'
echo 'NEGATIVE_HTTP_MATRIX=PASS'

# Correct bridge: exact multipart/form-data through public/maintenance.php -> inspectAndPublishUpload().
curl -sS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" \
  -F "_csrf=$MCSRF" -F "expected_sha256=$CORRECTIVE_SHA" \
  -F "atomic_zip=@$CORRECTIVE_UPDATE;filename=VF_Forge_V1.35.4_UPDATE_DIST_R1.zip;type=application/zip" \
  "$UP_BASE/maintenance.php" >"$GATE_ROOT/http-manual-upload-response.txt"
grep -Eq '^HTTP/.* (302|303)' "$GATE_ROOT/http-manual-upload-response.txt"
grep -Eqi '^Location: repair-v1\.35\.4\.php' "$GATE_ROOT/http-manual-upload-response.txt"
test -f "$UP_RT/repair-v1.35.4.php"
REMOTE_REPAIR_SHA=$(unzip -p "$CORRECTIVE_UPDATE" repair-v1.35.4.php|sha256sum|awk '{print $1}')
test "$(sha256sum "$UP_RT/repair-v1.35.4.php"|awk '{print $1}')" = "$REMOTE_REPAIR_SHA"
grep -Fq 'const VFF_ATOMIC_ALLOWED=["1.35.3"];' "$UP_RT/repair-v1.35.4.php"
echo 'HTTP_MULTIPART_UPLOAD=PASS'
echo 'INSPECT_AND_PUBLISH_UPLOAD=PASS'
echo 'REPAIR_HANDOFF=PASS repair-v1.35.4.php'
echo 'VFF_ATOMIC_ALLOWED=["1.35.3"]'
'''
"""
s=s[:start]+http_replacement+s[end:]

old_export='export CORRECTIVE_UPDATE="$BUILD_A/VF_Forge_V1.35.4_UPDATE_DIST_R1.zip"\n'
assert s.count(old_export)==1
s=s.replace(old_export,'export CORRECTIVE_UPDATE="$REMOTE_UPDATE"\nexport ORIGINAL_UPDATE\n',1)

p.write_text(s,encoding='utf-8')
PY

chmod +x "$PATCHED_GATE"
bash -n "$PATCHED_GATE"
bash "$PATCHED_GATE"

echo 'MANUAL_ATOMIC_HTTP_FINAL_GATE=PASS'
echo 'AUTOMATIC_DISTRIBUTION=UNSUPPORTED_FOR_CORRECTIVE_REVISION_ON_V1.35.3'
echo 'MANUAL_CORRECTIVE_DISTRIBUTION=SUPPORTED_VERIFIED'
echo 'PRODUCTION_WRITE=0'
