from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
(OUT / 'chapters').mkdir()
(OUT / 'templates').mkdir()
(OUT / 'evidence').mkdir()


def w(rel: str, text: str) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + '\n', encoding='utf-8')


def j(rel: str, obj) -> None:
    w(rel, json.dumps(obj, ensure_ascii=False, indent=2))


def run(script: str, args: list[str], out_rel: str):
    out = OUT / out_rel
    cp = subprocess.run(
        [sys.executable, str(SKILL / 'scripts' / script), *args, '--json', str(out)],
        capture_output=True,
        text=True,
    )
    data = json.loads(out.read_text(encoding='utf-8')) if out.exists() else None
    return cp, data


def require_pass(label: str, script: str, args: list[str], out_rel: str):
    cp, data = run(script, args, out_rel)
    assert cp.returncode == 0, f'{label} RC={cp.returncode}\n{cp.stdout}\n{cp.stderr}'
    assert data and data.get('decision') in {'PASS', 'PASS_RUNTIME_ACCEPTANCE', 'PASS_FREEZE_INTEGRITY', 'PASS_NOT_APPLICABLE_NEW_BOOK'}, (label, data)
    print(f'{label}=PASS decision={data.get("decision")}')
    return data


# Fresh reader-facing content: written for this run, not copied from A1 or the unit-test fixtures.
chapter1 = r'''
# 第 1 章：先听人，再定活动

二十人的读书会最容易犯的错，是先订场地，再问大家真正需要什么。本章的目标不是“收集偏好”，而是建立一条能追溯的 participant evidence chain：谁说了什么、在什么时间和场景说、哪些只是偏好、哪些会直接阻止参加，以及这些证据支持了哪个决定。

## 从原话到可判断证据
输入不是“大家都喜欢安静”，而是带来源的观察。每条 evidence item 都要保留 participant source、date、raw statement、interpretation、confidence 与 counter-evidence。若两位参与者意见冲突，先标 UNKNOWN，不要用平均值把冲突抹掉。输出是可以支持 venue / format decision 的证据，而不是漂亮总结。

## 如何做场地与形式决定
至少比较两个 options。Rule / criteria 先写清：到场可达性、噪声、预算、讨论私密性和取消风险。Decision 必须说明 selected option、supporting evidence、rationale / tradeoff，以及 revisit trigger：例如确认人数低于 12、场地临时改变最低消费或三位行动不便参与者无法进入时，重新评估。

## 练习与纠错
练习：把“大家觉得咖啡馆挺好”改写成三条可验证 evidence。Reference judgment：如果缺来源、时间或反证，只能算弱证据。Common mistake：把组织者自己的偏好写成参与者事实。Adaptation：若换成亲子读书会，criteria 应增加儿童活动空间和监护边界，而不是复用当前阈值。
'''

chapter2 = r'''
# 第 2 章：把计划变成现场可执行系统

一个能执行的活动计划必须让另一位志愿者在你迟到二十分钟时仍能接手。输入包括已确认人数、场地 baseline version、书目、时间窗与负责人；输出是 run-of-show、readiness acceptance 和 incident recovery 路径。

## 计划、变更与交接
Baseline plan 先冻结：18:30 入场、19:00 开场、20:30 结束。Proposed change 必须写 change reason / evidence、owner / authority、impact、revalidation 与 accept / reject / defer。没有这些字段的“最新版计划”无法解释为什么改，也无法 rollback 到安全版本。

## 现场执行与证据日志
Steps: 1. 检查座位与签到。2. 验证音量和照明。3. 确认主持人与分组。4. 开场并记录关键事件。每个 checkpoint 都要留下 Record ID、Source / actor、Date / Time、Action / observation、Result、Interpretation 和 Linked decision/change。异常时不能只写“重试”：要写 failure trigger、diagnosis、recovery action、retry condition、post-retry evidence 和 stop/escalate 条件。

## 就绪验收
Expected 与 Actual 分开记录。Verification method 说明怎样检查；PASS / FAIL / PARTIAL 不能凭感觉。若有 defect / gap，要说明 rework；closure 只有在关键缺陷清零或明确接受剩余风险后才成立。
'''

