#!/usr/bin/env bash
set -Eeuo pipefail
: "$TARGET_SHA" "$MAIN_SHA" "$TARGET_TREE" "$TARGET_VERSION" "$RELEASE_TAG" "$EXPECTED_SHA" "$EXPECTED_BYTES" "$EXPECTED_FILES" "$EXPECTED_FINGERPRINT" "$RUN_ID" "$ARTIFACT_ID"
out="$GITHUB_WORKSPACE/proof-formal"; mkdir -p "$out"
product="$(realpath product)"
test "$(git -C "$product" rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C "$product" rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(tr -d '\r\n' < "$product/VERSION")" = "$TARGET_VERSION"
grep -Fq " * Version: $TARGET_VERSION" "$product/vf-ops.php"
grep -Fq "define('VF_OPS_VERSION', '$TARGET_VERSION')" "$product/vf-ops.php"
asset="$out/vf-tools-ops_V$TARGET_VERSION.zip"
python3 "$product/.github/release/build-ops-package.py" --source "$product" --output "$asset" > "$out/build.json"
python3 - "$out/build.json" "$asset" <<'PY'
import json,os,sys,hashlib,zipfile
m=json.load(open(sys.argv[1]));b=open(sys.argv[2],"rb").read()
print("PUBLIC_PACKAGE_METADATA", {k:m.get(k) for k in ("asset_sha256","asset_bytes","runtime_files","runtime_fingerprint","version","root_contract")}, "EXPECTED", {k:os.environ.get(k) for k in ("EXPECTED_SHA","EXPECTED_BYTES","EXPECTED_FILES","EXPECTED_FINGERPRINT","TARGET_VERSION")}, flush=True)
assert m["asset_sha256"]==os.environ["EXPECTED_SHA"]==hashlib.sha256(b).hexdigest()
assert m["asset_bytes"]==int(os.environ["EXPECTED_BYTES"])==len(b)
assert m["runtime_files"]==int(os.environ["EXPECTED_FILES"])
assert m["runtime_fingerprint"]==os.environ["EXPECTED_FINGERPRINT"]
assert m["version"]==os.environ["TARGET_VERSION"]
assert m["root_contract"]=="PASS_SINGLE_VF_OPS_ROOT"
with zipfile.ZipFile(sys.argv[2]) as z:
 ns=z.namelist()
 assert len(ns)==int(os.environ["EXPECTED_FILES"])
 assert all(n.startswith("vf-ops/") and not n.startswith("vf-ops/vf-ops/") for n in ns)
 assert "vf-ops/vf-ops.php" in ns
print("FORMAL_ZIP_EXACT_MACHINE_BYTE_MATCH=PASS")
PY
echo "stage=REMOTE_MACHINE_READBACK" > "$out/stage.txt"
gh api "repos/llhzx2018/core-free-runner-public/actions/runs/$RUN_ID" --jq '{status,conclusion,head_sha}' > "$out/runner.json"
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID" --jq '{id,name,expired}' > "$out/artifact.json"
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID/zip" > "$out/remote-machine.zip"
python3 - "$out" <<'PY'
import json,os,pathlib,sys,zipfile
p=pathlib.Path(sys.argv[1]);run=json.loads((p/'runner.json').read_text());a=json.loads((p/'artifact.json').read_text())
assert run['status']=='completed' and run['conclusion']=='success'
assert a['id']==int(os.environ['ARTIFACT_ID']) and not a['expired']
with zipfile.ZipFile(p/'remote-machine.zip') as z:
 receipt=json.loads(z.read('RESULT.json'))
 candidate=json.loads(z.read('candidate.json'))
 native=json.loads(z.read('native/FINAL_EVIDENCE.json'))
 browser=json.loads(z.read('native/browser-e2e.json'))
assert receipt['result']=='PASS' and receipt['source_sha']==os.environ['TARGET_SHA']
assert receipt['version']==os.environ['TARGET_VERSION'] and receipt['native_wp']=='PASS'
assert receipt['formal_upgrade']=='PASS' and receipt['formal_rollback']=='PASS'
assert receipt['production_write'] is False
assert candidate['asset_sha256']==os.environ['EXPECTED_SHA'] and candidate['asset_bytes']==int(os.environ['EXPECTED_BYTES'])
assert candidate['runtime_fingerprint']==os.environ['EXPECTED_FINGERPRINT']
assert native['result']=='PASS' and browser['result']=='PASS'
assert browser['blocking_errors']==0 and browser['responsive_failures']==0
(p/'gate-readback.json').write_text(json.dumps({'result':'PASS','machine_run':int(os.environ['RUN_ID']),'artifact_id':a['id'],'candidate_sha':receipt['source_sha']},indent=2)+'\n')
print("REMOTE_EXACT_MACHINE_RECEIPT=PASS")
PY
gh api "repos/llhzx2018/vf-tools-ops/commits/$MAIN_SHA" --jq '{sha:.sha,tree:.commit.tree.sha,parents:[.parents[].sha]}' > "$out/promoted-main.json"
python3 - "$out/promoted-main.json" <<'PY'
import json,os,sys
c=json.load(open(sys.argv[1]))
assert c['sha']==os.environ['MAIN_SHA'] and c['tree']==os.environ['TARGET_TREE']
assert os.environ['TARGET_SHA'] in c['parents']
print("MAIN_PROMOTION_EXACT_TREE=PASS")
PY
cat > "$out/release-notes.md" <<'EOF'
# VF Tools Ops 1.21.1097 · 搜索与分析集成保存与草稿保护

