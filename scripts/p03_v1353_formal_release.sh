#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_TOKEN:?}"
: "${CANDIDATE_COMMIT:?}"
: "${CANDIDATE_TREE:?}"
: "${PRODUCTION_COMMIT:?}"
: "${GATE_FULL_SHA:?}"
: "${GATE_FULL_BYTES:?}"
: "${GATE_UPDATE_SHA:?}"
: "${GATE_UPDATE_BYTES:?}"
: "${GATE_ATOMIC_SHA:?}"
: "${GATE_ATOMIC_BYTES:?}"
: "${GATE_SOURCE_MANIFEST_SHA:?}"

REPO='llhzx2018/vf-forge'
TAG='v1.35.3'
API="https://api.github.com/repos/$REPO"
AUTH=(-H 'Accept: application/vnd.github+json' -H "Authorization: Bearer $VF_RELEASE_TOKEN" -H 'X-GitHub-Api-Version: 2022-11-28')
ROOT='/tmp/p03-v1353-formal-release'
rm -rf "$ROOT"
mkdir -p "$ROOT"
trap 'rm -rf "$ROOT"; rm -rf p03; echo EPHEMERAL_RELEASE_CLEANUP=PASS' EXIT

# Exact candidate and source contract.
test -d p03/.git
test "$(git -C p03 rev-parse HEAD)" = "$CANDIDATE_COMMIT"
test "$(git -C p03 rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(tr -d '\r\n' < p03/VERSION)" = '1.35.3'
test "$(tr -d '\r\n' < p03/database/schema/SCHEMA_VERSION)" = '29'
grep -Fq "define('VFAB_VERSION', '1.35.3');" p03/src/app/bootstrap.php
grep -Fq "define('VFAB_SCHEMA_VERSION', 29);" p03/src/app/bootstrap.php
grep -Fq "TARGET_VERSION='1.35.3'" p03/scripts/build_atomic.py
grep -Fq "ALLOWED_SOURCES=['1.35.2']" p03/scripts/build_atomic.py
test -z "$(git -C p03 diff "$PRODUCTION_COMMIT"..HEAD -- database/schema database/migrations)"
ORIGIN=$(git -C p03 config --get remote.origin.url)
case "$ORIGIN" in *x-access-token*|*github_pat_*|*ghp_*) echo 'Credential persisted in origin URL' >&2; exit 80;; esac
if git -C p03 ls-files | grep -Ei '(^|/)(PRIVATE_DATA|storage/private|uploads|backup|backups|cache|session|sessions|logs|tmp)(/|$)|\.sqlite3?$|\.db$|(^|/)\.env$'; then
  echo 'Tracked private/runtime data found' >&2; exit 81
fi
echo EXACT_CANDIDATE_RELEASE_IDENTITY=PASS

cd p03
git worktree add --detach "$ROOT/production-worktree" "$PRODUCTION_COMMIT" >/dev/null
python3 "$ROOT/production-worktree/scripts/build_runtime.py" "$ROOT/runtime-production" >/dev/null
python3 scripts/build_runtime.py "$ROOT/runtime-target" >/dev/null
test "$(find "$ROOT/runtime-production" -type f | wc -l | tr -d ' ')" = '35'
test "$(find "$ROOT/runtime-target" -type f | wc -l | tr -d ' ')" = '37'
grep -Fq "define('VFAB_VERSION', '1.35.2');" "$ROOT/runtime-production/app/bootstrap.php"
grep -Fq "define('VFAB_VERSION', '1.35.3');" "$ROOT/runtime-target/app/bootstrap.php"