chapter3 = r'''
# 第 3 章：活动结束后，决定下一次怎么变

复盘不是“大家很开心”。它要回答：这次改变了什么、结果是什么、证据强不强、下一次继续还是改。没有 trace 的复盘会让下一次组织重新从印象开始。

## 迭代日志
每个 iteration 都有 Record ID、Date / version、Result、Interpretation 与 Linked decision。Decision rule 先写 criteria，再给 outcome 和 rationale。若证据不足，状态是 UNKNOWN；若下一次报名结构或场地约束变化，触发 revisit。

## 下一决策
Options: 保持当前形式 / 改成小组轮换 / 缩短总时长。Criteria 包括有效讨论人数、迟到率、参与者反馈和主持负担。Selected option 必须说明 supporting evidence、tradeoff、uncertainty、revisit trigger 与 next action。

## 训练反馈
练习：给出“有人说节奏太快”这一条反馈，判断是否足以改变流程。Reference judgment：单条匿名评论不能直接推翻 baseline，但应进入 evidence log 并等待更多同类证据。Common error：把高情绪强度当作高证据强度。Correction：补来源与频率；Retry：下一次使用同一问题收集结构化反馈；Completion：能解释为什么继续、修改或停止某项做法。
'''

w('chapters/01_evidence_and_decision.md', chapter1)
w('chapters/02_plan_execute_accept.md', chapter2)
w('chapters/03_iterate_next.md', chapter3)

COMMON_EXAMPLE = r'''
## Worked Example / Reference Guidance
Example: 参与者 P07 在报名表中写“19:00 前很难到达”，Source: registration form, Date: 2026-08-29, confidence: high for that participant. Reference judgment: 这条证据足以影响开场签到安排，但不足以单独改变全场开始时间，因为还缺其他参与者的 supporting evidence. Why: decision scope 要与 evidence scope 匹配。Common mistake: 把一个人的事实外推成所有人的事实。Adaptation: 若出现 6 名以上同类反馈，再按预设 threshold 重新评估开始时间。
'''

