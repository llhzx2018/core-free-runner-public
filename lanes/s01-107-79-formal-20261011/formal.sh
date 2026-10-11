#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p proof readback
export SOURCE_VERSION TARGET_VERSION TARGET_SHA TARGET_TREE BASE_SHA THEME_MAIN_SHA M3_SHA M3_TREE M3_VERSION M3_MAIN_SHA M3_BASE_SHA M3_SOURCE_VERSION CANDIDATE_RUN CANDIDATE_SHA CANDIDATE_ARTIFACT CANDIDATE_DIGEST
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(git -C m3target rev-parse HEAD)" = "$M3_SHA"
test "$(git -C m3target rev-parse HEAD^{tree})" = "$M3_TREE"
test "$(tr -d '[:space:]' < target/VERSION)" = "$TARGET_VERSION"
test "$(tr -d '[:space:]' < m3target/VERSION)" = "$M3_VERSION"
test "$(gh api "repos/llhzx2018/vf-tools-theme/git/ref/heads/main" --jq .object.sha)" = "$THEME_MAIN_SHA"
test "$(gh api "repos/llhzx2018/vf-tools-theme/git/commits/$THEME_MAIN_SHA" --jq .tree.sha)" = "$TARGET_TREE"
test "$(gh api "repos/llhzx2018/vf-tools-m3u8/git/ref/heads/main" --jq .object.sha)" = "$M3_MAIN_SHA"
test "$(gh api "repos/llhzx2018/vf-tools-m3u8/git/commits/$M3_MAIN_SHA" --jq .tree.sha)" = "$M3_TREE"

gh api "repos/llhzx2018/core-free-runner-public/actions/runs/$CANDIDATE_RUN" > /tmp/candidate-run.json
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$CANDIDATE_ARTIFACT" > /tmp/candidate-meta.json
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$CANDIDATE_ARTIFACT/zip" > /tmp/candidate-proof.zip
python3 - <<'PY'
import os,json,zipfile,hashlib,pathlib,stat
run=json.loads(pathlib.Path('/tmp/candidate-run.json').read_text())
meta=json.loads(pathlib.Path('/tmp/candidate-meta.json').read_text())
data=pathlib.Path('/tmp/candidate-proof.zip').read_bytes()
assert run['id']==int(os.environ['CANDIDATE_RUN']) and run['head_sha']==os.environ['CANDIDATE_SHA'] and run['conclusion']=='success'
assert meta['id']==int(os.environ['CANDIDATE_ARTIFACT']) and meta['workflow_run']['id']==run['id']
assert not meta['expired'] and meta['digest']==os.environ['CANDIDATE_DIGEST']=='sha256:'+hashlib.sha256(data).hexdigest() and meta['size_in_bytes']==len(data)
with zipfile.ZipFile('/tmp/candidate-proof.zip') as z:
 assert z.testzip() is None
 for item in z.infolist():
  p=pathlib.PurePosixPath(item.filename)
  assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(item.external_attr>>16) and p.suffix in ['.json','.png']
  if p.suffix=='.json':json.loads(z.read(item))
 assert 'FINAL_EVIDENCE.json' in z.namelist() and 'identity.json' in z.namelist()
 evidence=json.loads(z.read('FINAL_EVIDENCE.json'));theme=json.loads(z.read('identity.json'))
 assert evidence['status']=='PASS' and evidence['production']=='NOT_EXECUTED' and evidence['owner_product_pass']=='PENDING'
 assert evidence['theme_source_sha']==os.environ['TARGET_SHA'] and evidence['theme_source_tree']==os.environ['TARGET_TREE'] and evidence['theme_version']==os.environ['TARGET_VERSION']
 assert evidence['m3_source_sha']==os.environ['M3_SHA'] and evidence['m3_source_tree']==os.environ['M3_TREE'] and evidence['m3_version']==os.environ['M3_VERSION']
 assert set(evidence['checks'])=={'attribute-php','state-upgrade','state-rollback','state-reapply','tools-candidate','tools-reapply','tools-clean','embed-candidate','clean-installed'}
 assert set(evidence['checks'].values())=={'PASS'}
 for p in ['candidate','reapply','clean']:
  t=json.loads(z.read('tools-'+p+'.json'))
  assert t['status']=='PASS' and t['video']['width']>0 and t['video']['height']>0
 assert len(json.loads(z.read('tools-candidate.json'))['viewports'])==18
 assert theme['source_sha']==os.environ['TARGET_SHA'] and theme['source_tree']==os.environ['TARGET_TREE'] and theme['version']==os.environ['TARGET_VERSION']
 assert theme['frozen_shell_header_menu']=='PASS' and theme['security_boundary']=='SOURCE_PACKAGE_SECRET_SCAN_PASS'
 pathlib.Path('proof/candidate-reverse.json').write_text(json.dumps({'status':'PASS','candidate_run':run['id'],'artifact_id':meta['id'],'digest':meta['digest'],'theme_source_sha':evidence['theme_source_sha'],'m3_source_sha':evidence['m3_source_sha'],'theme_asset_bytes':theme['asset_bytes'],'theme_asset_sha256':theme['asset_sha256'],'production':'NOT_EXECUTED'},indent=2))
 pathlib.Path('/tmp/theme-expected.json').write_text(json.dumps(theme))
