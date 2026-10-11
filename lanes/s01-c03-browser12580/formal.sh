#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p proof readback
test "$(git -C target rev-parse HEAD)" = "$PRODUCT_MAIN_SHA"
test "$(git -C candidate rev-parse HEAD)" = "$QA_CANDIDATE_SHA"
export TREE="$(git -C target rev-parse HEAD^{tree})"
test "$TREE" = "$(git -C candidate rev-parse HEAD^{tree})"
test "$(tr -d '[:space:]' < target/VERSION)" = "1.25.80"
test "$(gh api repos/llhzx2018/vf-tools-m3u8/git/ref/heads/main --jq .object.sha)" = "$PRODUCT_MAIN_SHA"
test -n "$TREE"

gh api "repos/llhzx2018/core-free-runner-public/actions/runs/$QA_RUN" > /tmp/qa-run.json
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$QA_ARTIFACT" > /tmp/qa-meta.json
gh api "repos/llhzx2018/core-free-runner-public/actions/artifacts/$QA_ARTIFACT/zip" > /tmp/qa-evidence.zip
python3 - <<'PY'
import os,json,pathlib,zipfile,hashlib,stat
run=json.loads(pathlib.Path('/tmp/qa-run.json').read_text())
meta=json.loads(pathlib.Path('/tmp/qa-meta.json').read_text())
archive=pathlib.Path('/tmp/qa-evidence.zip').read_bytes()
assert run['id']==int(os.environ['QA_RUN']) and run['head_sha']==os.environ['QA_RUN_SHA'] and run['conclusion']=='success'
assert meta['id']==int(os.environ['QA_ARTIFACT']) and meta['workflow_run']['id']==run['id'] and meta['workflow_run']['head_sha']==run['head_sha']
assert not meta['expired'] and meta['digest']==os.environ['QA_DIGEST']=='sha256:'+hashlib.sha256(archive).hexdigest()
assert meta['size_in_bytes']==len(archive)
with zipfile.ZipFile('/tmp/qa-evidence.zip') as z:
 assert z.testzip() is None
 names=set(z.namelist())
 assert {'browser.json','wp-final.json','S01-C03-browser-12580.json'} <= names
 for item in z.infolist():
  p=pathlib.PurePosixPath(item.filename)
  assert not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(item.external_attr>>16)
 browser=json.loads(z.read('browser.json'));wp=json.loads(z.read('wp-final.json'));exact=json.loads(z.read('S01-C03-browser-12580.json'))
 assert browser['status']=='PASS' and browser['production']=='NOT_EXECUTED' and len(browser['checks'])>=24
 assert all(c['pass'] for c in browser['checks'])
 assert wp['status']=='PASS' and wp['m3u8']=='1.25.80' and wp['theme']=='1.35.108' and wp['browser_check_count']>=24
 assert exact['status']=='PASS' and exact['candidate_sha']==os.environ['QA_CANDIDATE_SHA'] and exact['version']=='1.25.80'
 safe={'status':'PASS','candidate_sha':os.environ['QA_CANDIDATE_SHA'],'run_sha':run['head_sha'],'run_id':run['id'],'artifact_id':meta['id'],'artifact_digest':meta['digest'],'browser_checks':len(browser['checks']),'production':'NOT_EXECUTED'}
 pathlib.Path('proof/QA_REVERSE.json').write_text(json.dumps(safe,indent=2))
 print('EXACT_QA_REVERSE_PASS',json.dumps(safe))
PY

python3 - <<'PY'
import os,pathlib,hashlib,zipfile,json,subprocess
root=pathlib.Path('target/src')
paths=sorted((p for p in root.rglob('*') if p.is_file() and p.name not in ['README.md','PACKAGE_PROFILE.json']),key=lambda x:x.relative_to(root).as_posix())
assert len(paths)==568,len(paths)
fp=hashlib.sha256()
for p in paths:
 assert not p.is_symlink()
 rel=p.relative_to(root).as_posix()
 assert not any(t in pathlib.PurePosixPath(rel).parts for t in ['tests','docs','evidence','private','.git','.github'])
 assert p.suffix.lower() not in ['.sql','.sqlite','.db','.zip','.log','.tmp']
 fp.update((rel+'\0'+hashlib.sha256(p.read_bytes()).hexdigest()+'\n').encode())
def build(dest):
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in paths:
   rel=p.relative_to(root).as_posix()
   i=zipfile.ZipInfo('vf-tool-m3u8/'+rel,date_time=(2026,10,11,0,0,0))
   i.create_system=3;i.external_attr=0o100644<<16;i.compress_type=zipfile.ZIP_DEFLATED
   z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
