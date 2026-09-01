from pathlib import Path
import json

p=Path('VF_PROJECT.json')
data=json.loads(p.read_text())
if data.get('production_version')!='2.36.0': raise SystemExit('production version drift')
if data.get('candidate_version')!='2.36.1': raise SystemExit('candidate version drift')
if data.get('schema_version')!='2026082901': raise SystemExit('schema drift')
rc=data.get('v2_36_1_release_candidate') or {}
if rc.get('product_fix_merge')!='2b60b27c1e5cb53f841e9e7f0c8e521bacba1030': raise SystemExit('product fix authority drift')
if rc.get('schema_change') is not False or rc.get('migration') is not None: raise SystemExit('migration boundary drift')

data['status']='V2.36.0 PRODUCTION CLOSURE PASS / V2.36.1 CANDIDATE PASS'
data['current_phase']='V2.36.1 CANDIDATE PASS / FORMAL ARTIFACT PENDING'
data['candidate_state']='PASS'
data['formal_release_state']='V2.36.0 PUBLISHED / PRODUCTION CLOSURE PASS / V2.36.1 FORMAL ARTIFACT PENDING'
data['develop_state']='V2.36.1 FORMAL PATCH SOURCE PREPARED / SINGLE-SYSTEM AUTH MODEL RESTORED / NOT RELEASED'
data['current_authority']='Owner Production V2.36.0 / Published Latest V2.36.0 / V2.36.1 Candidate Readiness PASS on exact 411404af399fc13856d71faec1ab4a6633a73ba3'
data['next_action']='Run V2.36.1 Formal Artifact Gate on the exact formal source after Candidate PASS binding. Do not promote main, publish Tag/Release, mutate core-updates or write Owner Production before subsequent gates pass.'
data['v2_36_1_candidate_gate']={
  'run':33472637909,
  'result':'PASS',
  'source':'411404af399fc13856d71faec1ab4a6633a73ba3',
  'tree':'d09ddb545c0c46cc2076ac1836c7857af31bc6e2',
  'runtime_tree':'91f92c5d3e7080469a7f5ab1497145454014c87a',
  'artifact':9787058642,
  'artifact_digest':'sha256:1e6dfd1aa9b7612f5ccf0b85bc46919979f224a0e75734680bce0de2b0ebcf60',
  'schema':'2026082901',
  'migration':None,
  'runtime_delta_files':10,
  'runtime_added':[],
  'runtime_removed':[],
  'atomic_upgrade':'2.36.0 -> 2.36.1 / PASS',
  'fresh_install':'PASS / BUSINESS DATA ZERO',
  'single_system_auth':'390 + 1440 / ANONYMOUS PUBLIC ONLY / AUTHENTICATED PUBLIC+PRIVATE+MANAGEMENT / PASS',
  'sqlite_integrity_fk':'PASS',
  'candidate_full_sha256':'1d0bedc8cc4878ae0dc6426d53d2e3a386930e0facc71c7b17595b78a34e5bb9',
  'candidate_update_sha256':'1dfb10277881a2a18cb7bb809bc3173756bdd3e06114b5895b0bd6c9a98249bc',
  'candidate_repair_sha256':'3e8a40d35972f2f1c210752e78a810dcd96dcd87d4c3ea6d85bdcb19505dfb8a',
  'release_published':False,
  'owner_production_write':False
}
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
