import json, os, pathlib, shutil, subprocess

# The prior job's later failure was its stale test-version expectation, after
# controls had completed. Reuse only that completed scope, never its run verdict.
prior = pathlib.Path('control-proof')
proof = pathlib.Path('proof')
old = json.loads((prior/'identity.json').read_text())
new = json.loads((proof/'identity.json').read_text())
assert old['source_sha'] == os.environ['CONTROL_PROOF_SHA']
assert old['source_tree'] == os.environ['CONTROL_PROOF_TREE']
delta = subprocess.check_output(['git','-C','target','diff','--name-only',old['source_sha'],new['source_sha']], text=True).splitlines()
assert delta == ['tests/layout-v8-browser-check.js'], delta
for key in ['version','asset','asset_bytes','asset_sha256']:
    assert old[key] == new[key], key+' runtime bytes changed; controls must rerun'
controls = json.loads((prior/'layout-controls.json').read_text())
assert controls['status'] == 'PASS' and len(controls['cases']) == 40 and len(controls['checks']) == 2286
assert all(c['control_save_reload']=='PASS' and c['section_isolation']=='PASS' and c['module_controls']=='PASS' for c in controls['cases'])
runtime = json.loads((prior/'runtime.json').read_text())
shutil.copy2(prior/'layout-controls.json',proof/'layout-controls.json')
provenance = dict(proof_run=os.environ['CONTROL_PROOF_RUN'], proof_source=old['source_sha'], proof_tree=old['source_tree'], current_source=new['source_sha'], asset_sha256=new['asset_sha256'], runtime_files=runtime['runtime_files'], runtime_fingerprint=runtime['runtime_fingerprint'], only_delta=delta, verdict='PASS_IDENTICAL_RUNTIME_BYTES', reused_scope='layout-controls only; no previous whole-run PASS')
(proof/'layout-controls-provenance.json').write_text(json.dumps(provenance,indent=2))
print(json.dumps(provenance))
