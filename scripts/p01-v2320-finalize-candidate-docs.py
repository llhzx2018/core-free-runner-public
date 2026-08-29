#!/usr/bin/env python3
from pathlib import Path
import json

VERSIONED_SOURCE='8b4f3483579bf2d286c551c1f33e876e4e7aec16'
VERSIONED_TREE='8e693bda3a16ad1e0952314858227ffbffd59897'
RUNTIME_TREE='f348cb314623906acc851cb79d75b1c8f6637aff'
RUN=33263475338
EVID_ART=9717934307
EVID_DIGEST='sha256:944b0d3d324c89cea7569296a67e451d6c261190d50e237a799a5e1e3ae421e6'
ART_ART=9717934562
ART_DIGEST='sha256:3c3815de47bf6d9199c41b9739f47f323f89d2a115bf231726db02a28d5a87c5'
FULL_SHA='b2103fcf307340e35da45500bcdb5ab9de92513755f423d92c8e4b3ab2be61aa'
UPDATE_SHA='3c1b7d4ee9cf5857d035864089b186f057f729d32760b75aa095983b9fe307ba'
REPAIR_SHA='327cf472aeb74f1fc3a9b77b11bb619ffe000522bdf2d417af92675f3151312d'

# VF_PROJECT
p=Path('VF_PROJECT.json'); data=json.loads(p.read_text(encoding='utf-8'))
assert data['candidate_version']=='2.32.0'
assert data['candidate_state']=='VERSIONED / UNIFIED READINESS GATE PENDING'
data['current_phase']='V2.32.0 CANDIDATE READY / L3 RELEASE GATE PENDING'
data['current_change']['result']='CANDIDATE READY / UNIFIED READINESS GATE PASS'
data['current_change']['gates']['candidate_readiness']=RUN
data['current_change']['versioned_candidate_source']=VERSIONED_SOURCE
data['current_change']['versioned_candidate_tree']=VERSIONED_TREE
data['current_change']['runtime_tree']=RUNTIME_TREE
data['current_change']['candidate_readiness_evidence']={
  'run':RUN,'artifact_id':EVID_ART,'artifact_digest':EVID_DIGEST,
  'unpublished_artifact_id':ART_ART,'unpublished_artifact_digest':ART_DIGEST,
  'full_sha256':FULL_SHA,'update_sha256':UPDATE_SHA,'repair_sha256':REPAIR_SHA,
  'actual_upgrade':'PASS','data_preservation':'PASS','idempotence':'PASS',
  'failure_rollback':'PASS','interruption_recovery':'PASS','fresh_runtime':'PASS',
  'desktop_mobile_home':'PASS','public_private_boundary':'PASS'
}
data['candidate_state']='READY_FOR_L3_RELEASE_GATE'
data['next_action']='Run final docs-bound exact-source fence; merge Candidate Closure to develop; formal release remains an L3-only next phase'
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Evidence doc
p=Path('docs/evidence/P01_V2.32.0_CANDIDATE_READINESS_20260830.md'); s=p.read_text(encoding='utf-8')
old='> Status: `CANDIDATE CLOSURE / UNIFIED READINESS GATE PENDING`'
assert s.count(old)==1
s=s.replace(old,'> Status: `PASS / READY_FOR_L3_RELEASE_GATE`',1)
marker='## 5. Boundary\n'
assert s.count(marker)==1
result=f'''## 5. Unified Candidate Readiness Result\n\n```text\nVersioned Candidate Source: {VERSIONED_SOURCE}\nVersioned Candidate Tree: {VERSIONED_TREE}\nRuntime src Tree: {RUNTIME_TREE}\nUnified Gate Run: {RUN} / PASS\nEvidence Artifact: {EVID_ART}\nEvidence Digest: {EVID_DIGEST}\nUnpublished Candidate Artifact: {ART_ART}\nUnpublished Artifact Digest: {ART_DIGEST}\nCandidate FULL SHA256: {FULL_SHA}\nCandidate UPDATE SHA256: {UPDATE_SHA}\nCandidate Repair SHA256: {REPAIR_SHA}\nFormal Release: NOT STARTED\nOwner Production Write: NO\n```\n\nMachine PASS includes exact source/version binding, 8-file runtime delta, no migration, deterministic unpublished FULL/UPDATE, real non-production `2.31.0 -> 2.32.0` Atomic Upgrade, data preservation, idempotence, failure rollback, hard-interruption recovery, Fresh Install, SQLite/FK, V9 Home-byte binding, Desktop/Mobile Home, health/activity/recent/favorite behavior, zero-pending behavior, authenticated Home root and anonymous Public Navigator boundary.\n\n## 6. Boundary\n'''
s=s.replace(marker,result,1)
old_tail='此文档当前只证明 Product Chain 已完成且可以进入 Unified Candidate Gate。它不等于 Formal Release Approval。Candidate Gate PASS 后再回写最终 Candidate Source / Tree / Run / Artifact / Digest，并执行 Final Metadata Fence。'
assert old_tail in s
s=s.replace(old_tail,'V2.32.0 Candidate Readiness 已 PASS，可进入 L3 Formal Release Gate；但 Formal Release 尚未开始。当前 docs-bound source 仍须通过一次只读 Final Metadata Fence，且本轮不允许 main、Tag、GitHub Release、core-updates 或 Owner Production 写入。',1)
p.write_text(s,encoding='utf-8')

