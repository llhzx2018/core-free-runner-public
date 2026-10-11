#!/usr/bin/env bash
set -Eeuo pipefail
export TARGET_SHA TARGET_TREE TARGET_VERSION SOURCE_VERSION BASE_SHA THEME_MAIN_SHA CANDIDATE_RUN CANDIDATE_SHA CANDIDATE_ARTIFACT CANDIDATE_DIGEST
mkdir -p proof readback
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(tr -d '[:space:]' < target/VERSION)" = "$TARGET_VERSION"
test "$(gh api "repos/llhzx2018/vf-tools-theme/git/ref/heads/main" --jq .object.sha)" = "$THEME_MAIN_SHA"
test "$(gh api "repos/llhzx2018/vf-tools-theme/git/commits/$THEME_MAIN_SHA" --jq .tree.sha)" = "$TARGET_TREE"

gh api "repos/llhzx2018/core-free-runner-public/actions/runs/$CANDIDATE_RUN" > /tmp/candidate-run-108.json
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$CANDIDATE_ARTIFACT" > /tmp/candidate-meta-108.json
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$CANDIDATE_ARTIFACT/zip" > /tmp/candidate-proof-108.zip
python3 - <<'PY'
import os,json,hashlib,pathlib,zipfile,stat
run=json.loads(pathlib.Path('/tmp/candidate-run-108.json').read_text())
meta=json.loads(pathlib.Path('/tmp/candidate-meta-108.json').read_text())
blob=pathlib.Path('/tmp/candidate-proof-108.zip').read_bytes()
assert run['id']==int(os.environ['CANDIDATE_RUN']) and run['head_sha']==os.environ['CANDIDATE_SHA'] and run['conclusion']=='success'
assert meta['id']==int(os.environ['CANDIDATE_ARTIFACT']) and meta['workflow_run']['id']==run['id'] and not meta['expired']
assert meta['digest']==os.environ['CANDIDATE_DIGEST']=='sha256:'+hashlib.sha256(blob).hexdigest() and meta['size_in_bytes']==len(blob)
with zipfile.ZipFile('/tmp/candidate-proof-108.zip') as z:
 assert z.testzip() is None
 for item in z.infolist():
  p=pathlib.PurePosixPath(item.filename)
  assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(item.external_attr>>16)
  assert p.suffix in ['.json','.png']
 final=json.loads(z.read('FINAL_EVIDENCE.json'))
 ident=json.loads(z.read('identity.json'))
 assert final['status']=='PASS' and final['production']=='NOT_EXECUTED' and final['owner_product_pass']=='PENDING'
 assert final['theme_source_sha']==os.environ['TARGET_SHA'] and final['theme_source_tree']==os.environ['TARGET_TREE']
 assert final['theme_version']==os.environ['TARGET_VERSION'] and final['m3_version']=='1.25.79'
 assert all(v=='PASS' for v in final['checks'].values())
 assert {'embed-alias-php','tools-candidate','tools-reapply','tools-clean','embed-candidate'}<=set(final['checks'])
 for name in ['candidate','reapply','clean']:
  proof=json.loads(z.read('tools-'+name+'.json'))
  assert proof['status']=='PASS' and proof['video']['width']>0 and proof['video']['height']>0
 assert ident['source_sha']==os.environ['TARGET_SHA'] and ident['source_tree']==os.environ['TARGET_TREE']
 assert ident['version']==os.environ['TARGET_VERSION']
 assert ident['frozen_shell_header_menu']=='PASS' and ident['security_boundary']=='SOURCE_PACKAGE_SECRET_SCAN_PASS'
 pathlib.Path('/tmp/theme108-candidate-identity.json').write_text(json.dumps(ident))
 pathlib.Path('proof/candidate-reverse.json').write_text(json.dumps({'status':'PASS','run_id':run['id'],'artifact_id':meta['id'],'digest':meta['digest'],'source_sha':ident['source_sha'],'source_tree':ident['source_tree'],'owner_product_pass':'PENDING'},indent=2))
