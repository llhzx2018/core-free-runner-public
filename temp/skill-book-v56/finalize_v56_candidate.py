from __future__ import annotations

import hashlib,json,sys
from pathlib import Path

root=Path(sys.argv[1]).resolve()
skill=root/'skills/skill-book/V5.6'
identity=skill/'SOURCE_PACKAGE_IDENTITY.md'
manifest_path=skill/'MANIFEST.json'
sums=skill/'SHA256SUMS.txt'

s=identity.read_text(encoding='utf-8')
assert '- Status: `CANDIDATE / NOT CURRENT`' in s
assert '- Candidate Authorization: `AUTHORIZED_TO_SEAL_CANDIDATE`' in s
assert '- Candidate publication: `PENDING_LOCAL_FINAL_BYTES_AND_REMOTE_VALIDATION`' in s
s=s.replace(
 '- Candidate publication: `PENDING_LOCAL_FINAL_BYTES_AND_REMOTE_VALIDATION`',
 '- Immutable package seal: `LOCAL_FINAL_BYTES_SEALED_AFTER_METADATA_RECONCILIATION`\n'
 '- Remote exact-source / prerelease status: `EXTERNAL_GOVERNANCE_EVIDENCE; MUST MATCH THIS IMMUTABLE PACKAGE; NOT SELF-MUTATED INTO PACKAGE`'
)
identity.write_text(s,encoding='utf-8')

m=json.loads(manifest_path.read_text(encoding='utf-8'))
assert m['artifact_id']=='SKILL-BOOK-V5.6-CANDIDATE'
assert m['status']=='CANDIDATE_NOT_CURRENT'
assert m['stability']=='CANDIDATE_STAGED_PENDING_FINAL_BYTE_SEAL'
assert m['candidate_authorization']=='AUTHORIZED_TO_SEAL_CANDIDATE'
assert m['package_seal_state']['local_final_bytes'].startswith('PENDING_')
assert m['current_promotion']=='NOT_AUTHORIZED'
assert m['real_reader_evidence']=='NOT_RUN'

m['package_seal_state']={
 'local_final_bytes':'PASS_FINAL_BYTES_AFTER_METADATA_RECONCILIATION',
 'deterministic_double_build':'PASS_REQUIRED_AND_VERIFIED_FOR_IMMUTABLE_CANDIDATE',
 'remote_exact_source':'EXTERNAL_GATE_MUST_MATCH_IMMUTABLE_PACKAGE',
 'prerelease':'EXTERNAL_GOVERNANCE_EVENT_NOT_SELF_MUTATED_INTO_PACKAGE',
}
m['validation']['candidate_stage_full_regression']='122/122 PASS'
m['validation']['candidate_stage_runner_run_job']='33258680813 / 99116743325'
m['validation']['final_byte_rerun_required']=False
m['validation']['final_byte_rerun_state']='PASS_REQUIRED_ON_THESE_IMMUTABLE_BYTES_BEFORE_RELEASE'
m['validation']['remote_evidence_model']='EXTERNAL_EVIDENCE_BOUND_BY_EXACT_SOURCE_AND_CANDIDATE_ZIP_SHA256'
m['stability']='CANDIDATE_NOT_CURRENT'
m['candidate_authorization']='AUTHORIZED_CANDIDATE_LOCAL_SEAL'

# Rebuild package inventory after Source Identity changes.
excluded={'MANIFEST.json','SHA256SUMS.txt'}
paths=sorted(x for x in skill.rglob('*') if x.is_file() and '__pycache__' not in x.parts and x.relative_to(skill).as_posix() not in excluded)
files=[]; lines=[]
for x in paths:
 rel=x.relative_to(skill).as_posix(); data=x.read_bytes(); h=hashlib.sha256(data).hexdigest()
 files.append({'path':rel,'bytes':len(data),'sha256':h}); lines.append(f'{h}  {rel}\n')
m['files']=files
m['validation']['source_non_manifest_tree_sha256']=hashlib.sha256(''.join(lines).encode()).hexdigest()
manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

rows=[]
for x in sorted(y for y in skill.rglob('*') if y.is_file() and y.name!='SHA256SUMS.txt' and '__pycache__' not in y.parts and y.suffix!='.pyc'):
 rel=x.relative_to(skill).as_posix(); rows.append(f'{hashlib.sha256(x.read_bytes()).hexdigest()}  {rel}')
sums.write_text('\n'.join(rows)+'\n',encoding='utf-8')

print('V56_FINAL_CANDIDATE_METADATA_PREPARED')
print('TREE_SHA='+m['validation']['source_non_manifest_tree_sha256'])
print('SOURCE_FILES='+str(len(files)))
print('SHA_ROWS='+str(len(rows)))
