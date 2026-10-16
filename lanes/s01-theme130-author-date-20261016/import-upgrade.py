import json,pathlib,subprocess,hashlib,zipfile,io,stat,os
repo='llhzx2018/core-free-runner-public';run=38910836816;artifact=12050766888;digest='sha256:de210aeede54e9fbb212601e39d5209c9c7b7b893551f74e33999b9c2e4b54e8';head='5d08d90770b1b046ff4716cc19c01a6140ef4ac3'
def api(path):return subprocess.check_output(['gh','api','repos/'+repo+'/'+path])
meta=json.loads(api('actions/artifacts/'+str(artifact)));data=api('actions/artifacts/'+str(artifact)+'/zip');r=json.loads(api('actions/runs/'+str(run)))
assert r['status']=='completed' and r['conclusion']=='failure' and r['head_sha']==head
assert meta['workflow_run']['id']==run and meta['workflow_run']['head_sha']==head and meta['size_in_bytes']==len(data) and not meta['expired']
assert meta['digest']==digest=='sha256:'+hashlib.sha256(data).hexdigest()
p=pathlib.Path('proof')
with zipfile.ZipFile(io.BytesIO(data)) as z:
 assert z.testzip() is None
 for f in z.infolist():
  n=pathlib.PurePosixPath(f.filename);assert not n.is_absolute() and '..' not in n.parts and not stat.S_ISLNK(f.external_attr>>16) and n.suffix in ['.json','.png']
 old=json.loads(z.read('identity.json'));new=json.loads((p/'identity.json').read_text())
 for key in ['source_sha','source_tree','version','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint']:assert old[key]==new[key],key
 assert old['source_sha']==os.environ['TARGET_SHA'] and old['source_tree']==os.environ['TARGET_TREE']
 for name in ['wordpress','wordpress-clean','browser-candidate','browser-reapply','browser-clean']:
  result=json.loads(z.read(name+'.json'));assert result['status']=='PASS' and all(c['pass'] for c in result['checks'])
  assert len(result['checks'])==(36 if name.startswith('wordpress') else 218)
 before=z.read('state-before.json')
 for phase in ['candidate','rollback','reapply','idempotent']:assert z.read('state-'+phase+'.json')==before
 cold=json.loads(z.read('state-clean-before.json'));warm=json.loads(z.read('state-clean-after.json'))
 assert cold['postTypes']==warm['postTypes']
 assert all(cold['stores'][k]==v for k,v in warm['stores'].items() if k!='theme_mods_vf-tools-theme')
 assert 'custom_css_post_id' not in cold['themeModFields'] and warm['themeModFields']['custom_css_post_id']==hashlib.sha256(b'-1').hexdigest()
 assert {k:v for k,v in warm['themeModFields'].items() if k!='custom_css_post_id'}==cold['themeModFields']
 keep=['wordpress.json','browser-candidate.json','browser-reapply.json','state-before.json','state-candidate.json','state-rollback.json','state-reapply.json','state-idempotent.json','baseline-observation.json']
 keep += [n for n in z.namelist() if n.endswith('.png') and ('-candidate-' in n or '-reapply-' in n)]
 for name in keep:(p/name).write_bytes(z.read(name))
receipt={'status':'PASS','classification':'HARNESS_COLD_FIRST_PUBLIC_CORE_LAZY_DEFAULT_ONLY','imported_run':run,'imported_runner_sha':head,'imported_artifact':artifact,'imported_digest':digest,'source_sha':old['source_sha'],'source_tree':old['source_tree'],'fresh_package_equals_imported':'PASS','imported_browser_checks':{'candidate':218,'reapply':218,'prior_clean':218},'imported_existing_state_preservation':'PASS_BYTE_IDENTICAL','old_clean_only_delta':'WordPress first public request initializes theme_mod custom_css_post_id=-1; all existing mod fields, protected stores, postmeta/content/translations/mounts unchanged','correction':'Warm public home in both languages and admin before readonly clean comparison; keep separate cold snapshot; exclude no fields','clean_reverification':'REQUIRED_IN_CURRENT_RUN','production':'NOT_EXECUTED'}
(p/'upgrade-evidence-import.json').write_text(json.dumps(receipt,indent=2));print('PASS exact unchanged-source upgrade/rollback/reapply evidence imported; clean recheck required')
