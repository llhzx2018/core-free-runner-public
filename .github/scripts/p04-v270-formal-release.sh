#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_REPOSITORY="llhzx2018/vf-infra"
TARGET_COMMIT="e2fd12cce0518333d7aa15e9d5babc5db0c9043b"
TARGET_PARENT="f86d79b871cf05c90af922afeb9fca851faf7c54"
TARGET_TREE="0395a8b8b702faee2f7d2bbab7a3b65ee98915e9"
TARGET_VERSION="2.7.0"
SOURCE_COMMIT="b8d080e432ba811f6689372636022774e558ffc1"
SOURCE_TREE="181cb02c1305500006f8cfe70a0e05bdf3ad7225"
SOURCE_VERSION="2.6.0"
SCHEMA="14"
TAG="v2.7.0"
RELEASE_NAME="VF Infra V2.7.0"
EXPECTED_RUNTIME_FILES="185"
EXPECTED_RUNTIME_FINGERPRINT="996165dcadb5100fc68cd47515b28a6bc71e6e6f8b2fe7e7fe7713dcbe765401"

TARGET_DIR="$GITHUB_WORKSPACE/private-vf-infra-target"
SOURCE_DIR="$GITHUB_WORKSPACE/private-vf-infra-source"
OUT="$RUNNER_TEMP/p04-v270-formal"
ASSETS="$RUNNER_TEMP/p04-v270-assets"
EVIDENCE="$GITHUB_WORKSPACE/p04-v270-release-evidence"
rm -rf "$OUT" "$ASSETS" "$EVIDENCE"
mkdir -p "$OUT" "$ASSETS" "$EVIDENCE"

fail(){ echo "P04_V270_FORMAL_RELEASE_FAIL_CLOSED: $*" >&2; exit 91; }
sha(){ sha256sum "$1" | awk '{print $1}'; }

echo "== exact candidate/source identity =="
test "$(git -C "$TARGET_DIR" rev-parse HEAD)" = "$TARGET_COMMIT" || fail target_commit
test "$(git -C "$TARGET_DIR" rev-parse HEAD^{tree})" = "$TARGET_TREE" || fail target_tree
test "$(git -C "$TARGET_DIR" rev-parse HEAD^)" = "$TARGET_PARENT" || fail target_parent
test "$(tr -d '\r\n' < "$TARGET_DIR/VERSION")" = "$TARGET_VERSION" || fail target_version
test "$(find "$TARGET_DIR/database/migrations" -maxdepth 1 -type f -name '*.sql' | wc -l | tr -d ' ')" = "$SCHEMA" || fail target_schema

test "$(git -C "$SOURCE_DIR" rev-parse HEAD)" = "$SOURCE_COMMIT" || fail source_commit
test "$(git -C "$SOURCE_DIR" rev-parse HEAD^{tree})" = "$SOURCE_TREE" || fail source_tree
test "$(tr -d '\r\n' < "$SOURCE_DIR/VERSION")" = "$SOURCE_VERSION" || fail source_version
test "$(find "$SOURCE_DIR/database/migrations" -maxdepth 1 -type f -name '*.sql' | wc -l | tr -d ' ')" = "$SCHEMA" || fail source_schema

echo "== immutable publication preflight =="
if gh api "repos/$TARGET_REPOSITORY/git/ref/tags/$TAG" >"$OUT/preexisting-tag.json" 2>/dev/null; then
  python3 - "$OUT/preexisting-tag.json" "$TARGET_COMMIT" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d["object"]["sha"]==sys.argv[2], (d["object"]["sha"],sys.argv[2])
PY
  echo "P04_V270_TAG_PREEXISTS_EXACT=YES"
else
  echo "P04_V270_TAG_PREEXISTS_EXACT=NO"
fi
if gh api "repos/$TARGET_REPOSITORY/releases/tags/$TAG" >"$OUT/preexisting-release.json" 2>/dev/null; then
  python3 - "$OUT/preexisting-release.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d["tag_name"]=="v2.7.0" and d["name"]=="VF Infra V2.7.0"
