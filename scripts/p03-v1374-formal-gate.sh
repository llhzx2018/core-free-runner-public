#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo P03_V1374_FORMAL_GATE_ERROR_LINE=$LINENO' ERR
: "${RUNNER_TEMP:?}"
: "${PHP_TEST_IMAGE:?}"
: "${FIXTURE_PASS:?}"

PRODUCT="$PWD/product"
OLD="$PWD/old"
CANDIDATE='b215f510a543ca5cf85af9e87257e2acb63d74ab'
BASE_MAIN='cc9a6da445240534016d08e148aa8a28c11be241'
OLD_SOURCE='29580b62a0839ee3453ccf0cf8a4902bdf3cd8ec'
TARGET='1.37.4'
SOURCE='1.37.3'
SCHEMA='30'
OUTA="$PRODUCT/build/v1374-a"
OUTB="$PRODUCT/build/v1374-b"
TARGET_RUNTIME="$RUNNER_TEMP/v1374-target-runtime"
OLD_RUNTIME="$RUNNER_TEMP/v1374-old-runtime"

log(){ printf '\n== %s ==\n' "$*"; }

log 'Exact source / release identity fence'
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C "$OLD" rev-parse HEAD)" = "$OLD_SOURCE"
test "$(cat "$PRODUCT/VERSION")" = "$TARGET"
test "$(cat "$PRODUCT/database/schema/SCHEMA_VERSION")" = "$SCHEMA"
grep -Fq "define('VFAB_VERSION', '1.37.4');" "$PRODUCT/src/app/bootstrap.php"
grep -Fq "define('VFAB_SCHEMA_VERSION', 30);" "$PRODUCT/src/app/bootstrap.php"
grep -Fq "TARGET_VERSION='1.37.4'" "$PRODUCT/scripts/build_atomic.py"
grep -Fq "ALLOWED_SOURCES=['1.37.3']" "$PRODUCT/scripts/build_atomic.py"
python3 - "$PRODUCT/VF_PROJECT.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
assert d['project_id']=='P03' and d['schema_version']==30
assert d['production_version']=='1.37.3'
assert d['working_version']==d['candidate_version']=='1.37.4'
assert d['production_write']=='NO'
assert d['version_semantics']['allowed_source_versions']==['1.37.3']
assert d['verification']['common_baseline_v2_runtime_gate_run_id']==33098729384
assert d['verification']['common_baseline_v2_final_gate_run_id']==33099096264
PY
printf '%s\n' CHANGELOG.md VERSION VF_PROJECT.json scripts/build_atomic.py src/app/bootstrap.php >"$RUNNER_TEMP/expected-files"
git -C "$PRODUCT" diff --name-only "$BASE_MAIN".."$CANDIDATE" | sort >"$RUNNER_TEMP/actual-files"
sort -o "$RUNNER_TEMP/expected-files" "$RUNNER_TEMP/expected-files"
diff -u "$RUNNER_TEMP/expected-files" "$RUNNER_TEMP/actual-files"
echo P03_V1374_EXACT_SOURCE_FENCE=PASS

log 'Syntax / source / schema / project intelligence contracts'
cd "$PRODUCT"
python3 scripts/repo_health.py .
python3 tests/integration/source_integrity_test.py
python3 tests/unit/schema_contract_test.py
python3 tests/unit/project_intelligence_contract_test.py
python3 tests/unit/project_intelligence_mcp_contract_test.py
python3 tests/integration/schema_sqlite_test.py
find src public -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$RUNNER_TEMP/p03-v1374-php-lint.log"
node --check public/assets/app.js
node --check public/assets/experience.js
node --check public/assets/project-intelligence.js
echo P03_V1374_SOURCE_CONTRACTS=PASS

log 'Build target / old runtimes'
rm -rf "$TARGET_RUNTIME" "$OLD_RUNTIME" "$OUTA" "$OUTB"
python3 scripts/build_runtime.py "$TARGET_RUNTIME" >/dev/null
python3 "$OLD/scripts/build_runtime.py" "$OLD_RUNTIME" >/dev/null
test -f "$TARGET_RUNTIME/app/bootstrap.php"
test -f "$OLD_RUNTIME/app/bootstrap.php"
grep -Fq "define('VFAB_VERSION', '1.37.4');" "$TARGET_RUNTIME/app/bootstrap.php"
grep -Fq "define('VFAB_VERSION', '1.37.3');" "$OLD_RUNTIME/app/bootstrap.php"
docker run --rm -v "$TARGET_RUNTIME:/app" -w /app "$PHP_TEST_IMAGE" php cli/check-requirements.php
echo P03_V1374_RUNTIME_BUILD=PASS