build_full(){
  python3 - "$ROOT/runtime-target" "$1" <<'PY'
import sys,zipfile
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2])
with zipfile.ZipFile(out,'w') as z:
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink(): continue
        rel=p.relative_to(root).as_posix()
        zi=zipfile.ZipInfo(rel,date_time=(2020,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED; zi.external_attr=(0o100644 & 0xFFFF)<<16
        z.writestr(zi,p.read_bytes(),compresslevel=9)
PY
}

for N in a b; do
  mkdir -p "$ROOT/build-$N"
  build_full "$ROOT/build-$N/VF_Forge_V1.35.3_FULL.zip"
  python3 scripts/build_atomic.py --base-runtime "$ROOT/runtime-production" --target-runtime "$ROOT/runtime-target" --output "$ROOT/build-$N" >"$ROOT/build-$N/build-atomic.json"
  cp "$ROOT/build-$N/VF_Forge_V1.35.3_Atomic_Upgrade.zip" "$ROOT/build-$N/VF_Forge_V1.35.3_UPDATE.zip"
done
for F in VF_Forge_V1.35.3_FULL.zip VF_Forge_V1.35.3_UPDATE.zip VF_Forge_V1.35.3_Atomic_Upgrade.zip; do cmp "$ROOT/build-a/$F" "$ROOT/build-b/$F"; done
OUT="$ROOT/build-a"

FULL_SHA=$(sha256sum "$OUT/VF_Forge_V1.35.3_FULL.zip"|awk '{print $1}'); FULL_BYTES=$(stat -c%s "$OUT/VF_Forge_V1.35.3_FULL.zip")
UPDATE_SHA=$(sha256sum "$OUT/VF_Forge_V1.35.3_UPDATE.zip"|awk '{print $1}'); UPDATE_BYTES=$(stat -c%s "$OUT/VF_Forge_V1.35.3_UPDATE.zip")
ATOMIC_SHA=$(sha256sum "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip"|awk '{print $1}'); ATOMIC_BYTES=$(stat -c%s "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip")
test "$FULL_SHA" = "$GATE_FULL_SHA"; test "$FULL_BYTES" = "$GATE_FULL_BYTES"
test "$UPDATE_SHA" = "$GATE_UPDATE_SHA"; test "$UPDATE_BYTES" = "$GATE_UPDATE_BYTES"
test "$ATOMIC_SHA" = "$GATE_ATOMIC_SHA"; test "$ATOMIC_BYTES" = "$GATE_ATOMIC_BYTES"
test "$UPDATE_SHA" = "$ATOMIC_SHA"; test "$UPDATE_BYTES" = "$ATOMIC_BYTES"
echo FORMAL_BUILD_EQUALS_GATE_BUILD=PASS

# ZIP/path/privacy/update/atomic contract.
unzip -t "$OUT/VF_Forge_V1.35.3_FULL.zip" >/dev/null
unzip -t "$OUT/VF_Forge_V1.35.3_UPDATE.zip" >/dev/null
unzip -t "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" >/dev/null
test "$(unzip -Z1 "$OUT/VF_Forge_V1.35.3_FULL.zip" | wc -l | tr -d ' ')" = '37'
test "$(unzip -Z1 "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip")" = 'repair-v1.35.3.php'
unzip -p "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" repair-v1.35.3.php >"$OUT/repair-v1.35.3.php"
php -l "$OUT/repair-v1.35.3.php" >/dev/null
grep -Fq "const VFF_PACKAGE_ID='vf-forge';" "$OUT/repair-v1.35.3.php"
grep -Fq "const VFF_PACKAGE_TYPE='app';" "$OUT/repair-v1.35.3.php"
grep -Fq "const VFF_ATOMIC_TARGET='1.35.3';" "$OUT/repair-v1.35.3.php"
grep -Fq 'const VFF_ATOMIC_SCHEMA=29;' "$OUT/repair-v1.35.3.php"
grep -Fq 'const VFF_ATOMIC_ALLOWED=["1.35.2"];' "$OUT/repair-v1.35.3.php"
python3 - "$OUT/VF_Forge_V1.35.3_FULL.zip" <<'PY'
import re,sys,zipfile
z=zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    n=i.filename.replace('\\','/')
    assert n and not n.startswith('/') and not re.match(r'^[A-Za-z]:',n) and '..' not in n.split('/')
    assert not re.search(r'(^|/)(PRIVATE_DATA|storage/private|uploads|backup|backups|cache|session|sessions|logs|tmp)(/|$)',n,re.I)
    assert not re.search(r'\.(sqlite3?|db)$|(^|/)\.env$',n,re.I)
print('FORMAL_FULL_PATH_PRIVACY_PASS',len(z.infolist()))
PY

# Exact target source manifest, same contract as Atomic payload.
python3 - "$ROOT/runtime-target" "$OUT/VF_Forge_V1.35.3_SOURCE_MANIFEST.txt" <<'PY'
import hashlib,re,sys
from pathlib import Path
root=Path(sys.argv[1]); rows=[]
for p in sorted(root.rglob('*')):
    if not p.is_file() or p.is_symlink(): continue
    rel=p.relative_to(root).as_posix(); top=rel.split('/',1)[0]
    if rel=='app/.runtime.php' or re.match(r'^repair-v[^/]+\.php$',rel): continue
    if rel in {'api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','robots.txt','setup.php','share.php'} or top in {'app','assets','cli','mcp'}:
        b=p.read_bytes(); rows.append(f'{rel}\t{len(b)}\t{hashlib.sha256(b).hexdigest()}')
text='\n'.join(rows)+'\n'; Path(sys.argv[2]).write_text(text,encoding='utf-8',newline='\n')
print('SOURCE_MANIFEST_FILES',len(rows))
PY
SRC_SHA=$(sha256sum "$OUT/VF_Forge_V1.35.3_SOURCE_MANIFEST.txt"|awk '{print $1}')
test "$SRC_SHA" = "$GATE_SOURCE_MANIFEST_SHA"

# Release notes and release manifest.
cat >"$OUT/VF_Forge_V1.35.3_RELEASE_NOTES.md" <<'EOF'
# VF Forge V1.35.3

Post-Seal 产品健康与 UA/UI 重构正式候选版本。Schema 保持 29，不执行数据模型迁移。

- 完成全系统健康审计与 A 类 Current Authority / Runtime Manifest 漂移清零。
- 一级导航重构为：工作台 / 项目 / 资产 / 取用入口 / 搜索；治理入口保留需要确认 / 设置。
- 资产提升为高频跨项目浏览与取回入口；只读详情采用 Context Drawer，写操作保持 Modal / 专用流程。
- 新增八档响应式合同：390 / 480 / 640 / 768 / 1024 / 1280 / 1440 / 1920。
- 新增跨对象 Semantic Consistency Gate，覆盖 Project Slot / Artifact Family / Snapshot / Release / Recipe。
- Exact Candidate、Browser E2E、Responsive、UA/UI、Formal Artifact Gate 均已 PASS。
- 正式直接升级来源锁定 V1.35.2，Schema 29 → 29；保留 Backup / Restore / Atomic Rollback / Fail-Closed 合同。
- 本 Release 不代表 Production 已升级；Production 仍保持 V1.35.2，等待真实在线升级授权。
EOF

RELEASED_AT=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
REPAIR_SHA=$(sha256sum "$OUT/repair-v1.35.3.php"|awk '{print $1}'); REPAIR_BYTES=$(stat -c%s "$OUT/repair-v1.35.3.php")
python3 - "$OUT/VF_Forge_V1.35.3_RELEASE_MANIFEST.json" "$RELEASED_AT" "$FULL_SHA" "$FULL_BYTES" "$UPDATE_SHA" "$UPDATE_BYTES" "$ATOMIC_SHA" "$ATOMIC_BYTES" "$REPAIR_SHA" "$REPAIR_BYTES" "$SRC_SHA" <<'PY'
import json,sys
p,at,fs,fb,us,ub,as_,ab,rs,rb,ss=sys.argv[1:]
d={
 'schema_version':'1.0','project_id':'P03','component_id':'APP','version':'1.35.3','schema':29,
 'candidate_commit':'370c699d4e105a9035393bcfb4e0aef982131cde','candidate_tree':'2652978e8f31f7d3fcc1ec3a315be15c0ce4066d',
 'production_baseline':'c074678fdad9856addb3d290b555b723ce7013ec','from_versions':['1.35.2'],'schema_from':'29','schema_to':'29',
 'release_tag':'v1.35.3','runtime_file_count':37,'source_manifest_sha256':ss,'released_at':at,
 'formal_gate_run':'31942079711','formal_build_equal_gate_build':True,
 'assets':{
  'full':{'name':'VF_Forge_V1.35.3_FULL.zip','bytes':int(fb),'sha256':fs},
  'update':{'name':'VF_Forge_V1.35.3_UPDATE.zip','bytes':int(ub),'sha256':us},
  'atomic':{'name':'VF_Forge_V1.35.3_Atomic_Upgrade.zip','bytes':int(ab),'sha256':as_},
  'repair':{'name':'repair-v1.35.3.php','bytes':int(rb),'sha256':rs},
  'source_manifest':{'name':'VF_Forge_V1.35.3_SOURCE_MANIFEST.txt','sha256':ss}
 }
}
open(p,'w',encoding='utf-8',newline='\n').write(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
PY

cd "$OUT"
sha256sum \
  VF_Forge_V1.35.3_FULL.zip \
  VF_Forge_V1.35.3_UPDATE.zip \
  VF_Forge_V1.35.3_Atomic_Upgrade.zip \
  repair-v1.35.3.php \
  VF_Forge_V1.35.3_RELEASE_MANIFEST.json \
  VF_Forge_V1.35.3_SOURCE_MANIFEST.txt \
  VF_Forge_V1.35.3_RELEASE_NOTES.md > SHA256SUMS.txt
sha256sum -c SHA256SUMS.txt >/dev/null

# Secret gate: the live token itself must not be present in any release file.
for F in VF_Forge_V1.35.3_FULL.zip VF_Forge_V1.35.3_UPDATE.zip VF_Forge_V1.35.3_Atomic_Upgrade.zip repair-v1.35.3.php VF_Forge_V1.35.3_RELEASE_MANIFEST.json VF_Forge_V1.35.3_SOURCE_MANIFEST.txt VF_Forge_V1.35.3_RELEASE_NOTES.md SHA256SUMS.txt; do
  if grep -aFq "$VF_RELEASE_TOKEN" "$F"; then echo "SECRET_LEAK_IN_$F" >&2; exit 82; fi
done
echo FORMAL_RELEASE_SECRET_PRIVACY_GATE=PASS

# Preflight: tag/release must not already exist.
TAG_CODE=$(curl -sS -o "$ROOT/tag-pre.json" -w '%{http_code}' "${AUTH[@]}" "$API/git/ref/tags/$TAG")
if [ "$TAG_CODE" != '404' ]; then echo "Tag already exists before release: HTTP $TAG_CODE" >&2; exit 83; fi
REL_CODE=$(curl -sS -o "$ROOT/release-pre.json" -w '%{http_code}' "${AUTH[@]}" "$API/releases/tags/$TAG")
if [ "$REL_CODE" != '404' ]; then echo "Release already exists before release: HTTP $REL_CODE" >&2; exit 84; fi

# Create immutable lightweight tag at exact Candidate commit.
python3 - "$ROOT/tag-create.json" "$CANDIDATE_COMMIT" <<'PY'
import json,sys
open(sys.argv[1],'w').write(json.dumps({'ref':'refs/tags/v1.35.3','sha':sys.argv[2]},separators=(',',':')))
PY
curl -fsS -X POST "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary @"$ROOT/tag-create.json" "$API/git/refs" >"$ROOT/tag-created.json"
TAG_SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["object"]["sha"])' "$ROOT/tag-created.json")
test "$TAG_SHA" = "$CANDIDATE_COMMIT"
echo FORMAL_TAG_CREATED_EXACT=PASS

# Create release.
python3 - "$ROOT/release-create.json" "$OUT/VF_Forge_V1.35.3_RELEASE_NOTES.md" "$CANDIDATE_COMMIT" <<'PY'
import json,sys
body=open(sys.argv[2],encoding='utf-8').read()
d={'tag_name':'v1.35.3','target_commitish':sys.argv[3],'name':'VF Forge V1.35.3','body':body,'draft':False,'prerelease':False,'make_latest':'true'}
open(sys.argv[1],'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,separators=(',',':')))
PY
curl -fsS -X POST "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary @"$ROOT/release-create.json" "$API/releases" >"$ROOT/release-created.json"
RID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$ROOT/release-created.json")
test -n "$RID"

upload(){
  local f="$1" ct="$2" n
  n=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$f")
  curl -fsS -X POST "${AUTH[@]}" -H "Content-Type: $ct" --data-binary @"$f" "https://uploads.github.com/repos/llhzx2018/vf-forge/releases/$RID/assets?name=$n" >"$ROOT/upload-$(basename "$f").json"
}
upload VF_Forge_V1.35.3_FULL.zip application/zip
upload VF_Forge_V1.35.3_UPDATE.zip application/zip
upload VF_Forge_V1.35.3_Atomic_Upgrade.zip application/zip
upload repair-v1.35.3.php application/x-php
upload VF_Forge_V1.35.3_RELEASE_MANIFEST.json application/json
upload VF_Forge_V1.35.3_SOURCE_MANIFEST.txt text/plain
upload VF_Forge_V1.35.3_RELEASE_NOTES.md text/markdown
upload SHA256SUMS.txt text/plain

# Remote readback: exact tag and exact asset identity.
curl -fsS "${AUTH[@]}" "$API/git/ref/tags/$TAG" >"$ROOT/tag-readback.json"
test "$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["object"]["sha"])' "$ROOT/tag-readback.json")" = "$CANDIDATE_COMMIT"
curl -fsS "${AUTH[@]}" "$API/releases/tags/$TAG" >"$ROOT/release-readback.json"
python3 - "$ROOT/release-readback.json" "$OUT" <<'PY'
import hashlib,json,os,sys
r=json.load(open(sys.argv[1])); root=sys.argv[2]
assert r['tag_name']=='v1.35.3' and r['name']=='VF Forge V1.35.3' and not r['draft'] and not r['prerelease']
expected=['VF_Forge_V1.35.3_FULL.zip','VF_Forge_V1.35.3_UPDATE.zip','VF_Forge_V1.35.3_Atomic_Upgrade.zip','repair-v1.35.3.php','VF_Forge_V1.35.3_RELEASE_MANIFEST.json','VF_Forge_V1.35.3_SOURCE_MANIFEST.txt','VF_Forge_V1.35.3_RELEASE_NOTES.md','SHA256SUMS.txt']
a={x['name']:x for x in r['assets']}
assert sorted(a)==sorted(expected),(sorted(a),expected)
for n in expected:
    p=os.path.join(root,n); b=os.path.getsize(p); h=hashlib.sha256(open(p,'rb').read()).hexdigest(); x=a[n]
    assert x['size']==b,(n,x['size'],b)
    digest=x.get('digest')
    if digest is not None: assert digest=='sha256:'+h,(n,digest,h)
    print('FORMAL_ASSET',x['id'],n,b,h)
print('FORMAL_RELEASE_ID',r['id'])
print('FORMAL_RELEASE_REMOTE_READBACK=PASS')
PY

echo "FORMAL_RELEASE_ID=$RID"
echo "FORMAL_FULL_SHA=$FULL_SHA FORMAL_FULL_BYTES=$FULL_BYTES"
echo "FORMAL_UPDATE_SHA=$UPDATE_SHA FORMAL_UPDATE_BYTES=$UPDATE_BYTES"
echo "FORMAL_ATOMIC_SHA=$ATOMIC_SHA FORMAL_ATOMIC_BYTES=$ATOMIC_BYTES"
echo "FORMAL_SOURCE_MANIFEST_SHA=$SRC_SHA"
echo FORMAL_RELEASE=PASS