PY
cp historic-footer/lanes/s01-c01-footer105-20261010/build.py lane/theme-build.py
python3 lane/theme-build.py > /tmp/theme108-build.txt
python3 - <<'PY'
import json,pathlib
built=json.loads(pathlib.Path('proof/identity.json').read_text())
tested=json.loads(pathlib.Path('/tmp/theme108-candidate-identity.json').read_text())
for key in ['status','source_sha','source_tree','version','asset','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint','frozen_shell_header_menu','security_boundary']:
 assert built[key]==tested[key],(key,built.get(key),tested.get(key))
PY
cat >/tmp/theme108-notes.md <<EOF
Theme 1.35.108: restore already-published WordPress/Polylang Embed Generator Page Mount, whose prior route displayed only an empty Theme shell. The real provider shortcode [vf_m3u8_embed] now loads through the existing bounded Theme public route renderer. Keeps legacy /embed/ and registered M3U8 Provider behavior unchanged. WordPress+MariaDB+Polylang+Playwright EN/ZH route, real media playback, full three tools, responsive and upgrade/rollback/reinstall tests are exact-source verified. Shell/Header/Header Menu unchanged; Production OWNER manual only; OWNER Production acceptance pending.
Exact source: $TARGET_SHA; tree: $TARGET_TREE; tested run: $CANDIDATE_RUN.
EOF
asset="vf-tools-theme_V$TARGET_VERSION.zip"
tag="v$TARGET_VERSION"
if ! gh release view "$tag" --repo llhzx2018/vf-tools-theme >/dev/null 2>&1;then
 gh release create "$tag" "proof/$asset" --repo llhzx2018/vf-tools-theme --target "$THEME_MAIN_SHA" --title "VF Tools Theme V$TARGET_VERSION" --notes-file /tmp/theme108-notes.md
fi
test "$(gh api "repos/llhzx2018/vf-tools-theme/git/ref/tags/$tag" --jq .object.sha)" = "$THEME_MAIN_SHA"
gh api "repos/llhzx2018/vf-tools-theme/releases/tags/$tag" > proof/theme-release-meta.json
gh release download "$tag" --repo llhzx2018/vf-tools-theme --pattern "$asset" --output "readback/$asset"
cmp "proof/$asset" "readback/$asset"
python3 - <<'PY'
import os,pathlib,json,hashlib,zipfile
ident=json.loads(pathlib.Path('proof/identity.json').read_text())
meta=json.loads(pathlib.Path('proof/theme-release-meta.json').read_text())
data=pathlib.Path('readback/'+ident['asset']).read_bytes()
assert meta['tag_name']=='v'+os.environ['TARGET_VERSION'] and not meta['draft'] and not meta['prerelease']
assert len(meta['assets'])==1
remote=meta['assets'][0]
assert remote['name']==ident['asset'] and remote['size']==len(data)==ident['asset_bytes']
assert hashlib.sha256(data).hexdigest()==ident['asset_sha256']
assert remote['digest']=='sha256:'+ident['asset_sha256']
with zipfile.ZipFile(pathlib.Path('readback/'+ident['asset'])) as z:
 assert z.testzip() is None
result={'status':'PASS','version':ident['version'],'source_sha':ident['source_sha'],'source_tree':ident['source_tree'],'main_sha':os.environ['THEME_MAIN_SHA'],'release_id':meta['id'],'asset_id':remote['id'],'tag':meta['tag_name'],'asset_name':ident['asset'],'asset_bytes':ident['asset_bytes'],'asset_sha256':ident['asset_sha256'],'runtime_files':ident['runtime_files'],'runtime_fingerprint':ident['runtime_fingerprint'],'released_at':meta['published_at'],'production':'NOT_EXECUTED','owner_product_pass':'PENDING'}
pathlib.Path('proof/theme-FINAL_RELEASE.json').write_text(json.dumps(result,indent=2))
print('PUBLIC_SAFE_THEME108_FORMAL_RELEASE',json.dumps(result))
PY