assets: dict[str, str] = {
'01_participant_evidence_capture.md': r'''
# Participant Evidence Capture
## Task / Trigger
Actor: organizer. Trigger: registration or interview arrives. Goal: capture participant evidence before venue and format decisions. Scope: participation constraints and discussion needs; out of scope: diagnosing personalities. Handoff / next action: venue decision record.
## Evidence Item
Evidence ID: ____
Source / participant: ____
Date: ____  Session context: ____
Raw statement / observation: ____
Interpretation: ____
Confidence / quality: ____
Counter-evidence / contradiction / UNKNOWN: ____
Linked decision / action informed: ____
## Evidence Trace
Record ID: ____ | Source / actor: ____ | Date: ____ | Action / observation: ____ | Result: ____ | Interpretation: ____ | Linked decision/change: ____
## Completion
Completion: close only when required evidence is attached, UNKNOWN items are visible, and handoff to the decision record is explicit.
''' + COMMON_EXAMPLE,
'02_venue_format_decision_record.md': r'''
# Venue / Format Decision Record
## Options and Rule
Options: A = library room; B = quiet cafe; C = community room.
Criteria / threshold / decision rule: access >= 18/20 confirmed participants; noise test PASS; total fixed cost <= budget; cancellation risk acceptable.
Evidence source / supporting evidence: participant ledger IDs ____; venue visit record ____.
Selected option / decision: ____
Rationale / tradeoff / why: ____
Uncertainty / exception / UNKNOWN: ____
Revisit trigger / reconsider if: confirmed attendance < 12, access condition changes, or venue terms change.
## Input Evidence
Evidence item / observation: ____ | Source: ____ | Date: ____ | Confidence: ____ | Counter-evidence: ____ | Linked action: ____
## Completion
Completion: close only when the rule has evidence, uncertainty is explicit, and next action is handed to the event plan.
''' + COMMON_EXAMPLE,
'03_event_plan_contract.md': r'''
# Event Plan / Contract
## Context and Objective
Owner: organizer. Trigger: venue decision approved. Objective: make the event executable by a backup volunteer. Scope: 18:30–20:30 event operations; non-goal: long-term community strategy. Output / handoff: run-of-show and readiness check.
## Change Control
Baseline version: RC-PLAN-01
Proposed change: ____
Change reason / evidence: ____
Owner / authority / approver: ____
Impact / affected assumptions / scope: ____
Revalidation / re-validate method: ____
Accept / Reject / Defer: ____
Superseded version / rollback target / freeze state: ____
## Acceptance
Expected: named owners, room access, materials, timing and emergency contact all confirmed.
Actual: ____
Verification method: independent checklist review 24h before event.
Verification evidence: ____
PASS / FAIL / PARTIAL: ____
Defect / gap / rework: ____
Closure / acceptance decision: ____
## Completion
Completion: close only when required evidence is attached, unresolved blockers are explicit, and handoff to execution is authorized.
''',
'04_run_of_show_execution_log.md': r'''
# Run-of-Show Execution Log
## Task and Inputs
Actor / owner: floor lead. Trigger: doors open. Goal: execute the event safely and on time. Inputs: approved plan, participant list, venue access, materials. Preconditions / dependency: room access and host confirmed. Output / handoff: acceptance and incident records.
## Ordered Steps
1. Check entrance, seats and signs. Checkpoint: access test.
2. Verify lighting and noise. Checkpoint: host can hear rear seat.
3. Confirm host and small-group leads. Exception path: if blocked, assign backup lead.
4. Start session. Handoff / next action: readiness/acceptance record.
## Evidence Log
Record ID: ____ | Source / actor: ____ | Date: ____ | Action / observation: ____ | Result: ____ | Interpretation: ____ | Linked decision/change: ____
## Failure Recovery
Failure trigger / anomaly: ____
Diagnosis / likely cause / root cause: ____
Recovery action / correction / rollback: ____
Retry condition / retry only when: ____
Post-retry evidence / retry result: ____
Escalate / pause when / stop when: ____
## Validation
Expected: event begins within 10 minutes of plan and all safety/access checks pass. Actual: ____. Verification method: timestamp + checklist. Verification evidence: ____. PASS / FAIL / PARTIAL: ____. Defect / rework: ____. Closure: ____.
## Completion
Completion: close only when trace is complete, blockers are handed off, and next stage is authorized.
''',
'05_readiness_acceptance_record.md': r'''
# Readiness Acceptance Record
## Acceptance Check
Expected: venue open, 20 seats available, host present, materials ready, access route unobstructed.
Actual: ____
Verification method / verify by: second volunteer physically checks each item.
Verification evidence / evidence log: photo or checklist ID ____.
PASS / FAIL / PARTIAL: ____
Defect / gap: ____
Rework: ____
Closure / acceptance decision: READY / NOT_READY.
## Completion
Completion: close only when required evidence is attached, unresolved blockers are explicit, and READY permission is recorded.
''' + COMMON_EXAMPLE,
'06_incident_recovery_log.md': r'''
# Incident Recovery Log
## Task / Trigger
Owner: floor lead. Trigger: an incident or operational anomaly interrupts the session. Goal: recover without hiding risk. Scope: event operations; handoff: acceptance or stop decision.
## Evidence Trace
Record ID: ____ | Source / actor: ____ | Date: ____ | Action / observation: ____ | Result: ____ | Interpretation: ____ | Linked decision/change: ____
## Recovery Loop
Failure trigger / anomaly: ____
Diagnosis / likely cause / root cause: ____
Recovery action / correction / rollback: ____
Retry condition / retry only when: ____
Post-retry evidence / retry result: ____
Escalate / pause when / stop after: ____
## Ordered Steps
1. Make the area safe. 2. Capture evidence. 3. Diagnose one likely cause. 4. Apply recovery. Checkpoint: condition cleared. Exception path: if not cleared, stop and escalate. Handoff / next action: acceptance record.
## Validation
Expected: incident condition cleared without creating new risk. Actual: ____. Verification method: repeat original check. Verification evidence: ____. PASS / FAIL / PARTIAL: ____. Defect / rework: ____. Closure: ____.
## Completion
Completion: close only when the retry evidence supports the state transition or an explicit stop/escalation is recorded.
''',
'07_post_event_iteration_log.md': r'''
# Post-event Iteration Log / Next Decision
## Evidence Trace
Record ID: ITER-____ | Source / actor: participant survey + organizer log | Date: ____ | Version: ____ | Action / observation: ____ | Result: ____ | Interpretation: ____ | Linked decision/change: ____
## Decision Rule
Options: keep format / rotate small groups / shorten session.
Criteria / threshold / rule: change only when at least two independent evidence sources show the same material friction or a safety/access defect requires immediate change.
Evidence source / supporting evidence: record IDs ____.
Selected option / decision / outcome: ____
Rationale / tradeoff / why: ____
Uncertainty / exception / UNKNOWN: ____
Revisit trigger / reconsider if: next cohort composition changes materially or the same friction repeats.
Next action: ____
## Completion
Completion: close only when evidence is linked to the next decision, blockers/UNKNOWN are visible, and the next-stage action has an owner.
''' + COMMON_EXAMPLE,
'08_baseline_snapshot.md': r'''
# Event Baseline Snapshot
## Baseline Evidence
Source: approved venue agreement + confirmed participant list. Date: ____ Time: ____ Version: BASE-____. Evidence item / observation: ____ . Confidence / quality: ____ . Linked decision: event plan baseline.
## Baseline State
Baseline version / current version: BASE-____. Frozen scope: venue, start/end time, seating capacity, host, budget ceiling. Superseded version / rollback target: ____ . Freeze state: ACTIVE / SUPERSEDED.
## Completion
Completion: close only when source provenance and capture time are recorded, unresolved UNKNOWN is visible, and comparison/rollback target is explicit.
''',
}
for name, text in assets.items():
    w('templates/' + name, text)