# Current Authority
p=Path('docs/authority/CURRENT.md'); s=p.read_text(encoding='utf-8')
needle='Candidate Version: 2.32.0\nSchema: 2026082901 (unchanged)\nMigration: NONE\nRelease: NO\nProduction Write: NO'
assert s.count(needle)==1
replacement=f'''Candidate Version: 2.32.0\nVersioned Candidate Source: {VERSIONED_SOURCE}\nVersioned Candidate Tree: {VERSIONED_TREE}\nRuntime src Tree: {RUNTIME_TREE}\nUnified Candidate Gate: {RUN} PASS\nEvidence Artifact: {EVID_ART} / {EVID_DIGEST}\nSchema: 2026082901 (unchanged)\nMigration: NONE\nRelease: NO\nProduction Write: NO'''
s=s.replace(needle,replacement,1)
old='当前只允许完成 V2.32 Candidate Readiness / Metadata Fence。统一 Candidate Gate PASS 前，不进入 main Promotion、Tag、GitHub Release、core-updates 或 Owner Production。'
assert old in s
s=s.replace(old,'V2.32 Candidate Readiness 已 PASS，状态为 `READY_FOR_L3_RELEASE_GATE`。当前 L2 只剩 docs-bound Final Metadata Fence 与 Candidate Closure → develop；Formal Release/main/Tag/GitHub Release/core-updates/Owner Production 均属于后续 L3，当前不执行。',1)
p.write_text(s,encoding='utf-8')

# Handoff
p=Path('docs/handoff/CURRENT_STATE.md'); s=p.read_text(encoding='utf-8')
assert 'Candidate Gate: PENDING' in s
s=s.replace('Candidate Gate: PENDING',f'Candidate Gate: {RUN} PASS\nVersioned Candidate Source: {VERSIONED_SOURCE}\nVersioned Candidate Tree: {VERSIONED_TREE}\nRuntime src Tree: {RUNTIME_TREE}\nEvidence Artifact: {EVID_ART} / {EVID_DIGEST}',1)
old='执行 V2.32.0 Unified Candidate Readiness Gate，绑定最终 Versioned Candidate Source/Tree，并验证 Fresh Runtime、真实 `2.31.0 -> 2.32.0` 非生产升级、数据保留、Desktop/Mobile Home、Public/Private、SQLite/FK。\n\nGate PASS 前：不动 main、Tag、Release、core-updates、Owner Production。'
assert old in s
s=s.replace(old,'Unified Candidate Readiness 已 PASS。下一步仅执行 docs-bound Final Metadata Fence，并把 Candidate Closure 合并回 develop。之后如继续正式发布，必须切换到 L3 Formal Release Gate。\n\n当前仍不动 main、Tag、GitHub Release、core-updates、Owner Production。',1)
p.write_text(s,encoding='utf-8')