log 'Common Product Baseline V2 current runtime'
BASELINE_OUT="$RUNNER_TEMP/p03-v1374-baseline.txt"
docker run --rm -v "$TARGET_RUNTIME:/app" -w /app "$PHP_TEST_IMAGE" php cli/baseline-verify.php | tee "$BASELINE_OUT"
grep -Fq 'BASELINE=VF-COMMON-PRODUCT-BASELINE@2.0' "$BASELINE_OUT"
grep -Fq 'PROFILE=PERSONAL_SINGLE_ADMIN' "$BASELINE_OUT"
grep -Fq 'DRIFT_COUNT=0' "$BASELINE_OUT"
grep -Fq 'UNKNOWN_COUNT=0' "$BASELINE_OUT"
echo P03_V1374_COMMON_BASELINE_V2=PASS

log 'Fresh install / data / backup-restore / MCP regression'
cp tests/maintenance/current_reverify.sh "$RUNNER_TEMP/p03-v1374-current-reverify.sh"
python3 - "$RUNNER_TEMP/p03-v1374-current-reverify.sh" "$TARGET" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); version=sys.argv[2]
s=p.read_text(encoding='utf-8')
s=s.replace("assert d['ok'] and d['version']=='1.35.0'",f"assert d['ok'] and d['version']=='{version}'")
p.write_text(s,encoding='utf-8')
PY
bash "$RUNNER_TEMP/p03-v1374-current-reverify.sh"
bash tests/maintenance/project_intelligence_mcp.sh
echo P03_V1374_FRESH_MCP=PASS

log 'Deterministic Atomic release build A/B'
python3 scripts/build_atomic.py --base-runtime "$OLD_RUNTIME" --target-runtime "$TARGET_RUNTIME" --output "$OUTA" >/dev/null
python3 scripts/build_atomic.py --base-runtime "$OLD_RUNTIME" --target-runtime "$TARGET_RUNTIME" --output "$OUTB" >/dev/null
for f in VF_Forge_V1.37.4_Atomic_Upgrade.zip SOURCE_MANIFEST.txt; do
  test -f "$OUTA/$f"; test -f "$OUTB/$f"; cmp "$OUTA/$f" "$OUTB/$f"
done
unzip -t "$OUTA/VF_Forge_V1.37.4_Atomic_Upgrade.zip" >/dev/null
unzip -l "$OUTA/VF_Forge_V1.37.4_Atomic_Upgrade.zip" | grep -Fq 'repair-v1.37.4.php'
echo P03_V1374_ATOMIC_DETERMINISTIC=PASS

log 'Real V1.37.3 -> V1.37.4 Atomic success + source/database rollback failure path'
cp tests/maintenance/v1370_atomic_e2e.sh "$RUNNER_TEMP/p03-v1374-atomic-e2e.sh"
python3 - "$RUNNER_TEMP/p03-v1374-atomic-e2e.sh" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
repls={
"3962a68bbbcfbfc5aece6a338effebcafac759a9":"29580b62a0839ee3453ccf0cf8a4902bdf3cd8ec",
"1.36.2":"1.37.3","1.37.0":"1.37.4","V1370":"V1374","v1370":"v1374",
"18170":"18174","18171":"18175"
}
for a,b in repls.items(): s=s.replace(a,b)
p.write_text(s,encoding='utf-8')
PY
export BASE_SHA="$OLD_SOURCE"
export V1374_RELEASE_DIR="$OUTA"
export V1374_TARGET_RUNTIME="$TARGET_RUNTIME"
bash "$RUNNER_TEMP/p03-v1374-atomic-e2e.sh"
echo P03_V1374_ATOMIC_E2E=PASS

log 'Browser E2E responsive regression'
RUNTIME="$RUNNER_TEMP/vf-forge-v1374-browser-runtime"
DATA_ROOT="$RUNNER_TEMP/vf-forge-v1374-browser-private"
COOKIE="$RUNNER_TEMP/vf-forge-v1374-browser-cookies"
BASE='http://127.0.0.1:18176'
rm -rf "$RUNTIME" "$DATA_ROOT" "$COOKIE"; mkdir -p "$DATA_ROOT"
python3 scripts/build_runtime.py "$RUNTIME" >/dev/null
docker rm -f vf-forge-v1374-browser-http >/dev/null 2>&1 || true
docker run -d --rm --name vf-forge-v1374-browser-http --user "$(id -u):$(id -g)" -p 18176:18176 \
  -v "$RUNTIME:/app" -v "$DATA_ROOT:$DATA_ROOT" -w /app "$PHP_TEST_IMAGE" \
  php -S 0.0.0.0:18176 -t /app >/dev/null