asset_paths = [f'templates/{name}' for name in assets]
roles = [
    'evidence_capture', 'decision_record', 'plan_or_contract', 'execution_brief_or_log',
    'acceptance_record', 'execution_brief_or_log', 'iteration_log', 'baseline_snapshot'
]

rtc = {
    'BOOK_TYPE': 'PRACTICAL_PROJECT',
    'BOOK_TITLE': '20 人线下读书会：从参与者证据到复盘迭代',
    'TARGET_READER': '第一次独立组织 15–25 人线下读书会的个人组织者',
    'CURRENT_STATE': '有活动想法，但决策依赖印象、现场流程不可交接、复盘缺证据',
    'DESIRED_STATE': '能用证据做场地与形式决策，执行活动，验收就绪，处理事故并形成下一次迭代决定',
    'MUST_UNDERSTAND': ['证据与偏好的区别', '决策规则与复盘日志为什么需要可追溯'],
    'MUST_BE_ABLE_TO_JUDGE': [
        {'id': 'judge_venue', 'statement': '根据参与者证据、约束与反证选择场地和形式'},
        {'id': 'judge_next', 'statement': '根据活动结果决定保持、调整或停止某项做法'},
    ],
    'MUST_BE_ABLE_TO_DO': [
        {'id': 'do_event', 'statement': '独立完成计划、现场执行、就绪验收、事故恢复和复盘迭代'},
    ],
    'MUST_AVOID': ['把个别偏好当群体事实', '只写日期和感想的伪复盘', '失败后无诊断地重复尝试'],
    'COMPLETION_EVIDENCE': ['完整 participant evidence trace', 'venue decision record', 'readiness acceptance', 'incident recovery trace', 'post-event next decision'],
}
j('evidence/reader_transformation_contract.json', rtc)

