import pathlib,json,os
p=pathlib.Path('proof')
records={k:json.loads((p/(name+'.json')).read_text()) for k,name in [('controls','live-browser'),('public','public-output'),('paired','paired-output'),('versions','installed-versions'),('package','package-identity')]}
assert all(x['status']=='PASS' for x in records.values())
assert len(records['controls']['checks'])==6 and all(x['status']=='PASS' for x in records['controls']['checks'])
assert len(records['controls']['tests'])==60
assert not records['controls']['errors']
assert records['versions']['theme']==os.environ['TARGET_VERSION'] and records['versions']['provider']==os.environ['PROVIDER_VERSION']
r={'status':'PASS','scope':'THM-SEO-001 current formal Theme plus actual C03 provider, bounded controls and public SEO outputs','source_sha':os.environ['TARGET_SHA'],'source_tree':os.environ['TARGET_TREE'],'theme_version':os.environ['TARGET_VERSION'],'provider_version':os.environ['PROVIDER_VERSION'],'control_cases':len(records['controls']['tests']),'public_cases':len(records['public']['tests']),'paired_cases':len(records['paired']['tests']),'widths':[x['width'] for x in records['controls']['checks']],'original_assertions_preserved':True,'harness_adaptation':'selected route identified by canonical routeId, not assumed array offset zero','production':'NOT_EXECUTED','owner_acceptance':'NOT_CLAIMED','domain_algorithms':'NOT_CLAIMED','run_id':os.environ['GITHUB_RUN_ID']}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(r,indent=2))
print('VF_SEO_FINAL_BEGIN');print(json.dumps(r));print('VF_SEO_FINAL_END')
for name in ['FINAL_EVIDENCE','package-identity','live-browser','public-output','paired-output','installed-versions','performance']:
 print('VF_RECORD_BEGIN '+name);print((p/(name+'.json')).read_text());print('VF_RECORD_END '+name)