assert d["draft"] is False and d["prerelease"] is False
if d.get("assets"): raise SystemExit("PREEXISTING_RELEASE_ASSETS_NOT_ALLOWED")
PY
  echo "P04_V270_RELEASE_PREEXISTS_EMPTY_EXACT=YES"
else
  echo "P04_V270_RELEASE_PREEXISTS_EMPTY_EXACT=NO"
fi

echo "== build exact source/target release trees =="
python3 "$SOURCE_DIR/scripts/build-release-tree.py" "$OUT/source-runtime"
python3 "$TARGET_DIR/scripts/build-release-tree.py" "$OUT/target-runtime"

python3 - "$OUT/source-runtime" "$OUT/target-runtime" "$EXPECTED_RUNTIME_FILES" "$EXPECTED_RUNTIME_FINGERPRINT" <<'PY'
from pathlib import Path
import json,sys
src,tgt=Path(sys.argv[1]),Path(sys.argv[2])
expected_count=int(sys.argv[3]); expected_fp=sys.argv[4]
assert (src/'VERSION.txt').read_text().strip()=='2.6.0'
assert (tgt/'VERSION.txt').read_text().strip()=='2.7.0'
assert len([p for p in tgt.rglob('*') if p.is_file()])==expected_count
m=json.loads((tgt/'release-manifest.json').read_text())
assert int(m['target_schema'])==14
assert m['source_fingerprint']==expected_fp,(m['source_fingerprint'],expected_fp)
print("P04_V270_RELEASE_TREE_IDENTITY_PASS")
PY

echo "== deterministic FULLs and exact runtime delta =="
python3 - "$OUT/source-runtime" "$OUT/source-full.zip" "$OUT/target-runtime" "$ASSETS/VF_Infra_V2.7.0_FULL.zip" "$OUT/payload-paths.json" <<'PY'
from pathlib import Path
import hashlib,json,os,sys,zipfile
src,srczip,tgt,tgtzip,payload=map(Path,sys.argv[1:])
def deterministic_zip(root,out):
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=True) as z:
        for f in sorted(x for x in root.rglob('*') if x.is_file()):
            rel=f.relative_to(root).as_posix()
            info=zipfile.ZipInfo(rel,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
            info.create_system=3; info.external_attr=((0o100755 if os.access(f,os.X_OK) else 0o100644)<<16)
            z.writestr(info,f.read_bytes())
def inv(root):
    return {f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in root.rglob('*') if f.is_file()}
deterministic_zip(src,srczip); deterministic_zip(tgt,tgtzip)
a,b=inv(src),inv(tgt)
deleted=sorted(set(a)-set(b))
if deleted: raise SystemExit("V270_RUNTIME_DELETIONS_UNSUPPORTED "+json.dumps(deleted))
changed=sorted(k for k in b if k not in a or a[k]!=b[k])
if 'VERSION.txt' not in changed or 'release-manifest.json' not in changed:
    raise SystemExit("V270_IDENTITY_PAYLOAD_MISSING")
payload.write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'added_or_changed':len(changed),'deleted':len(deleted),'payload_paths':changed},ensure_ascii=False))
print("P04_V270_RUNTIME_DELTA_PASS")
PY

echo "== build proven Atomic/UPDATE using exact dynamic delta =="
python3 - "$TARGET_DIR" "$OUT/target-runtime" "$OUT/update-set" "$OUT/payload-paths.json" <<'PY'
from pathlib import Path
import json,re,sys
root,runtime,out,payload=map(Path,sys.argv[1:])
paths=json.loads(payload.read_text())
source=(root/'scripts/build-v256-update-release.py').read_text(encoding='utf-8')
source=source.replace("TARGET='2.5.6'","TARGET='2.7.0'",1).replace("SOURCE='2.5.5'","SOURCE='2.6.0'",1)
source,n=re.subn(r"PAYLOAD_PATHS=\[.*?\]\n\np=", "PAYLOAD_PATHS="+repr(paths)+"\n\np=", source, count=1, flags=re.S)
if n!=1: raise SystemExit("V270_PAYLOAD_SENTINEL_DRIFT")
source=source.replace("source=source.replace('vfi251','vfi256').replace('atomic_251','atomic_256')",
                      "source=source.replace('vfi251','vfi270').replace('atomic_251','atomic_270')",1)
