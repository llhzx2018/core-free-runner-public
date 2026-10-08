import os,json,pathlib
p=pathlib.Path('proof')
names=['identity.json','preview-baseline.json','preview-controls.json','preview-workflow.json','preview-artifact-preservation.json','preview-browser-errors.json','preview-state-wordpress.json','preview-security.json','preview-result-widths.json','preview-component.json','upgrade-rollback.json','clean-install.json','installed-versions.json','performance.json']
d={name:json.loads((p/name).read_text()) for name in names}
assert d['preview-baseline.json']['status']=='REPRODUCED'
assert all(v['status']=='PASS' for name,v in d.items() if name!='preview-baseline.json')
assert len(d['preview-controls.json']['rows'])==6
assert d['preview-controls.json']['canonical_state_preserved']
assert d['clean-install.json']['setup_revisit']=='LOCKED_ALREADY_INSTALLED'
assert d['preview-workflow.json']['roundtrip']['domain_count']==6
assert d['preview-workflow.json']['roundtrip']['revision_restored'] and d['preview-workflow.json']['roundtrip']['journal_clean']
r=json.loads((p/'installed-runtime.json').read_text())
assert r['fingerprint_sha256']==d['identity.json']['runtime_fingerprint'] and r['file_count']==d['identity.json']['runtime_files']
result={**d['identity.json'],'status':'PASS','scope':'THM-PREVIEW-001 independent preview plus workflow regression','controls_widths':6,'actual_job_verdicts':d['preview-workflow.json']['modes'],'canonical_state_preserved':True,'upgrade':'PASS','rollback':'PASS','reapply':'PASS','repeat_install':'PASS','clean_install':'PASS','production':'NOT_EXECUTED','owner_real_use':'PENDING_POST_MANUAL_UPGRADE'}
(p/'FINAL_EVIDENCE.json').write_text(json.dumps(result,indent=2))
for name in names+['FINAL_EVIDENCE.json']:
 print('VF_JSON_BEGIN '+name);print((p/name).read_text());print('VF_JSON_END '+name)
