import os,json,pathlib
p=pathlib.Path('proof')
names=['identity.json','provider-actual.json','provider-reapply.json','footer-browser.json','footer-variant-four.json','footer-variant-simple.json','footer-variant-accordion.json','upgrade-rollback.json','clean-install.json','installed-versions.json','provider-contract.json','directory-contract.json','heading-contract.json','performance.json']
d={name:json.loads((p/name).read_text()) for name in names}
assert all(v['status']=='PASS' for v in d.values())
assert json.loads((p/'provider-baseline.json').read_text())['status']=='PASS'
assert json.loads((p/'provider-rollback.json').read_text())['status']=='PASS'
assert json.loads((p/'footer-baseline.json').read_text())['status']=='REPRODUCED'
assert json.loads((p/'footer-rollback.json').read_text())['status']=='REPRODUCED'
assert len(d['footer-browser.json']['rows'])==6 and d['footer-browser.json']['directory_tools']==11
r=json.loads((p/'installed-runtime.json').read_text());assert r['fingerprint_sha256']==d['identity.json']['runtime_fingerprint'] and r['file_count']==d['identity.json']['runtime_files']
result={**d['identity.json'],'status':'PASS','scope':'FOOTER_INVERSE_SURFACE_CASCADE_COMPATIBILITY','controls_widths':6,'canonical_state_preserved':True,'upgrade':'PASS','rollback':'PASS','reapply':'PASS','repeat_install':'PASS','clean_install':'PASS','production':'NOT_EXECUTED','owner_real_use':'PENDING_POST_MANUAL_UPGRADE'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2))
for name in names+['FINAL_EVIDENCE.json']:
 print('VF_JSON_BEGIN '+name);print((p/name).read_text());print('VF_JSON_END '+name)