source=source.replace(
    "'V2.5.6 只增加正式维护通道，Schema 与业务模型保持不变。',\n    'V2.5.6 修复 Provider 计费完整性、Job 健康语义并重构 UA/UI；Schema 与远程写权限保持不变。'",
    "'V2.7.0 只增加正式维护通道，Schema 与业务模型保持不变。',\n    'V2.7.0 完成 Reference-Locked Personal Infrastructure Runtime 与最终 UI 精修；Schema 与 Provider 远程写权限保持不变。'"
)
import sys as _sys
old=_sys.argv[:]
try:
    _sys.argv=[str(root/'scripts/build-v270-formal-generated.py'),'--target-runtime',str(runtime),'--output',str(out)]
    code=compile(source,str(root/'scripts/build-v270-formal-generated.py'),'exec')
    scope={'__name__':'__main__','__file__':str(root/'scripts/build-v270-formal-generated.py')}
    exec(code,scope,scope)
finally:
    _sys.argv=old

pkg=out/'PACKAGE_MANIFEST.json'
d=json.loads(pkg.read_text(encoding='utf-8'))
d['maintenance_only']=False
d['release_kind']='product_experience_generation'
d['product_experience_generation_change']=True
d['candidate_phase']='FORMAL_CANDIDATE'
d['schema_change']=False
d['business_model_change']=False
d['provider_write_authority_change']=False
d['migration']='NONE'
pkg.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print("P04_V270_UPDATE_BUILD_PASS")
PY

cp "$OUT/update-set/VF_Infra_V2.7.0_UPDATE.zip" "$ASSETS/"
cp "$OUT/update-set/VF_Infra_V2.7.0_ATOMIC.zip" "$ASSETS/"
cp "$OUT/update-set/repair-v2.7.0.php" "$ASSETS/"
cp "$OUT/update-set/PACKAGE_MANIFEST.json" "$ASSETS/"
cp "$OUT/update-set/PRODUCTION_SOURCE_MANIFEST_EXPECTED.txt" "$ASSETS/"
python3 - "$OUT/update-set" <<'PY'
from pathlib import Path
import hashlib,sys
r=Path(sys.argv[1])
names=['VF_Infra_V2.7.0_ATOMIC.zip','VF_Infra_V2.7.0_UPDATE.zip','repair-v2.7.0.php','PACKAGE_MANIFEST.json','PRODUCTION_SOURCE_MANIFEST_EXPECTED.txt']
(r/'SHA256SUMS.txt').write_text(''.join(f"{hashlib.sha256((r/n).read_bytes()).hexdigest()}  {n}\n" for n in names),encoding='utf-8')
PY
cp "$OUT/update-set/SHA256SUMS.txt" "$ASSETS/"

cmp -s "$ASSETS/VF_Infra_V2.7.0_UPDATE.zip" "$ASSETS/VF_Infra_V2.7.0_ATOMIC.zip" || fail update_atomic_not_identical
(cd "$ASSETS" && sha256sum -c SHA256SUMS.txt)

UPDATE_SHA="$(sha "$ASSETS/VF_Infra_V2.7.0_UPDATE.zip")"
python3 "$TARGET_DIR/scripts/validate-online-atomic-package.py" --runtime "$OUT/target-runtime" --zip "$ASSETS/VF_Infra_V2.7.0_UPDATE.zip" --version 2.7.0 --sha256 "$UPDATE_SHA"

if python3 "$TARGET_DIR/scripts/validate-online-atomic-package.py" --runtime "$OUT/target-runtime" --zip "$ASSETS/VF_Infra_V2.7.0_UPDATE.zip" --version 2.7.0 --sha256 "0000000000000000000000000000000000000000000000000000000000000000"; then
  fail negative_sha_gate_did_not_fail
else
  echo "P04_V270_NEGATIVE_SHA_GATE_PASS"
fi

sed "s/'2\.6\.0'/'2.7.0'/g" "$TARGET_DIR/scripts/full-runtime-vs-update-result-source-exact-gate.py" > "$OUT/source-exact-v270.py"
python3 "$OUT/source-exact-v270.py" --baseline-full "$OUT/source-full.zip" --candidate-full "$ASSETS/VF_Infra_V2.7.0_FULL.zip" --candidate-update "$ASSETS/VF_Infra_V2.7.0_UPDATE.zip"

