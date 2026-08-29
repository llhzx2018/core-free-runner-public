#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

repo=Path(sys.argv[1])
root=repo/'skills'/'skill-book'/'V5.7'

def patch(rel,old,new,count=1):
    p=root/rel
    s=p.read_text(encoding='utf-8')
    if s.count(old)<count:
        raise SystemExit(f'PATCH_ANCHOR_MISSING {rel}: {old[:100]!r}')
    s=s.replace(old,new,count)
    p.write_text(s,encoding='utf-8')

# Runtime Acceptance: reader-transfer verifier and mandatory evidence.
patch('scripts/runtime_acceptance_audit.py',
      "DEPTH=ROOT/'practical_asset_depth_audit.py'\nBASE=ROOT/'postdraft_baseline_audit.py'",
      "DEPTH=ROOT/'practical_asset_depth_audit.py'\nTRANSFER=ROOT/'reader_transfer_audit.py'\nBASE=ROOT/'postdraft_baseline_audit.py'")
patch('scripts/runtime_acceptance_audit.py',
      " 'evidence/practical_asset_depth_contract.json','evidence/practical_asset_depth_audit.json',\n 'evidence/prefreeze_random_open.json'",
      " 'evidence/practical_asset_depth_contract.json','evidence/practical_asset_depth_audit.json',\n 'evidence/reader_transfer_contract.json','evidence/reader_transfer_proxy.json','evidence/reader_transfer_audit.json',\n 'evidence/prefreeze_random_open.json'")
patch('scripts/runtime_acceptance_audit.py',
      "    declared_depth=root/'evidence'/'practical_asset_depth_audit.json'\n    if not declared_depth.exists(): blocks.append('PRACTICAL_ASSET_DEPTH_AUDIT_EVIDENCE_MISSING')\n    reader_contract=root/'evidence'/'reader_transformation_contract.json'",
      "    declared_depth=root/'evidence'/'practical_asset_depth_audit.json'\n    if not declared_depth.exists(): blocks.append('PRACTICAL_ASSET_DEPTH_AUDIT_EVIDENCE_MISSING')\n    transfer_contract=root/'evidence'/'reader_transfer_contract.json'\n    transfer_proxy=root/'evidence'/'reader_transfer_proxy.json'\n    declared_transfer=root/'evidence'/'reader_transfer_audit.json'\n    if not transfer_contract.exists(): blocks.append('READER_TRANSFER_CONTRACT_EVIDENCE_MISSING')\n    if not transfer_proxy.exists(): blocks.append('READER_TRANSFER_PROXY_EVIDENCE_MISSING')\n    if not declared_transfer.exists(): blocks.append('READER_TRANSFER_AUDIT_EVIDENCE_MISSING')\n    reader_contract=root/'evidence'/'reader_transformation_contract.json'")
patch('scripts/runtime_acceptance_audit.py',
      "        if cpd.returncode!=0 or not drsp or drsp.get('decision')!='PASS': blocks.append('PRACTICAL_ASSET_DEPTH_EXTERNAL_REAUDIT_BLOCK')",
      "        if cpd.returncode!=0 or not drsp or drsp.get('decision')!='PASS': blocks.append('PRACTICAL_ASSET_DEPTH_EXTERNAL_REAUDIT_BLOCK')\n        tro=Path(td)/'reader_transfer.json';cpt,trsp=run_json([sys.executable,str(TRANSFER),'--new',str(root),'--json',str(tro)],tro)\n        if cpt.returncode!=0 or not trsp or trsp.get('decision')!='PASS' or trsp.get('real_reader_evidence')!='NOT_RUN': blocks.append('READER_TRANSFER_EXTERNAL_REAUDIT_BLOCK')")

# Fidelity: transfer contract/proxy/audit are canonical Runtime Authority inputs.
patch('scripts/runtime_authority_fidelity_audit.py',
      " 'evidence/practical_asset_depth_contract.json',\n 'evidence/practical_asset_depth_audit.json',\n 'evidence/prefreeze_random_open.json',",
      " 'evidence/practical_asset_depth_contract.json',\n 'evidence/practical_asset_depth_audit.json',\n 'evidence/reader_transfer_contract.json',\n 'evidence/reader_transfer_proxy.json',\n 'evidence/reader_transfer_audit.json',\n 'evidence/prefreeze_random_open.json',")