asset=pathlib.Path('proof/vf-tools-m3u8_V1.25.80.zip')
build(asset);build('/tmp/rebuild-12580.zip')
assert asset.read_bytes()==pathlib.Path('/tmp/rebuild-12580.zip').read_bytes()
with zipfile.ZipFile(asset) as z:
 assert z.testzip() is None and len(z.namelist())==len(paths)
 src=z.read('vf-tool-m3u8/vf-tool-m3u8.php')
 assert b'Version: 1.25.80' in src
manifest=json.loads((root/'config/performance-bundles.php').read_text().splitlines()[2])['browser-stream-test']
for typ,source_key,out in [('js','jsSources','script'),('css','cssSources','style')]:
 rebuilt='\n'.join((root/p).read_text() for p in manifest[source_key])+'\n'
 assert rebuilt==(root/manifest[out]).read_text(),typ
identity={'status':'PASS','version':'1.25.80','source_sha':os.environ['PRODUCT_MAIN_SHA'],'source_tree':os.environ['TREE'],'asset':asset.name,'asset_bytes':asset.stat().st_size,'asset_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'runtime_files':len(paths),'runtime_fingerprint':fp.hexdigest(),'deterministic_build':'PASS','deployed_bundle_parity':'PASS','physical_root':'vf-tool-m3u8','production':'NOT_EXECUTED'}
pathlib.Path('proof/IDENTITY.json').write_text(json.dumps(identity,indent=2))
print('FORMAL_PACKAGE_IDENTITY',json.dumps(identity))
PY

cat >/tmp/m3-notes.md <<EOF
VF Tools M3U8 1.25.80 / R300: Browser Stream Test operational and UX closure.
Fixes cancelled-run races, protects signed media URL parameters across origins, redacts sensitive query tokens in copied and exported diagnostic reports, and improves 390px mobile readability.
Both original module source and production-served concatenated JS/CSS have been rebuilt to exact source parity. Verified on isolated WordPress 7.1.2 + MariaDB 11.8.8 + headless Chromium with real 320x180 decoded HLS video, manual manifest, clipboard, JSON download, viewport and 24 browser checks. Existing Theme 1.35.108 unchanged; Production remains OWNER-manual only.
Exact main source: $PRODUCT_MAIN_SHA. QA Run: $QA_RUN; artifact: $QA_ARTIFACT.
EOF
TAG=v1.25.80
ASSET=vf-tools-m3u8_V1.25.80.zip
if ! gh release view "$TAG" --repo llhzx2018/vf-tools-m3u8 >/dev/null 2>&1; then
 gh release create "$TAG" "proof/$ASSET" --repo llhzx2018/vf-tools-m3u8 --target "$PRODUCT_MAIN_SHA" --title "VF Tools M3U8 V1.25.80" --notes-file /tmp/m3-notes.md
fi
test "$(gh api "repos/llhzx2018/vf-tools-m3u8/git/ref/tags/$TAG" --jq .object.sha)" = "$PRODUCT_MAIN_SHA"
gh api "repos/llhzx2018/vf-tools-m3u8/releases/tags/$TAG" > proof/RELEASE_META.json
gh release download "$TAG" --repo llhzx2018/vf-tools-m3u8 --pattern "$ASSET" --output "readback/$ASSET"
cmp "proof/$ASSET" "readback/$ASSET"
python3 - <<'PY'
import json,hashlib,pathlib
i=json.loads(pathlib.Path('proof/IDENTITY.json').read_text())
r=json.loads(pathlib.Path('proof/RELEASE_META.json').read_text())
b=pathlib.Path('readback/'+i['asset']).read_bytes()
assert r['tag_name']=='v1.25.80' and not r['draft'] and not r['prerelease'] and len(r['assets'])==1
a=r['assets'][0]
assert a['name']==i['asset'] and a['size']==i['asset_bytes']==len(b)
assert a['digest']=='sha256:'+i['asset_sha256']=='sha256:'+hashlib.sha256(b).hexdigest()
out={'status':'PASS','version':'1.25.80','tag':r['tag_name'],'source_sha':i['source_sha'],'source_tree':i['source_tree'],'release_id':r['id'],'asset_id':a['id'],'asset_name':a['name'],'asset_bytes':a['size'],'asset_sha256':i['asset_sha256'],'runtime_files':i['runtime_files'],'runtime_fingerprint':i['runtime_fingerprint'],'released_at':r['published_at'],'candidate_run_id':int(__import__('os').environ['QA_RUN']),'production':'NOT_EXECUTED','owner_manual_upgrade':'PENDING'}
pathlib.Path('proof/FINAL_FORMAL.json').write_text(json.dumps(out,indent=2))
print('S01_C03_12580_FORMAL_RELEASE_PASS',json.dumps(out))
PY