echo "== manifest / release metadata =="
python3 - "$OUT" "$ASSETS" "$TARGET_COMMIT" "$TARGET_TREE" "$EXPECTED_RUNTIME_FILES" "$EXPECTED_RUNTIME_FINGERPRINT" <<'PY'
from pathlib import Path
import hashlib,json,sys
out,assets=Path(sys.argv[1]),Path(sys.argv[2])
commit,tree=sys.argv[3],sys.argv[4]; count=int(sys.argv[5]); fp=sys.argv[6]
pkg=json.loads((assets/'PACKAGE_MANIFEST.json').read_text())
assert pkg['version']=='2.7.0'
assert pkg['allowed_source_versions']==['2.6.0']
assert int(pkg['schema'])==14 and pkg['schema_change'] is False
assert pkg['maintenance_only'] is False and pkg['release_kind']=='product_experience_generation'
assert pkg['candidate_phase']=='FORMAL_CANDIDATE'
assert pkg['provider_write_authority_change'] is False
assert pkg['migration']=='NONE'
source_manifest=assets/'PRODUCTION_SOURCE_MANIFEST_EXPECTED.txt'
source_sha=hashlib.sha256(source_manifest.read_bytes()).hexdigest()
def meta(p): return {'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
base={'project':'P04 · VF Infra','version':'2.7.0','source_version':'2.6.0','schema':14,'migration':'NONE','product_commit':commit,'product_tree':tree,'tested_runtime_parent':'f86d79b871cf05c90af922afeb9fca851faf7c54','runtime_file_count':count,'runtime_fingerprint':fp,'production_source_manifest_file_sha256':source_sha,'allowed_source_versions':['2.6.0'],'update_type':'ATOMIC','backup_required':True,'rollback_supported':True,'release_kind':'product_experience_generation','provider_write_authority_change':False,'production_upgrade':'NOT_EXECUTED','production_write':0,'main_alignment':'NOT_EXECUTED'}
core_names=['VF_Infra_V2.7.0_FULL.zip','VF_Infra_V2.7.0_UPDATE.zip','VF_Infra_V2.7.0_ATOMIC.zip','repair-v2.7.0.php','PACKAGE_MANIFEST.json','PRODUCTION_SOURCE_MANIFEST_EXPECTED.txt','SHA256SUMS.txt']
base['artifacts']={n:meta(assets/n) for n in core_names}
(assets/'FORMAL_ARTIFACT_MANIFEST.json').write_text(json.dumps(base,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
rel={**base,'tag':'v2.7.0','release_name':'VF Infra V2.7.0'}
(assets/'RELEASE_MANIFEST.json').write_text(json.dumps(rel,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
(assets/'RELEASE_NOTES.md').write_text("""# VF Infra V2.7.0

V2.7.0 将 OWNER 已真实使用并通过的 Reference-Locked Personal Infrastructure Control 正式发布。

核心产品方向：
- 一级导航：概览 / 域名 / 服务器 / 服务商 / 设置。
- 个人优先级：费用 → 到期 → 续费 → 价格变化 → 风险 → OWNER 下一步 → 资源详情。
- Domain：到期、续费价、价格变化、自动续费与风险优先。
- Server：月费用、年度预计、账期与风险优先。
- Provider：账户状态、费用可信度、受影响资产与 OWNER 下一步。
- Desktop 以 Table 为主，Mobile 以 Card / Stacked 为主。
- 完成最终精准 UI 精修，不改变 Schema、数据模型或 Provider 远程写权限。

Schema 14 → 14，无 Migration。
正式在线升级只允许 V2.6.0 → V2.7.0。

Formal Candidate Commit: e2fd12cce0518333d7aa15e9d5babc5db0c9043b
Tested Runtime Parent: f86d79b871cf05c90af922afeb9fca851faf7c54
Candidate Gate: PASS
OWNER REAL USE: PASS
MASTER ACTUAL PIXEL REVIEW: PASS
""",encoding='utf-8')
PY

python3 - "$ASSETS" <<'PY'
from pathlib import Path
import hashlib,sys
r=Path(sys.argv[1]); names=sorted(p.name for p in r.iterdir() if p.is_file())
(r/'FORMAL_SHA256SUMS.txt').write_text(''.join(f"{hashlib.sha256((r/n).read_bytes()).hexdigest()}  {n}\n" for n in names),encoding='utf-8')
PY

echo "== create/reuse exact immutable tag/release and upload =="
if ! gh api "repos/$TARGET_REPOSITORY/git/ref/tags/$TAG" >/dev/null 2>&1; then
  gh api --method POST "repos/$TARGET_REPOSITORY/git/refs" -f ref="refs/tags/$TAG" -f sha="$TARGET_COMMIT" >/dev/null
fi
TAG_SHA="$(gh api "repos/$TARGET_REPOSITORY/git/ref/tags/$TAG" --jq '.object.sha')"
test "$TAG_SHA" = "$TARGET_COMMIT" || fail tag_target_after_create

if ! gh api "repos/$TARGET_REPOSITORY/releases/tags/$TAG" >/dev/null 2>&1; then
  gh release create "$TAG" --repo "$TARGET_REPOSITORY" --verify-tag --title "$RELEASE_NAME" --notes-file "$ASSETS/RELEASE_NOTES.md"
fi

gh api "repos/$TARGET_REPOSITORY/releases/tags/$TAG" > "$OUT/release-before-upload.json"
PRE_COUNT="$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["assets"]))' "$OUT/release-before-upload.json")"
if [ "$PRE_COUNT" = "0" ]; then gh release upload "$TAG" --repo "$TARGET_REPOSITORY" "$ASSETS"/*; fi

echo "== exact remote release readback =="
gh api "repos/$TARGET_REPOSITORY/git/ref/tags/$TAG" > "$EVIDENCE/tag.json"
gh api "repos/$TARGET_REPOSITORY/releases/tags/$TAG" > "$EVIDENCE/release.json"
python3 - "$ASSETS" "$EVIDENCE" "$TARGET_COMMIT" "$TARGET_TREE" <<'PY'
from pathlib import Path
import hashlib,json,sys
assets,evidence=Path(sys.argv[1]),Path(sys.argv[2]); commit,tree=sys.argv[3],sys.argv[4]
tag=json.loads((evidence/'tag.json').read_text()); rel=json.loads((evidence/'release.json').read_text())
assert tag['object']['sha']==commit
assert rel['tag_name']=='v2.7.0' and rel['name']=='VF Infra V2.7.0' and rel['draft'] is False and rel['prerelease'] is False
local={p.name:(p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()) for p in assets.iterdir() if p.is_file()}
remote={a['name']:a for a in rel['assets']}
assert set(remote)==set(local),(sorted(remote),sorted(local))
checked={}
for n,(size,sha) in local.items():
    a=remote[n]; assert a['size']==size,(n,a['size'],size); assert (a.get('digest') or '')=='sha256:'+sha,(n,a.get('digest'),sha)
    checked[n]={'asset_id':a['id'],'bytes':size,'sha256':sha,'github_digest':a.get('digest')}
update=checked['VF_Infra_V2.7.0_UPDATE.zip']
result={'tag':'v2.7.0','tag_target':commit,'product_tree':tree,'release_id':rel['id'],'published_at':rel['published_at'],'draft':rel['draft'],'prerelease':rel['prerelease'],'asset_count':len(checked),'assets':checked,'update_asset':update,'remote_readback':'PASS'}
(evidence/'remote-release-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,ensure_ascii=False,sort_keys=True)); print("P04_V270_REMOTE_RELEASE_READBACK_PASS")
PY

cp "$OUT/payload-paths.json" "$EVIDENCE/"
python3 - "$ASSETS" "$EVIDENCE" <<'PY'
from pathlib import Path
import hashlib,json,sys
a,e=Path(sys.argv[1]),Path(sys.argv[2]); d={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in a.iterdir() if p.is_file()}
(e/'formal-local-assets.json').write_text(json.dumps(d,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
PY
echo "P04_V270_FORMAL_RELEASE_PASS"
