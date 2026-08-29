#!/usr/bin/env python3
from pathlib import Path
import json

VERSIONED_SOURCE='da430cf426915a11198cfb9c6aa5335da391402f'
VERSIONED_TREE='064b40e984c26a6d13b29e020415259a8e192a6a'
RUNTIME_TREE='febc1b01a5b59963bc974cdc6455cfa824c0adc3'
RUN=33268162412
EVID_ART=9719277764
EVID_DIGEST='sha256:278c874e6ba0ee1aa134a16e31ceb754c2b3f73461a0c0cc76e01112c50d0499'
ART_ART=9719278185
ART_DIGEST='sha256:dc6196bab962088d905aaca6b76488cb2dd824e53a5495e6d3afe232000b14ee'

p=Path('VF_PROJECT.json'); data=json.loads(p.read_text(encoding='utf-8'))
assert data['candidate_version']=='2.33.0'
assert data['candidate_state']=='VERSIONED / UNIFIED READINESS GATE PENDING'
data['current_phase']='V2.33.0 CANDIDATE READY / L3 RELEASE GATE PENDING'
data['current_change']['result']='CANDIDATE READY / UNIFIED READINESS GATE PASS'
data['current_change']['gates']['candidate_readiness']=RUN
data['current_change']['versioned_candidate_source']=VERSIONED_SOURCE
data['current_change']['versioned_candidate_tree']=VERSIONED_TREE
data['current_change']['runtime_tree']=RUNTIME_TREE
data['current_change']['candidate_readiness_evidence']={
  'run':RUN,'artifact_id':EVID_ART,'artifact_digest':EVID_DIGEST,
  'unpublished_artifact_id':ART_ART,'unpublished_artifact_digest':ART_DIGEST,
  'actual_upgrade':'PASS','data_preservation':'PASS','idempotence':'PASS',
  'repair_self_test':'PASS','fresh_runtime':'PASS','schema_unchanged':'PASS',
  'health_triage_v4_binding':'PASS'
}
data['candidate_state']='READY_FOR_L3_RELEASE_GATE'
data['next_action']='Run final docs-bound exact-source fence; merge Candidate Closure to develop; then L3 formal release gate'
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

p=Path('docs/evidence/P01_V2.33.0_CANDIDATE_READINESS_20260830.md'); s=p.read_text(encoding='utf-8')
old='> Status: `CANDIDATE CLOSURE / UNIFIED READINESS GATE PENDING`'
assert s.count(old)==1
s=s.replace(old,'> Status: `PASS / READY_FOR_L3_RELEASE_GATE`',1)
marker='## 5. Boundary\n'
assert s.count(marker)==1
result=f'''## 5. Unified Candidate Readiness Result\n\n```text\nVersioned Candidate Source: {VERSIONED_SOURCE}\nVersioned Candidate Tree: {VERSIONED_TREE}\nRuntime src Tree: {RUNTIME_TREE}\nUnified Gate Run: {RUN} / PASS\nEvidence Artifact: {EVID_ART}\nEvidence Digest: {EVID_DIGEST}\nUnpublished Candidate Artifact: {ART_ART}\nUnpublished Artifact Digest: {ART_DIGEST}\nFormal Release: NOT STARTED\nOwner Production Write: NO\n```\n\nMachine PASS includes exact source/version binding, 6-file runtime delta, no migration, deterministic unpublished FULL/UPDATE, real non-production `2.32.0 -> 2.33.0` Atomic Upgrade, data preservation, idempotence, repair self-test, Fresh Runtime, SQLite/FK, and exact V4 Health Triage byte binding.\n\n## 6. Boundary\n'''
s=s.replace(marker,result,1)
old_tail='此文档当前只证明 Product Chain 已完成且可以进入 Unified Candidate Gate。它不等于 Formal Release Approval。Candidate Gate PASS 后再回写最终 Candidate Source / Tree / Run / Artifact / Digest，并执行 Final Metadata Fence。'
assert old_tail in s
s=s.replace(old_tail,'V2.33.0 Candidate Readiness 已 PASS，可进入 L3 Formal Release Gate；但 Formal Release 尚未开始。当前 docs-bound source 仍须通过一次只读 Final Metadata Fence，且此时不允许 main、Tag、GitHub Release、core-updates 或 Owner Production 写入。',1)
p.write_text(s,encoding='utf-8')

p=Path('docs/authority/CURRENT.md'); s=p.read_text(encoding='utf-8')
needle='Candidate Version: 2.33.0\nSchema: 2026082901 (unchanged)\nMigration: NONE\nRelease: NO\nProduction Write: NO'
assert s.count(needle)==1
replacement=f'''Candidate Version: 2.33.0\nVersioned Candidate Source: {VERSIONED_SOURCE}\nVersioned Candidate Tree: {VERSIONED_TREE}\nRuntime src Tree: {RUNTIME_TREE}\nUnified Candidate Gate: {RUN} PASS\nEvidence Artifact: {EVID_ART} / {EVID_DIGEST}\nSchema: 2026082901 (unchanged)\nMigration: NONE\nRelease: NO\nProduction Write: NO'''
s=s.replace(needle,replacement,1)
old='当前只允许完成 V2.33 Candidate Readiness / Metadata Fence。统一 Candidate Gate PASS 前，不进入 main Promotion、Tag、GitHub Release、core-updates 或 Owner Production。'
assert old in s
s=s.replace(old,'V2.33 Candidate Readiness 已 PASS，状态为 `READY_FOR_L3_RELEASE_GATE`。当前只剩 docs-bound Final Metadata Fence 与 Candidate Closure → develop；随后才能进入 L3 Formal Release。Owner Production 仍由 Owner 手工执行。',1)
p.write_text(s,encoding='utf-8')

p=Path('docs/handoff/CURRENT_STATE.md'); s=p.read_text(encoding='utf-8')
assert 'Candidate Gate: PENDING' in s
s=s.replace('Candidate Gate: PENDING',f'Candidate Gate: {RUN} PASS\nVersioned Candidate Source: {VERSIONED_SOURCE}\nVersioned Candidate Tree: {VERSIONED_TREE}\nRuntime src Tree: {RUNTIME_TREE}\nEvidence Artifact: {EVID_ART} / {EVID_DIGEST}',1)
old='执行 V2.33.0 Unified Candidate Readiness Gate，绑定最终 Versioned Candidate Source/Tree，并验证 Fresh Runtime、真实 `2.32.0 -> 2.33.0` 非生产升级、数据保留、网址健康治理语义、Desktop/Mobile、Public/Private、SQLite/FK。\n\nGate PASS 前：不动 main、Tag、Release、core-updates、Owner Production。'
assert old in s
s=s.replace(old,'Unified Candidate Readiness 已 PASS。下一步只执行 docs-bound Final Metadata Fence，并把 Candidate Closure 合并回 develop；随后进入 L3 Formal Release。Owner Production 不由助手写入。',1)
p.write_text(s,encoding='utf-8')