phases = [
    {'phase': p, 'applicability': 'REQUIRED', 'rationale': '线下活动从证据收集到复盘需要该阶段形成可交接的判断或操作证据。'}
    for p in ('DISCOVER','DECIDE','PLAN','EXECUTE','VERIFY','RELEASE_OR_USE','OBSERVE','ITERATE')
]
class_rows = [
    {'class': 'evidence_capture', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[0]]},
    {'class': 'decision_record', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[1]]},
    {'class': 'plan_or_contract', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[2]]},
    {'class': 'execution_brief_or_log', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[3], asset_paths[5]]},
    {'class': 'acceptance_record', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[4]]},
    {'class': 'baseline_snapshot', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[7]]},
    {'class': 'iteration_log', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[6]]},
    {'class': 'next_decision', 'applicability': 'REQUIRED', 'asset_paths': [asset_paths[6]]},
]
phase_depth = [
    {'phase': p, 'applicability': 'OPTIONAL', 'rationale': '该软件/网站专用细分阶段不适用于线下读书会；当前活动生命周期已由通用 operator responsibilities 覆盖。'}
    for p in ('PROBLEM_DISCOVERY','OPPORTUNITY_SELECTION','ALTERNATIVE_PRESSURE','PREBUILD_VALIDATION','DEVELOPMENT_ENTRY_DECISION','SCOPE','BUILD','ACCEPTANCE','PRODUCTION','DISCOVERABILITY','ACTIVATION','OBSERVABILITY_DECISION')
]
gen = {
    'book_type': 'PRACTICAL_PROJECT',
    'lifecycle': phases,
    'phase_depth': phase_depth,
    'capability_mappings': [
        {'capability_id': 'judge_venue', 'statement': rtc['MUST_BE_ABLE_TO_JUDGE'][0]['statement'], 'chapter_paths': ['chapters/01_evidence_and_decision.md'], 'asset_paths': [asset_paths[0], asset_paths[1]]},
        {'capability_id': 'judge_next', 'statement': rtc['MUST_BE_ABLE_TO_JUDGE'][1]['statement'], 'chapter_paths': ['chapters/03_iterate_next.md'], 'asset_paths': [asset_paths[6]]},
        {'capability_id': 'do_event', 'statement': rtc['MUST_BE_ABLE_TO_DO'][0]['statement'], 'chapter_paths': ['chapters/02_plan_execute_accept.md','chapters/03_iterate_next.md'], 'asset_paths': [asset_paths[2],asset_paths[3],asset_paths[4],asset_paths[5],asset_paths[6],asset_paths[7]]},
    ],
    'operator_responsibility_classes': class_rows,
}
j('evidence/generation_responsibility_contract.json', gen)

chapter_contract = []
chapter_defs = [
    ('chapters/01_evidence_and_decision.md', [asset_paths[0],asset_paths[1]]),
    ('chapters/02_plan_execute_accept.md', [asset_paths[2],asset_paths[3],asset_paths[4],asset_paths[5],asset_paths[7]]),
    ('chapters/03_iterate_next.md', [asset_paths[6]]),
]
for path, linked in chapter_defs:
    chapter_contract.append({
        'path': path, 'complexity': 'HIGH',
        'must_explain': ['mechanism','why','boundary','evidence'],
        'must_judge': ['continue','revise','stop'],
        'boundaries': ['unknown','out_of_scope'],
        'failure_modes': ['false_evidence','unowned_recovery'],
        'worked_examples': ['reading_club_case'],
        'practice_outputs': ['completed_operator_record'],
        'template_assets': linked,
    })

adequacy_assets = []
depth_assets = []
role_dims = {
    'evidence_capture': ['context_task','input_evidence','evidence_log','completion','example_guidance'],
    'decision_record': ['input_evidence','decision_rule','completion','example_guidance'],
    'plan_or_contract': ['context_task','change_control','validation_acceptance','completion'],
    'execution_brief_or_log': ['context_task','input_evidence','execution_steps','evidence_log','failure_recovery','validation_acceptance','completion'],
    'acceptance_record': ['validation_acceptance','completion','example_guidance'],
    'iteration_log': ['evidence_log','decision_rule','completion','example_guidance'],
    'baseline_snapshot': ['input_evidence','change_control','completion'],
}
for i, path in enumerate(asset_paths):
    role = roles[i]
    dims = role_dims[role]
    adequacy_assets.append({'path': path, 'complexity': 'HIGH', 'required_dimensions': dims, 'training_instrument': role in {'decision_record','acceptance_record','iteration_log'}})
    ds = [role]
    if path.endswith('07_post_event_iteration_log.md'):
        ds = ['iteration_log','next_decision']
    depth_assets.append({'path': path, 'roles': ds, 'complexity': 'HIGH', 'required_dimensions': dims, 'depth_requirements': {}, 'n_a': {}, 'promise_links': ['judge_venue' if i < 2 else 'do_event'], 'lifecycle_links': ['ITERATE' if i == 6 else 'EXECUTE']})

