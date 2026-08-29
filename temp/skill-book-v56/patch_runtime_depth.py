from pathlib import Path


def repl(s, old, new, label, count=1):
    got = s.count(old)
    assert got == count, (label, got, count)
    return s.replace(old, new)


# runtime_acceptance_audit.py
p = Path('scripts/runtime_acceptance_audit.py')
s = p.read_text(encoding='utf-8')
s = repl(
    s,
    "ADEQ=ROOT/'adequacy_audit.py'\nBASE=ROOT/'postdraft_baseline_audit.py'",
    "ADEQ=ROOT/'adequacy_audit.py'\nDEPTH=ROOT/'practical_asset_depth_audit.py'\nBASE=ROOT/'postdraft_baseline_audit.py'",
    'runtime-depth-script',
)
s = repl(
    s,
    "'evidence/training_feedback_contract.json','evidence/training_feedback_pre_freeze.json','evidence/adequacy_contract.json','evidence/adequacy_audit.json',\n 'evidence/prefreeze_random_open.json'",
    "'evidence/training_feedback_contract.json','evidence/training_feedback_pre_freeze.json','evidence/adequacy_contract.json','evidence/adequacy_audit.json',\n 'evidence/practical_asset_depth_contract.json','evidence/practical_asset_depth_audit.json',\n 'evidence/prefreeze_random_open.json'",
    'runtime-receipt-list',
)
s = repl(
    s,
    "    declared_adequacy=root/'evidence'/'adequacy_audit.json'\n    if not declared_adequacy.exists(): blocks.append('ADEQUACY_AUDIT_EVIDENCE_MISSING')\n    reader_contract=root/'evidence'/'reader_transformation_contract.json'",
    "    declared_adequacy=root/'evidence'/'adequacy_audit.json'\n    if not declared_adequacy.exists(): blocks.append('ADEQUACY_AUDIT_EVIDENCE_MISSING')\n    depth_contract=root/'evidence'/'practical_asset_depth_contract.json'\n    if not depth_contract.exists(): blocks.append('PRACTICAL_ASSET_DEPTH_CONTRACT_EVIDENCE_MISSING')\n    declared_depth=root/'evidence'/'practical_asset_depth_audit.json'\n    if not declared_depth.exists(): blocks.append('PRACTICAL_ASSET_DEPTH_AUDIT_EVIDENCE_MISSING')\n    reader_contract=root/'evidence'/'reader_transformation_contract.json'",
    'runtime-depth-evidence',
)
s = repl(
    s,
    "        ao=Path(td)/'adequacy.json';cp,ar=run_json([sys.executable,str(ADEQ),'--new',str(root),'--json',str(ao)],ao)\n        if cp.returncode!=0 or not ar or ar.get('decision')!='PASS': blocks.append('ADEQUACY_EXTERNAL_REAUDIT_BLOCK')\n        ro=Path(td)/'responsibility.json'",
    "        ao=Path(td)/'adequacy.json';cp,ar=run_json([sys.executable,str(ADEQ),'--new',str(root),'--json',str(ao)],ao)\n        if cp.returncode!=0 or not ar or ar.get('decision')!='PASS': blocks.append('ADEQUACY_EXTERNAL_REAUDIT_BLOCK')\n        deptho=Path(td)/'practical_asset_depth.json';cpd,drsp=run_json([sys.executable,str(DEPTH),'--new',str(root),'--json',str(deptho)],deptho)\n        if cpd.returncode!=0 or not drsp or drsp.get('decision')!='PASS': blocks.append('PRACTICAL_ASSET_DEPTH_EXTERNAL_REAUDIT_BLOCK')\n        ro=Path(td)/'responsibility.json'",
    'runtime-depth-reaudit',
)
s = repl(
    s,
    "'adequacy_external':ar if 'ar' in locals() else None,'generation_responsibility_external':",
    "'adequacy_external':ar if 'ar' in locals() else None,'practical_asset_depth_external':drsp if 'drsp' in locals() else None,'generation_responsibility_external':",
    'runtime-depth-report',
)
p.write_text(s, encoding='utf-8')


# test_runtime_acceptance_audit.py
p = Path('tests/test_runtime_acceptance_audit.py')
s = p.read_text(encoding='utf-8')
s = repl(
    s,
    ";ADEQ=R/'scripts'/'adequacy_audit.py';RESP=R/'scripts'/'generation_responsibility_audit.py'",
    ";ADEQ=R/'scripts'/'adequacy_audit.py';DEPTH=R/'scripts'/'practical_asset_depth_audit.py';RESP=R/'scripts'/'generation_responsibility_audit.py'",
    'fixture-depth-script',
)
old = "'evidence/adequacy_contract.json','evidence/adequacy_audit.json','evidence/prefreeze_random_open.json'"
new = "'evidence/adequacy_contract.json','evidence/adequacy_audit.json','evidence/practical_asset_depth_contract.json','evidence/practical_asset_depth_audit.json','evidence/prefreeze_random_open.json'"
s = repl(s, old, new, 'fixture-depth-lists', 2)

