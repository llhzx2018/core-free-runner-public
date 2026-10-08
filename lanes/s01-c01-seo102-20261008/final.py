import os,json,pathlib
p=pathlib.Path('proof')
files=['identity.json','provider-actual.json','provider-baseline.json','provider-rollback.json','provider-reapply.json','upgrade-rollback.json','clean-install.json','live-browser.json','public-output.json','paired-output.json','directory-browser.json','performance.json','envelope-contract.json','flat-contract.json','null-contract.json','heading-contract.json']
d={name:json.loads((p/name).read_text()) for name in files}
assert all(v['status']=='PASS' for k,v in d.items() if k not in ['provider-baseline.json','provider-rollback.json'])
assert d['provider-baseline.json']['status']==d['provider-rollback.json']['status']=='REPRODUCED'
assert d['provider-actual.json']['registry_count']==11 and d['provider-actual.json']['language_pages']==22
assert len(d['live-browser.json']['tests'])==60
assert len(d['directory-browser.json']['rows'])==6
for name in ['public-output.json','paired-output.json']:assert d[name]['status']=='PASS'
runtime=json.loads((p/'installed-runtime.json').read_text())
assert runtime['file_count']==d['identity.json']['runtime_files'] and runtime['fingerprint_sha256']==d['identity.json']['runtime_fingerprint']
result={**d['identity.json'],'status':'PASS','upgrade':'PASS','rollback':'PASS','reapply':'PASS','clean_install':'PASS','canonical_data_preservation':'PASS','provider_actual_language_reads':22,'provider_acceptance':'NOT_PROVEN_FAIL_CLOSED_PRESERVED','seo_controls_cases':60,'head_xml':'PASS','polylang':'PASS','directory_widths':6,'owner_real_use':'PENDING_POST_MANUAL_UPGRADE','production':'NOT_EXECUTED'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2))
for name in files+['FINAL_EVIDENCE.json']:
 print('VF_JSON_BEGIN '+name);print((p/name).read_text());print('VF_JSON_END '+name)
