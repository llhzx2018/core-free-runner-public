import json,os,pathlib,hashlib,zipfile,stat
run=json.loads(pathlib.Path('/tmp/formal-run.json').read_text());m=json.loads(pathlib.Path('/tmp/formal-meta.json').read_text());data=pathlib.Path('/tmp/formal-proof.zip').read_bytes()
assert run['id']==int(os.environ['FORMAL_RUN']) and run['conclusion']=='success' and run['head_sha']==os.environ['FORMAL_RUNNER_SHA']
assert m['workflow_run']['id']==run['id'] and m['workflow_run']['head_sha']==run['head_sha'] and m['id']==int(os.environ['FORMAL_ARTIFACT_ID']) and m['size_in_bytes']==len(data) and m['digest']=='sha256:'+hashlib.sha256(data).hexdigest() and not m['expired']
with zipfile.ZipFile('/tmp/formal-proof.zip') as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
 for i in z.infolist():
  p=pathlib.PurePosixPath(i.filename);assert p.suffix=='.json' and not p.is_absolute() and '..' not in p.parts and not stat.S_ISLNK(i.external_attr>>16);json.loads(z.read(i))
 f=json.loads(z.read('FINAL_RELEASE.json'))
assert f['status']=='PASS' and f['source_sha']==os.environ['COMPONENT_SOURCE_SHA'] and f['version']==os.environ['TARGET_VERSION'] and f['production']=='NOT_EXECUTED'
pathlib.Path('proof/formal-reverse.json').write_text(json.dumps({'status':'PASS','run_id':run['id'],'runner_sha':run['head_sha'],'artifact_id':m['id'],'bytes':len(data),'digest':m['digest'],'final':f},indent=2))