PY
# Deterministic runtime ZIP builds; paths remain private and are never uploaded to Public Artifact.
cp historic-footer/lanes/s01-c01-footer105-20261010/build.py lane/theme-build.py
cp historic-embed/lanes/s01-c03-embed79-20261010/build.py lane/m3-build.py
cp historic-embed/lanes/s01-c03-embed79-20261010/base-channel.json lane/base-channel.json
python3 lane/theme-build.py > /tmp/theme-build.txt
mkdir -p m3run/lane
ln -s "$PWD/m3target" m3run/target
cp lane/base-channel.json m3run/lane/base-channel.json
(cd m3run && TARGET_SHA="$M3_SHA" TARGET_TREE="$M3_TREE" TARGET_VERSION="$M3_VERSION" SOURCE_VERSION="$M3_SOURCE_VERSION" python3 ../lane/m3-build.py) > /tmp/m3-build.txt
python3 - <<'PY'
import os,json,pathlib
t=json.loads(pathlib.Path('proof/identity.json').read_text())
expected=json.loads(pathlib.Path('/tmp/theme-expected.json').read_text())
for k in ['source_sha','source_tree','version','asset','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint']:
 assert t[k]==expected[k],(k,t.get(k),expected.get(k))
m=json.loads(pathlib.Path('m3run/proof/identity.json').read_text())
assert m['source_sha']==os.environ['M3_SHA'] and m['source_tree']==os.environ['M3_TREE'] and m['version']==os.environ['M3_VERSION']
assert m['asset_bytes']==3571384 and m['asset_sha256']=='4cc71ee830aae17b1d695657c9c4c3b5701fc7d0b95c18b5f8ced753e9deb1cd'
pathlib.Path('proof/m3-identity.json').write_text(json.dumps(m,indent=2))
PY
cat > /tmp/theme-notes.md <<EOF
Theme 1.35.107 修复公共静态 HTML 链接重写错误匹配长属性名中的 action，造成播放列表检查器按钮失效。严格完整属性边界；真实 href/action/data-href 链接解析与未知目标阻断保持。真实 PHP 渲染回归以及 Theme106/M3U878 到 Theme107/M3U879 联合 WordPress/Playwright 回归通过。Shell/Header/Header Menu 保持冻结。机器通过不等于 OWNER/Production PASS。Production 仅 OWNER 手工升级。
Exact source: $TARGET_SHA; tree: $TARGET_TREE; tested run: $CANDIDATE_RUN.
EOF
cat > /tmp/m3-notes.md <<EOF
M3U8 1.25.79：默认 Embed/Share 播放地址改为读取已有 player Page Mounts 公共 URL，不再意外使用首页 iframe；显式自定义地址保留。实际媒体解码、父子窗口握手、复制/JSON 导出、联合 WordPress 工具回归、回退与干净安装通过。未改 Schema、Updater、Theme Shell/Header/Menu。机器通过不等于 OWNER/Production PASS。Production 仅 OWNER 手工升级。
Exact source: $M3_SHA; tree: $M3_TREE; tested run: $CANDIDATE_RUN.
EOF
# Formal release is idempotent only for identical exact source/tag and delivered bytes.
for component in theme m3; do
 if [ "$component" = theme ];then repo=llhzx2018/vf-tools-theme; version="$TARGET_VERSION"; main="$THEME_MAIN_SHA"; asset="vf-tools-theme_V$version.zip"; zip_path="proof/$asset"; notes=/tmp/theme-notes.md
 else repo=llhzx2018/vf-tools-m3u8;version="$M3_VERSION";main="$M3_MAIN_SHA";asset="vf-tools-m3u8_V$version.zip";zip_path="m3run/proof/$asset";notes=/tmp/m3-notes.md;fi
 tag="v$version"
 if gh release view "$tag" --repo "$repo" >/dev/null 2>&1;then
  echo "Existing formal Release $repo/$tag: fail-closed remote exact identity verification"
 else
  gh release create "$tag" "$zip_path" --repo "$repo" --target "$main" --title "VF Tools $component V$version" --notes-file "$notes"
 fi
 test "$(gh api "repos/$repo/git/ref/tags/$tag" --jq .object.sha)" = "$main"
 gh api "repos/$repo/releases/tags/$tag" > "proof/$component-release-meta.json"
 gh release download "$tag" --repo "$repo" --pattern "$asset" --output "readback/$asset"
 cmp "$zip_path" "readback/$asset"