trap 'docker logs vf-forge-v1374-browser-http 2>/dev/null || true; docker rm -f vf-forge-v1374-browser-http >/dev/null 2>&1 || true' EXIT
ready=0
for i in $(seq 1 80); do if curl -fsS "$BASE/setup.php" >/dev/null 2>&1; then ready=1; break; fi; sleep .25; done
test "$ready" = 1
curl -fsS -c "$COOKIE" "$BASE/setup.php" -o "$RUNNER_TEMP/v1374-browser-setup.html"
CSRF=$(python3 - "$RUNNER_TEMP/v1374-browser-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" \
  --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=VF Forge V1.37.4 Browser Fixture' \
  --data-urlencode "data_root=$DATA_ROOT" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" \
  "$BASE/setup.php" >"$RUNNER_TEMP/v1374-browser-setup-post.txt"
grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$RUNNER_TEMP/v1374-browser-setup-post.txt"
test "$(sqlite3 "$DATA_ROOT/database/"*.sqlite 'pragma integrity_check;')" = ok
BASE_URL="$BASE" FIXTURE_PASS="$FIXTURE_PASS" node tests/maintenance/browser_reverify.mjs
docker rm -f vf-forge-v1374-browser-http >/dev/null
trap - EXIT
echo P03_V1374_BROWSER_E2E=PASS

log 'Deterministic FULL clean-install artifact + checksums'
python3 - "$TARGET_RUNTIME" "$OUTA/VF_Forge_V1.37.4_FULL.zip" "$OUTB/VF_Forge_V1.37.4_FULL.zip" <<'PY'
from pathlib import Path
import sys,zipfile,stat
root=Path(sys.argv[1])
def build(dst):
    dst=Path(dst); dst.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(dst,'w') as z:
        for p in sorted(x for x in root.rglob('*') if x.is_file() and not x.is_symlink()):
            rel=p.relative_to(root).as_posix(); b=p.read_bytes()
            i=zipfile.ZipInfo(rel,date_time=(2020,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(i,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
for x in sys.argv[2:]: build(x)
PY
cmp "$OUTA/VF_Forge_V1.37.4_FULL.zip" "$OUTB/VF_Forge_V1.37.4_FULL.zip"
unzip -t "$OUTA/VF_Forge_V1.37.4_FULL.zip" >/dev/null
python3 - "$OUTA" "$CANDIDATE" <<'PY'
from pathlib import Path
import hashlib,json,sys
out=Path(sys.argv[1]); sha=sys.argv[2]
arts=['VF_Forge_V1.37.4_Atomic_Upgrade.zip','VF_Forge_V1.37.4_FULL.zip','SOURCE_MANIFEST.txt']
rows=[]
for n in arts:
 p=out/n; b=p.read_bytes(); rows.append({'name':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(out/'P03_V1.37.4_RELEASE_MANIFEST.json').write_text(json.dumps({'schema':'vf-p03-release/1','project_id':'P03','version':'1.37.4','source_version':'1.37.3','schema_version':30,'candidate_source_sha':sha,'production_changed':False,'artifacts':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
allfiles=[out/x for x in arts]+[out/'P03_V1.37.4_RELEASE_MANIFEST.json']
(out/'RELEASE_SHA256SUMS.txt').write_text(''.join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in allfiles),encoding='utf-8')
PY
(cd "$OUTA" && sha256sum -c RELEASE_SHA256SUMS.txt)
echo P03_V1374_ARTIFACT_SET=PASS

cat >"$RUNNER_TEMP/P03-V1.37.4-FORMAL-GATE.env" <<EOF
P03_V1374_EXACT_SOURCE=$CANDIDATE
P03_V1374_MACHINE=PASS
P03_V1374_SCHEMA=$SCHEMA
P03_V1374_BASELINE_V2=PASS
P03_V1374_DRIFT=0
P03_V1374_UNKNOWN=0
P03_V1374_ATOMIC_FROM=$SOURCE
P03_V1374_ATOMIC_TO=$TARGET
P03_V1374_ATOMIC_SUCCESS=PASS
P03_V1374_ROLLBACK=PASS
P03_V1374_BROWSER=PASS
P03_V1374_RELEASE=NO
P03_V1374_PRODUCTION=NO
EOF
cp "$RUNNER_TEMP/P03-V1.37.4-FORMAL-GATE.env" "$OUTA/"
echo 'P03_V1374_FORMAL_GATE=PASS'