j('evidence/adequacy_contract.json', {'chapters': chapter_contract, 'assets': adequacy_assets})
j('evidence/practical_asset_depth_contract.json', {'schema': 'skill-book.practical-asset-depth.v1', 'assets': depth_assets})

core_ops = {'execution_implementation','measurement_attribution','experiment_change_control','diagnosis_incident_recovery','quality_acceptance','operating_cadence','end_to_end_repeatable_workflow'}
ops_names = ['economics_viability','acquisition_funnel','execution_implementation','measurement_attribution','experiment_change_control','diagnosis_incident_recovery','quality_acceptance','scale_resource_constraints','operating_cadence','end_to_end_repeatable_workflow']
ops = {
    'book_type': 'PRACTICAL_PROJECT',
    'responsibilities': [
        {
            'responsibility': n,
            'applicability': 'REQUIRED' if n in core_ops else 'OPTIONAL',
            'rationale': '对线下活动，执行、测量、变更、事故恢复、验收与复盘是闭环核心；商业获客等并非本书承诺。',
            'chapter_paths': ['chapters/02_plan_execute_accept.md','chapters/03_iterate_next.md'],
            'asset_paths': [asset_paths[2],asset_paths[3],asset_paths[4],asset_paths[5],asset_paths[6]],
            'judgment': '根据证据判断继续、调整、暂停或停止，并保留 UNKNOWN。',
            'execution': '执行一个有负责人、检查点、日志和交接的活动操作循环。',
            'validation': '使用 expected/actual、verification method 和 PASS/FAIL/PARTIAL 复核结果。',
        }
        for n in ops_names
    ],
}
j('evidence/operational_closure_contract.json', ops)

feedback_loop = {
    'expected_output': '完成一份可复核的 operator record，而不是只写感想。',
    'reference_judgment': '参考判断必须说明证据强度、边界和下一动作。',
    'error_class': '常见错误是缺 provenance、无阈值、无 diagnosis 或无 linkage。',
    'correction': '补齐缺失的证据或责任链，只修改造成失败的环节。',
    'retry': '按相同验证条件重新执行并保留新的 evidence。',
    'completion_condition': '能够解释为什么 PASS/BLOCK，并把记录交给下一阶段。',
}
training = {'chapters': [
    {'chapter_path': p, 'applicability': 'REQUIRED', 'feedback_asset_paths': linked[:1], 'feedback_loop': feedback_loop}
    for p, linked in chapter_defs
]}
j('evidence/training_feedback_contract.json', training)

# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.
require_pass('GEN_RESP_PRE_DRAFT', 'generation_responsibility_audit.py', ['--new', str(OUT), '--stage', 'PRE_DRAFT'], 'evidence/generation_responsibility_pre_draft.json')
require_pass('GEN_RESP_PRE_FREEZE', 'generation_responsibility_audit.py', ['--new', str(OUT), '--stage', 'PRE_FREEZE'], 'evidence/generation_responsibility_pre_freeze.json')
require_pass('OPERATIONAL_PRE_DRAFT', 'operational_closure_audit.py', ['--new', str(OUT), '--stage', 'PRE_DRAFT'], 'evidence/operational_closure_pre_draft.json')
require_pass('OPERATIONAL_PRE_FREEZE', 'operational_closure_audit.py', ['--new', str(OUT), '--stage', 'PRE_FREEZE'], 'evidence/operational_closure_pre_freeze.json')
require_pass('TRAINING_PRE_FREEZE', 'training_feedback_audit.py', ['--new', str(OUT), '--stage', 'PRE_FREEZE'], 'evidence/training_feedback_pre_freeze.json')
require_pass('ADEQUACY_GOOD', 'adequacy_audit.py', ['--new', str(OUT)], 'evidence/adequacy_audit.json')
require_pass('DEPTH_GOOD', 'practical_asset_depth_audit.py', ['--new', str(OUT)], 'evidence/practical_asset_depth_audit.json')
require_pass('RANDOM_OPEN_GOOD', 'prefreeze_random_open_audit.py', ['--new', str(OUT), '--phase', 'GENERATION'], 'evidence/prefreeze_random_open.json')
require_pass('SHADOW_LOCAL_VALUE_GOOD', 'shadow_local_value_audit.py', ['--new', str(OUT)], 'evidence/shadow_local_value.json')

