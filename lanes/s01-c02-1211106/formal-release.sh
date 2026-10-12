#!/usr/bin/env bash
set -Eeuo pipefail
: "$TARGET_SHA" "$MAIN_SHA" "$TARGET_TREE" "$TARGET_VERSION" "$RELEASE_TAG" "$RUN_ID" "$ARTIFACT_ID"
out="$GITHUB_WORKSPACE/proof-formal"; mkdir -p "$out"
# Expected bytes and hashes must come from the exact PASS candidate receipt, not guessed values.
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID/zip" > "$out/machine-preflight.zip"
python3 - "$out" <<'PY'
import json,os,pathlib,sys,zipfile
p=pathlib.Path(sys.argv[1])
with zipfile.ZipFile(p/'machine-preflight.zip') as z:
    candidate=json.loads(z.read('candidate.json'))
    receipt=json.loads(z.read('RESULT.json'))
assert receipt['result']=='PASS' and receipt['source_sha']==os.environ['TARGET_SHA']
assert receipt['version']==os.environ['TARGET_VERSION']
assert candidate['version']==os.environ['TARGET_VERSION']
keys={'EXPECTED_SHA':candidate['asset_sha256'],'EXPECTED_BYTES':candidate['asset_bytes'],
      'EXPECTED_FILES':candidate['runtime_files'],'EXPECTED_FINGERPRINT':candidate['runtime_fingerprint']}
with (p/'expected.env').open('w') as f:
    for key,value in keys.items():
        assert isinstance(value,(str,int)) and str(value).replace('.','').replace('-','').isalnum()
        f.write(key+'='+str(value)+'\n')
print('PINNED_MACHINE_CANDIDATE_METADATA=PASS')
PY
set -a
source "$out/expected.env"
set +a
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
assert receipt.get('licensed_pro')=='PASS' and receipt.get('licensed_pro_version')=='3.8.2'
assert receipt.get('slug_real_wp_browser')=='PASS'
with zipfile.ZipFile(p/'remote-machine.zip') as z:
 licensed=json.loads(z.read('PRO_STAGING.json'))
 coverage=json.loads(z.read('SLUG_COVERAGE.json'))
 clean=json.loads(z.read('SLUG_BROWSER_clean.json'))
 issue=json.loads(z.read('SLUG_BROWSER_issue.json'))
assert licensed['status']=='PASS' and licensed['polylang_pro_gate']=='PASS'
assert licensed['candidate_sha']==os.environ['TARGET_SHA'] and licensed['production']=='NOT_EXECUTED'
assert coverage['result']=='PASS' and coverage['candidate_sha']==os.environ['TARGET_SHA']
assert coverage['native_inventory']==3001 and coverage['zero_page_writes']=='PASS' and coverage['production_write'] is False
assert clean['result']==issue['result']=='PASS' and issue['native_http_rejection_cases']==11
assert clean['candidate_sha']==issue['candidate_sha']==os.environ['TARGET_SHA']
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
# VF Tools Ops 1.21.1106 · 多语言 Slug 清理扫描覆盖状态修复

修复多语言 Slug 清理在仅检查前 500 个对象时误报全站 PASS，以及自动处理仅覆盖前 3000 个对象时误报全站处理完成。额外读取一个边界对象判断覆盖不足，实际检查预算保持；不完整空扫描显示 WARN，页面明确标注本次检查数量和本批范围，批量结果显示 PARTIAL。

修复 PR #402；完整精确候选使用 WordPress/MariaDB 与真实 Polylang Pro 3.8.2 验证 50/51、500/501、3000/3001 原生查询、只读扫描与零页面写入，四种宽度 1440/1024/768/390 的 clean/issue 界面及真实认证 POST 的 11 种拒绝情形。原共享 slug、双向翻译关联、错误/缺失 301 阻断、竞态保护、回退、安装升级与数据保全均经过精确候选机器验证。

许可文件仅在既有私有测试输入与隔离临时目录使用，不包含在正式 ZIP 或公共证据中。冻结 Shell/Header/Menu、M3U8、Theme、Schema、权限和更新协议不变。

正式包适用于 WordPress 完整安装或从已声明支持的版本原地升级，本次直接验证从 1.21.1105 升级与回滚；Schema 保持 6.0.0，无数据迁移。升级前保留站点备份，回滚与数据保全已验证。ZIP 的 exact SHA-256 与字节数由候选回执冻结并通过远端下载重算，详见正式 Release Asset digest 及公共更新 Manifest。

Production 只由 OWNER 手工升级。本版不会自动修改页面、翻译关系、301 或 M3U8 挂载，已授权完成的 1286↔1124、4348 草稿及中文挂载保持现状。扫描超过预算时明确报告覆盖不足，尚未提供跨批次遍历全站的新增工作流。机器和 Release PASS 不代表 OWNER 真实使用 PASS，完整 Production 交互验收仍独立待确认。
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
 gh release create "$RELEASE_TAG" "$asset" --repo llhzx2018/vf-tools-ops --verify-tag --target "$TARGET_SHA" --latest --title "VF Tools Ops $TARGET_VERSION · Slug 扫描覆盖状态修复" --notes-file "$out/release-notes.md"
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
print('S01_C02_POLYLANG_FORMAL_RELEASE_PASS')
PY