2026-10-12。OWNER 的搜索与分析集成截图确认 GSC 属性及凭据当前尚待配置，这一状态正确。旧版在 GSC 已配置/已连接时主动作变为连接、检查或同步，保存已修改设置缺乏持续可用的入口。本版在所有已配置状态保留关联单一原生配置表单的保存操作；改动草稿时阻断使用旧配置进行 GSC 授权、检查、同步和 IndexNow 提交，并在离开页面前提示确认，防止错误丢弃。

完善 OAuth / Service Account 模式切换、GA4 错误更正与折叠字段定位、包含分隔符的密钥变更检测、凭据不回显和静默数据回读安全。Ops Shell/Header/Menu 不改；真实后台权限、加密、IndexNow 和 Schema 6.0.0 不变。

PR #356 修复、PR #385 候选，WordPress 7.0.2/MariaDB 真实加密配置保存/修改/Revision/Hash 回归 #38187991447 PASS；40 组真实 Chromium 四宽度界面场景 #38187864771 PASS；候选完整原生升级/回滚、安全和资源一致性 #38188183505 PASS。

Production OWNER 手工升级。真实 GSC/IndexNow 密钥未被模拟为有效远程认证，连接第三方服务需站点管理员自身配置；隔离机器 PASS 不冒充 OWNER Product Real Use PASS。
EOF
EOF
echo "stage=FORMAL_RELEASE" >> "$out/stage.txt"
if [ -z "$GH_TOKEN" ]; then echo "BLOCKED_RELEASE_WRITE_CREDENTIAL" >&2; exit 21; fi
if gh api "repos/llhzx2018/vf-tools-ops/git/ref/tags/$RELEASE_TAG" --jq '.object.sha' > "$out/existing-tag.txt" 2>/dev/null; then
 test "$(cat "$out/existing-tag.txt")" = "$TARGET_SHA"
else
 gh api -X POST "repos/llhzx2018/vf-tools-ops/git/refs" -f ref="refs/tags/$RELEASE_TAG" -f sha="$TARGET_SHA" > /dev/null
fi
if gh release view "$RELEASE_TAG" --repo llhzx2018/vf-tools-ops --json tagName >/dev/null 2>&1; then
 echo "Existing Release detected, readback only"
else
 gh release create "$RELEASE_TAG" "$asset" --repo llhzx2018/vf-tools-ops --verify-tag --target "$TARGET_SHA" --latest --title "VF Tools Ops 1.21.1097 · 页面功能与 UX/UI 修复" --notes-file "$out/release-notes.md"
fi
gh api "repos/llhzx2018/vf-tools-ops/releases/tags/$RELEASE_TAG" --jq '{tag_name,published_at,draft,prerelease,assets:[.assets[]|{id,name,size,digest,browser_download_url}]}' > "$out/release.json"
python3 - "$out/release.json" <<'PY'
import os,json,sys
r=json.load(open(sys.argv[1]));name='vf-tools-ops_V'+os.environ['TARGET_VERSION']+'.zip'
a=[x for x in r['assets'] if x['name']==name]
assert r['tag_name']==os.environ['RELEASE_TAG'] and not r['draft'] and not r['prerelease']
assert len(a)==1 and a[0]['size']==int(os.environ['EXPECTED_BYTES'])
assert a[0]['digest']=='sha256:'+os.environ['EXPECTED_SHA']
print('FORMAL_RELEASE_ASSET_METADATA_SHA=PASS')
PY
mkdir -p "$out/download-check"
gh release download "$RELEASE_TAG" --repo llhzx2018/vf-tools-ops --pattern "vf-tools-ops_V$TARGET_VERSION.zip" --dir "$out/download-check" --clobber
test "$(sha256sum "$out/download-check/vf-tools-ops_V$TARGET_VERSION.zip" | awk '{print $1}')" = "$EXPECTED_SHA"
test "$(wc -c < "$out/download-check/vf-tools-ops_V$TARGET_VERSION.zip" | tr -d ' ')" = "$EXPECTED_BYTES"
echo "stage=FORMAL_RELEASE_REMOTE_PASS" >> "$out/stage.txt"
python3 - "$out" <<'PY'
import json,os,pathlib,sys
p=pathlib.Path(sys.argv[1]);r=json.loads((p/'release.json').read_text())
x={'result':'PASS','component_id':'S01-C02','version':os.environ['TARGET_VERSION'],'tag':os.environ['RELEASE_TAG'],
'source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'main_sha':os.environ['MAIN_SHA'],
'asset_name':'vf-tools-ops_V'+os.environ['TARGET_VERSION']+'.zip','asset_bytes':int(os.environ['EXPECTED_BYTES']),
'asset_sha256':os.environ['EXPECTED_SHA'],'runtime_files':int(os.environ['EXPECTED_FILES']),
'runtime_fingerprint':os.environ['EXPECTED_FINGERPRINT'],'released_at':r['published_at'],
'machine_run':int(os.environ['RUN_ID']),'download_verified':'PASS','production':'UNCHANGED','distribution':'NOT_UPDATED'}
(p/'FINAL_FORMAL_RELEASE.json').write_text(json.dumps(x,indent=2)+'\n')
print('S01_C02_1211097_FORMAL_RELEASE_PASS')
PY