depth_append_source = (
    "DEPTH_TOOL_APPEND='\\n## V5.6 Evidence Trace\\nRecord ID: ____ Source / actor: ____ Date: ____ Action / observation: ____ Result: ____ Interpretation: ____ Linked decision/change: ____"
    "\\n## V5.6 Decision Review\\nOptions: A / B. Criteria / threshold: ____ Evidence source: ____ Selected option: ____ Rationale / tradeoff: ____ Uncertainty: ____ Revisit trigger: ____"
    "\\n## V5.6 Change Control\\nBaseline version: ____ Proposed change: ____ Change reason / evidence: ____ Owner / authority: ____ Impact: ____ Revalidation: ____ Accept / Reject / Defer: ____ Superseded version / rollback target: ____"
    "\\n## V5.6 Recovery Loop\\nFailure trigger: ____ Diagnosis / likely cause: ____ Recovery action: ____ Retry condition: ____ Post-retry evidence: ____ Escalate or pause when: ____"
    "\\n## V5.6 Acceptance\\nExpected: ____ Actual: ____ Verification method: ____ PASS / FAIL / PARTIAL: ____ Defect / rework: ____"
    "\\n## V5.6 Completion\\nCompletion: close only when required evidence is attached and blockers are handed off.\\n'\n"
)
s = repl(s, "def rich_tool(i):\n", depth_append_source + "def rich_tool(i):\n", 'fixture-depth-append-definition')
s = repl(s, "w(new/rel,rich_tool(i))", "w(new/rel,rich_tool(i)+DEPTH_TOOL_APPEND)", 'fixture-depth-append-use')

old = "  w(new/'evidence'/'adequacy_contract.json',json.dumps({'chapters':chapters,'assets':assets},ensure_ascii=False))\n  rtc="
new = (
    "  w(new/'evidence'/'adequacy_contract.json',json.dumps({'chapters':chapters,'assets':assets},ensure_ascii=False))\n"
    "  depth_dims={'decision_record':['input_evidence','decision_rule','completion'],'plan_or_contract':['context_task','change_control','validation_acceptance','completion'],'execution_brief_or_log':['input_evidence','execution_steps','evidence_log','failure_recovery','validation_acceptance','completion'],'acceptance_record':['validation_acceptance','completion'],'iteration_log':['evidence_log','decision_rule','completion']}\n"
    "  depth_assets=[{'path':asset_paths[i],'roles':[c],'complexity':'HIGH','required_dimensions':depth_dims[c],'n_a':{},'promise_links':['fixture_do']} for i,c in enumerate(classes)]\n"
    "  w(new/'evidence'/'practical_asset_depth_contract.json',json.dumps({'schema':'skill-book.practical-asset-depth.v1','assets':depth_assets},ensure_ascii=False))\n"
    "  rtc="
)
s = repl(s, old, new, 'fixture-depth-contract')
s = repl(
    s,
    "  genprom('ADEQUACY',ADEQ,['--new',str(new)],new/'evidence'/'adequacy_audit.json')\n  genprom('GEN_RESP_PRE_DRAFT'",
    "  genprom('ADEQUACY',ADEQ,['--new',str(new)],new/'evidence'/'adequacy_audit.json')\n  depthout=new/'evidence'/'practical_asset_depth_audit.json';cpd=run_report(DEPTH,['--new',str(new)],depthout);assert cpd.returncode==0,cpd.stdout+cpd.stderr\n  genprom('GEN_RESP_PRE_DRAFT'",
    'fixture-depth-audit',
)
marker = " def test_good_evidence_truth_passes_when_runtime_writes_authority_path(self):"
insert = (
    " def test_practical_asset_depth_evidence_is_runtime_mandatory(self):\n"
    "  td,old,new=self.fixture(False);(new/'evidence'/'practical_asset_depth_audit.json').unlink();cp,r=self.audit(old,new,True,False);self.assertNotEqual(cp.returncode,0);self.assertIn('PRACTICAL_ASSET_DEPTH_AUDIT_EVIDENCE_MISSING',r['blocks']);td.cleanup()\n"
    + marker
)
s = repl(s, marker, insert, 'fixture-depth-runtime-test')
p.write_text(s, encoding='utf-8')

print('RUNTIME_DEPTH_PATCH_APPLIED')
