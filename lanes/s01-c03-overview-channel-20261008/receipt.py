import pathlib,json,hashlib,zipfile,os
m=json.loads(pathlib.Path('/tmp/channel-proof-meta.json').read_text());data=pathlib.Path('/tmp/channel-proof.zip').read_bytes()
assert m['id']==int(os.environ['PROOF_ID']) and m['workflow_run']['id']==int(os.environ['GITHUB_RUN_ID']) and m['workflow_run']['head_sha']==os.environ['GITHUB_SHA'] and m['size_in_bytes']==len(data) and m['digest']=='sha256:'+hashlib.sha256(data).hexdigest() and not m['expired']
with zipfile.ZipFile('/tmp/channel-proof.zip') as z:
 assert z.testzip() is None
 f=json.loads(z.read('FINAL_CHANNEL.json'));assert f['status']=='PASS' and f['source_sha']==os.environ['TARGET_SHA'] and f['source_tree']==os.environ['TARGET_TREE']
r={'status':'PASS','artifact_id':m['id'],'bytes':len(data),'digest':m['digest'],'source_sha':f['source_sha'],'source_tree':f['source_tree'],'run_id':int(os.environ['GITHUB_RUN_ID']),'runner_sha':os.environ['GITHUB_SHA'],'crc':'PASS'}
print('VF_CHANNEL_RECEIPT_BEGIN');print(json.dumps(r));print('VF_CHANNEL_RECEIPT_END')