# Runtime Acceptance fixture and expectations.
p=root/'tests'/'test_runtime_acceptance_audit.py'
s=p.read_text(encoding='utf-8')
s=s.replace(";DEPTH=R/'scripts'/'practical_asset_depth_audit.py';RESP=", ";DEPTH=R/'scripts'/'practical_asset_depth_audit.py';TRANSFER=R/'scripts'/'reader_transfer_audit.py';RESP=",1)
s=s.replace("'evidence/practical_asset_depth_audit.json','evidence/prefreeze_random_open.json'", "'evidence/practical_asset_depth_audit.json','evidence/reader_transfer_contract.json','evidence/reader_transfer_proxy.json','evidence/reader_transfer_audit.json','evidence/prefreeze_random_open.json'")
anchor="  depthout=new/'evidence'/'practical_asset_depth_audit.json';cpd=run_report(DEPTH,['--new',str(new)],depthout);assert cpd.returncode==0,cpd.stdout+cpd.stderr\n"
if anchor not in s: raise SystemExit('RUNTIME_TEST_DEPTH_ANCHOR_MISSING')
transfer_fixture="""  transfer_contract={'schema':'skill-book-reader-transfer-contract/v1','domain':'runtime-equipment-handoff','authority':{'proxy_layer':'BLIND_READER_PROXY_ONLY','real_reader_derivation':'FORBIDDEN','real_reader_evidence':'NOT_RUN'},'tasks':[{'id':'r','axis':'READ','required_responsibilities':['sequence','boundary','next_decision']},{'id':'l','axis':'LEARN','required_responsibilities':['rule','rationale','changed_case'],'near_miss':{'correct_option':'B','options':['A','B','C']}},{'id':'t','axis':'TRAIN','required_responsibilities':['evidence_link','decision_rule','completion'],'requires_retry_repair':True},{'id':'d','axis':'DO','required_responsibilities':['state','evidence','next_action','acceptance'],'requires_operator_handoff':True}]};w(new/'evidence'/'reader_transfer_contract.json',json.dumps(transfer_contract))
  transfer_proxy={'schema':'skill-book-reader-transfer-proxy/v1','domain':'runtime-equipment-handoff','source':{'kind':'BLIND_READER_PROXY','reader_id':'runtime-proxy','fresh':True,'blind_to':['generation_contract','verifier','canonical'],'real_reader':False},'results':[{'task_id':'r','axis':'READ','first_attempt':{'answer':'verify, decide, handoff','responsibilities':{'sequence':'PASS','boundary':'PASS','next_decision':'PASS'}}},{'task_id':'l','axis':'LEARN','first_attempt':{'answer':'changed evidence changes the decision','responsibilities':{'rule':'PASS','rationale':'PASS','changed_case':'PASS'}},'near_miss_choice':'B'},{'task_id':'t','axis':'TRAIN','first_attempt':{'answer':'continue','responsibilities':{'evidence_link':'FAIL','decision_rule':'FAIL','completion':'PASS'}},'feedback':{'target_responsibilities':['evidence_link','decision_rule'],'message':'Use current evidence and an explicit decision rule before continuing.'},'retry':{'answer':'hold until current evidence satisfies the explicit rule','responsibilities':{'evidence_link':'PASS','decision_rule':'PASS','completion':'PASS'},'changed_responsibilities':['evidence_link','decision_rule']}},{'task_id':'d','axis':'DO','first_attempt':{'answer':'make handoff record','responsibilities':{'state':'PASS','evidence':'PASS','next_action':'PASS','acceptance':'PASS'}},'output':{'artifact':'handoff-record','steps':['record state','attach evidence','assign action'],'acceptance_results':{'trace':'PASS','state':'PASS'}},'handoff':{'operator1':{'state_id':'x-HOLD','state':'HOLD','evidence':'e-1','next_action':'inspect','owner':'operator-b'},'operator2':{'received_state_id':'x-HOLD','received_evidence':'e-1','next_action':'inspect','result':'inspection complete','acceptance':'PASS'}}}]};w(new/'evidence'/'reader_transfer_proxy.json',json.dumps(transfer_proxy))
  transferout=new/'evidence'/'reader_transfer_audit.json';cpt=run_report(TRANSFER,['--new',str(new)],transferout);assert cpt.returncode==0,cpt.stdout+cpt.stderr
"""
s=s.replace(anchor,anchor+transfer_fixture,1)
method_anchor=" def test_practical_asset_depth_evidence_is_runtime_mandatory(self):\n  td,old,new=self.fixture(False);(new/'evidence'/'practical_asset_depth_audit.json').unlink();cp,r=self.audit(old,new,True,False);self.assertNotEqual(cp.returncode,0);self.assertIn('PRACTICAL_ASSET_DEPTH_AUDIT_EVIDENCE_MISSING',r['blocks']);td.cleanup()\n"
if method_anchor not in s: raise SystemExit('RUNTIME_TEST_METHOD_ANCHOR_MISSING')
method_new=method_anchor+" def test_reader_transfer_evidence_is_runtime_mandatory(self):\n  td,old,new=self.fixture(False);(new/'evidence'/'reader_transfer_audit.json').unlink();cp,r=self.audit(old,new,True,False);self.assertNotEqual(cp.returncode,0);self.assertIn('READER_TRANSFER_AUDIT_EVIDENCE_MISSING',r['blocks']);td.cleanup()\n"
s=s.replace(method_anchor,method_new,1)
p.write_text(s,encoding='utf-8')

# Fidelity tests: canonical input set + explicit deletion test.
p=root/'tests'/'test_runtime_authority_fidelity_audit.py'
s=p.read_text(encoding='utf-8')
s=s.replace("'evidence/practical_asset_depth_audit.json','evidence/prefreeze_random_open.json'", "'evidence/practical_asset_depth_audit.json','evidence/reader_transfer_contract.json','evidence/reader_transfer_proxy.json','evidence/reader_transfer_audit.json','evidence/prefreeze_random_open.json'",1)
anchor="def test_depth_inputs_are_canonical_runtime_inputs(tmp_path):\n fixture(tmp_path);(tmp_path/'evidence'/'practical_asset_depth_audit.json').unlink();cp,r=run(tmp_path);assert cp.returncode!=0;assert 'CANONICAL_RUNTIME_INPUTS_MISSING' in r['blocks']\n"
if anchor not in s: raise SystemExit('FIDELITY_TEST_ANCHOR_MISSING')
s=s.replace(anchor,anchor+"def test_reader_transfer_inputs_are_canonical_runtime_inputs(tmp_path):\n fixture(tmp_path);(tmp_path/'evidence'/'reader_transfer_audit.json').unlink();cp,r=run(tmp_path);assert cp.returncode!=0;assert 'CANONICAL_RUNTIME_INPUTS_MISSING' in r['blocks']\n",1)
p.write_text(s,encoding='utf-8')

print('V57_RUNTIME_TRANSFER_PATCH_APPLIED')
