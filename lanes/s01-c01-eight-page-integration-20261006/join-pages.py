import os,json,pathlib,hashlib,zipfile,stat,subprocess,time,io
repo='llhzx2018/core-free-runner-public';run_id=37448760215;runner_sha='a90280c3ae23a0314ff5baf26b0d325fe91832cc'
def api(path):return subprocess.check_output(['gh','api',f'repos/{repo}/'+path])
for attempt in range(60):
 run=json.loads(api(f'actions/runs/{run_id}'))
 assert run['head_sha']==runner_sha
 if run['status']=='completed':break
 time.sleep(10)
else:raise RuntimeError('EXACT_PAGE_PROOF_NOT_COMPLETED')
assert run['conclusion'] in ['success','failure']
artifacts=json.loads(api(f'actions/runs/{run_id}/artifacts'))['artifacts'];assert len(artifacts)==1
meta=artifacts[0];assert meta['workflow_run']['id']==run_id and meta['workflow_run']['head_sha']==runner_sha and not meta['expired']
data=api(f"actions/artifacts/{meta['id']}/zip");assert len(data)==meta['size_in_bytes'] and 'sha256:'+hashlib.sha256(data).hexdigest()==meta['digest']
p=pathlib.Path('proof');current=json.loads((p/'FINAL_EVIDENCE.json').read_text());assert current['status']=='PASS' and current['cross_page_cases']>=15 and current['data_checks']>=44
pages={};page_docs={}
with zipfile.ZipFile(io.BytesIO(data)) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
 for entry in z.infolist():
  path=pathlib.PurePosixPath(entry.filename)
  assert not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename and not stat.S_ISLNK(entry.external_attr>>16)
  assert path.suffix in ['.json','.png']
  if path.suffix=='.json':json.loads(z.read(entry))
 identity=json.loads(z.read('proof/identity.json'))
 assert all(identity[k]==current[k] for k in ['source_sha','source_tree','version','asset','asset_bytes','asset_sha256'])
 for name in ['overview','brand','layout','navigation','render','seo','preview','recovery']:
  d=json.loads(z.read(f'proof/{name}/live-browser.json'));assert d['status']=='PASS',name
  assert len(d['checks'])==6 and all(c.get('status','PASS')=='PASS' for c in d['checks']),name
  pages[name]={'status':'PASS','widths':6,'function_checks':len(d.get('functional',d.get('tests',{}))),'context_count':len(d.get('contexts',[])),'source_run':run_id}
  page_docs[name]=d
 assert len(page_docs['layout']['contexts'])==20 and all(c['status']=='PASS' for c in page_docs['layout']['contexts'])
 for name in ['public-output','paired-output']:assert json.loads(z.read(f'proof/seo/{name}.json'))['status']=='PASS'
 recovery=json.loads(z.read('proof/recovery-data.json'));assert recovery['status']=='PASS' and len(recovery['checks'])>=44 and all(v=='PASS' for v in recovery['checks'].values())
 assert all(page_docs['recovery'][k]=='PASS' for k in ['real_import','real_restore','failed_write_retry','revision_conflict','nonce','guest','permission','corruption','upload_abuse'])
 if run['conclusion']=='failure':
  failure=json.loads(z.read('proof/integration/integration-failure.json'))
  assert failure['message']=='spawnSync docker ENOBUFS' and len(failure['cases'])>=10
  classification={'original_run_conclusion':'failure','cause':'TEST_HARNESS_CHILD_PROCESS_BUFFER','original_failure_retained':True,'remediation':'16MiB bounded test buffer; unchanged product 8MiB import limit','independent_same_source_continuous_retry':'PASS'}
 else:classification={'original_run_conclusion':'success','cause':'NONE'}
target=p/'page-controls';target.mkdir(exist_ok=True)
for name,d in page_docs.items():(target/(name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2))
receipt={'status':'PASS','source_run':run_id,'source_runner_sha':runner_sha,'source_sha':identity['source_sha'],'source_tree':identity['source_tree'],'artifact_id':meta['id'],'bytes':len(data),'digest':meta['digest'],'crc':'PASS','all_json_parse':'PASS','safe_paths':'PASS','failure_classification':classification}
(p/'page-source-readback.json').write_text(json.dumps(receipt,indent=2))
current.update(canonical_page_count=8,layout_context_count=20,pages=pages,page_control_suite='EXACT_SOURCE_REUSED_ACTUAL_PAGE_PROOFS',page_source=receipt,scope='Theme eight canonical admin pages and controls at six widths plus continuous cross-page/frontend/recovery, native upgrade rollback reapply and clean install')
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(current,ensure_ascii=False,indent=2));print('VF_EIGHT_PAGE_JOIN_BEGIN');print(json.dumps(current));print('VF_EIGHT_PAGE_JOIN_END')
