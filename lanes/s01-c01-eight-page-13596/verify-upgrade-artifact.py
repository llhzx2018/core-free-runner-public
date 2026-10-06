import os,json,pathlib,hashlib,zipfile,stat
meta=json.loads(pathlib.Path('/tmp/upgrade-artifact-meta.json').read_text())
data=pathlib.Path('/tmp/upgrade-artifact.zip').read_bytes()
assert meta['id']==int(os.environ['UPGRADE_ARTIFACT_ID']) and meta['workflow_run']['id']==int(os.environ['UPGRADE_RUN'])
assert meta['workflow_run']['head_sha']==os.environ['UPGRADE_RUNNER_SHA'] and not meta['expired']
assert meta['digest']==os.environ['UPGRADE_ARTIFACT_DIGEST']=='sha256:'+hashlib.sha256(data).hexdigest()
assert meta['size_in_bytes']==len(data)
with zipfile.ZipFile('/tmp/upgrade-artifact.zip') as z:
 assert z.testzip() is None
 names=z.namelist();assert len(names)==len(set(names))
 for entry in z.infolist():
  p=pathlib.PurePosixPath(entry.filename)
  assert not p.is_absolute() and '..' not in p.parts and '\\' not in entry.filename and not stat.S_ISLNK(entry.external_attr>>16)
  assert p.suffix in ['.json','.png']
  if p.suffix=='.json':json.loads(z.read(entry))
 z.extractall('upgrade-tested')
p=pathlib.Path('upgrade-tested/proof');final=json.loads((p/'FINAL_EVIDENCE.json').read_text())
assert final['source_sha']==os.environ['CANDIDATE_SHA'] and final['source_tree']==os.environ['TARGET_TREE'] and final['version']==os.environ['TARGET_VERSION']
assert all(final[k]=='PASS' for k in ['status','upgrade','source_rollback','reapply','clean_install','security_boundary','frozen_shell_header_menu'])
assert final['baseline_defect']=='REPRODUCED' and final['data_checks']>=44 and final['cross_page_cases']>=15
layout=json.loads((p/'page-controls/layout.json').read_text());assert layout['status']=='PASS' and len(layout['checks'])==6 and len(layout['contexts'])==20
full=json.loads(pathlib.Path('tested/proof/FINAL_EVIDENCE.json').read_text())
assert all(final[k]==full[k] for k in ['asset','asset_bytes','asset_sha256','source_sha','source_tree','version'])
print('EXACT_NATIVE_UPGRADE_RECOVERY_GATE=PASS')