done
python3 - <<'PY'
import os,json,hashlib,pathlib,zipfile
p=pathlib.Path('proof')
for comp,repo,ver,main,identity,source in [
 ('theme','llhzx2018/vf-tools-theme',os.environ['TARGET_VERSION'],os.environ['THEME_MAIN_SHA'],p/'identity.json',p/('vf-tools-theme_V'+os.environ['TARGET_VERSION']+'.zip')),
 ('m3','llhzx2018/vf-tools-m3u8',os.environ['M3_VERSION'],os.environ['M3_MAIN_SHA'],p/'m3-identity.json',pathlib.Path('m3run/proof/vf-tools-m3u8_V'+os.environ['M3_VERSION']+'.zip'))]:
 meta=json.loads((p/(comp+'-release-meta.json')).read_text())
 ident=json.loads(identity.read_text())
 asset=ident.get('asset') or ident['asset_name']
 fetched=pathlib.Path('readback')/asset
 data=fetched.read_bytes()
 assert meta['tag_name']=='v'+ver and not meta['draft'] and not meta['prerelease']
 assert len(meta['assets'])==1
 remote=meta['assets'][0]
 assert remote['name']==asset and remote['size']==len(data)==ident['asset_bytes'] and remote['digest']=='sha256:'+hashlib.sha256(data).hexdigest()
 assert ident['asset_sha256']==hashlib.sha256(data).hexdigest() and data==source.read_bytes()
 with zipfile.ZipFile(fetched) as z:assert z.testzip() is None
 receipt={'status':'PASS','component':comp,'repo':repo,'version':ver,'source_sha':ident['source_sha'],'source_tree':ident['source_tree'],'main_sha':main,'release_id':meta['id'],'tag':'v'+ver,'asset_id':remote['id'],'asset_name':asset,'asset_bytes':len(data),'asset_sha256':hashlib.sha256(data).hexdigest(),'runtime_files':ident['runtime_files'],'runtime_fingerprint':ident['runtime_fingerprint'],'published_at':meta['published_at'],'distribution':'NOT_EXECUTED','production':'NOT_EXECUTED','owner_pass':'PENDING_POST_OWNER_UPGRADE'}
 (p/(comp+'-FINAL_RELEASE.json')).write_text(json.dumps(receipt,indent=2))
 print('PUBLIC_SAFE_FORMAL_RECEIPT',json.dumps(receipt))
PY