# Adversarial mutation: preserve enough breadth words for the old Adequacy layer, destroy iteration trace depth.
iter_path = OUT / asset_paths[6]
good_iteration = iter_path.read_text(encoding='utf-8')
thin_iteration = r'''
# Post-event Iteration Log / Next Decision
## Log
Date: ____ | Note / record log: ____ | Evidence: ____
## Decision
Rule / criteria: if feedback looks materially worse, revise. Decision: CONTINUE / REVISE. Rationale / why: ____ . Revisit trigger: next cohort changes.
## Completion
Completion: close when note is written and next action is named. Blocker / UNKNOWN: ____ . Next action / handoff: ____.
'''
iter_path.write_text(thin_iteration.strip() + '\n', encoding='utf-8')
cp_a, thin_adequacy = run('adequacy_audit.py', ['--new', str(OUT)], 'evidence/adequacy_thin_iteration.json')
assert cp_a.returncode == 0 and thin_adequacy.get('decision') == 'PASS', thin_adequacy
print('THIN_ITERATION_OLD_ADEQUACY_FALSE_GREEN=PASS')
cp_d, thin_depth = run('practical_asset_depth_audit.py', ['--new', str(OUT)], 'evidence/practical_asset_depth_thin_iteration.json')
assert cp_d.returncode != 0 and thin_depth.get('decision') == 'BLOCK', thin_depth
blocks = set(thin_depth.get('blocks') or [])
assert 'PRACTICAL_ASSET_EVIDENCE_LOG_SHALLOW' in blocks or 'PRACTICAL_ASSET_TRACE_CHAIN_BROKEN' in blocks, thin_depth
print('THIN_ITERATION_DEPTH_BLOCK=PASS blocks=' + ','.join(sorted(blocks)))

# Repair without changing verifier or contract; the exact original generated asset must pass again.
iter_path.write_text(good_iteration, encoding='utf-8')
require_pass('DEPTH_REPAIRED', 'practical_asset_depth_audit.py', ['--new', str(OUT)], 'evidence/practical_asset_depth_repaired.json')

summary = {
    'test_id': 'V5.6_FRESH_NON_A1_READING_CLUB_20260829',
    'domain': '20-person offline reading club',
    'canonical_used': False,
    'real_reader_evidence': 'NOT_RUN',
    'fresh_reader_facing_chapters': 3,
    'fresh_practical_assets': len(asset_paths),
    'good_generation_gates': {
        'generation_responsibility_pre_draft': 'PASS',
        'generation_responsibility_pre_freeze': 'PASS',
        'operational_closure_pre_draft': 'PASS',
        'operational_closure_pre_freeze': 'PASS',
        'training_feedback_pre_freeze': 'PASS',
        'adequacy': 'PASS',
        'practical_asset_depth': 'PASS',
        'prefreeze_random_open': 'PASS',
        'shadow_local_value': 'PASS',
    },
    'adversarial_mutation': {
        'asset': asset_paths[6],
        'old_adequacy_result': 'PASS_FALSE_GREEN_REPRODUCED',
        'depth_result': 'BLOCK_AS_REQUIRED',
        'depth_blocks': sorted(blocks),
        'repair_result': 'PASS',
        'verifier_changed_during_repair': False,
        'contract_changed_during_repair': False,
    },
    'decision': 'PASS_FRESH_NON_A1_GENERATION_DEPTH_GATE',
}
j('evidence/FRESH_NON_A1_SUMMARY.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print('FRESH_NON_A1_GENERATION_GATE_PASS')
