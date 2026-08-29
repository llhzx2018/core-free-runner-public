from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')

old="""phase_depth = [
    {'phase': p, 'applicability': 'OPTIONAL', 'rationale': '该软件/网站专用细分阶段不适用于线下读书会；当前活动生命周期已由通用 operator responsibilities 覆盖。'}
    for p in ('PROBLEM_DISCOVERY','OPPORTUNITY_SELECTION','ALTERNATIVE_PRESSURE','PREBUILD_VALIDATION','DEVELOPMENT_ENTRY_DECISION','SCOPE','BUILD','ACCEPTANCE','PRODUCTION','DISCOVERABILITY','ACTIVATION','OBSERVABILITY_DECISION')
]
"""
new="""phase_depth = []
for p in ('PROBLEM_DISCOVERY','OPPORTUNITY_SELECTION','ALTERNATIVE_PRESSURE','PREBUILD_VALIDATION','DEVELOPMENT_ENTRY_DECISION','SCOPE','BUILD','ACCEPTANCE','PRODUCTION','DISCOVERABILITY','ACTIVATION','OBSERVABILITY_DECISION'):
    if p == 'OBSERVABILITY_DECISION':
        phase_depth.append({'phase': p, 'applicability': 'REQUIRED', 'rationale': '本书明确承诺活动后根据结果证据判断保持、调整或停止，因此观察信号到下一决策是必需阶段。'})
    else:
        phase_depth.append({'phase': p, 'applicability': 'OPTIONAL', 'rationale': '该软件/网站专用细分阶段不适用于线下读书会；当前活动生命周期已由通用 operator responsibilities 覆盖。'})
"""
assert s.count(old)==1, s.count(old)
s=s.replace(old,new)

marker="j('evidence/generation_responsibility_contract.json', gen)\n"
assert s.count(marker)==1
insert=r"""# Promise responsibilities inferred from this fresh book's own reader contract.
w('references/operator/observability_decision.md', r'''
# Observability Decision Operator Reference
Baseline: the approved event plan and baseline snapshot. Signal interpretation: compare attendance friction, discussion participation, access defects and host load against the same definitions used during the event. Change control: do not change format from one emotional comment; link evidence IDs, state the proposed change, impact and revalidation. Next decision: KEEP / REVISE / STOP with rationale, UNKNOWN handling and revisit trigger. Judgment: weak signals remain hypotheses. Execution: collect post-event evidence from at least two independent sources where possible. Validation: the next decision must cite the evidence trace. Failure recovery: if feedback is contradictory, keep UNKNOWN and collect another sample rather than forcing a conclusion. Completion: close only when baseline, interpreted signal and next action are linked.
''')
w('references/operator/rollback_recovery.md', r'''
# Rollback / Recovery Operator Reference
Rollback target: last approved event plan or safe operating state. Rollback method: stop the affected activity, restore the approved arrangement, and record the exact change reversed. Stateful caveat: a participant safety/access incident cannot be erased by restoring the schedule; preserve incident evidence and escalation state. Retest: repeat the original readiness or incident check under the same acceptance rule. Judgment: rollback is allowed only when it reduces risk and does not hide evidence. Execution: identify trigger, diagnose, recover, retest, then decide resume or stop. Validation: post-retry evidence must support the state transition. Failure recovery: repeated failure triggers escalation and stop. Completion: closure requires linked incident ID, rollback target and revalidation result.
''')
gen['promise_responsibilities'] = [
    {
        'responsibility': 'observability_decision',
        'applicability': 'REQUIRED',
        'dimensions': ['baseline','signal_interpretation','change_control','next_decision'],
        'chapter_paths': ['chapters/03_iterate_next.md'],
        'operator_reference_paths': ['references/operator/observability_decision.md'],
        'asset_paths': ['templates/07_post_event_iteration_log.md','templates/08_baseline_snapshot.md'],
        'judgment': '根据 baseline 与可追溯的活动后信号判断 KEEP / REVISE / STOP，并保留 UNKNOWN 与 revisit trigger。',
        'execution': '收集活动结果与参与者证据，链接到迭代日志和下一决策。',
        'validation': '下一决定必须能从 baseline、signal、interpretation 和 evidence IDs 重建。',
        'failure_recovery': '信号冲突时不强行下结论，补采样后再按同一规则判断。',
        'completion': '只有 baseline、信号解释、变更控制和下一动作全部可追溯时才关闭。',
    },
    {
        'responsibility': 'rollback_recovery',
        'applicability': 'REQUIRED',
        'dimensions': ['rollback_target','rollback_method','stateful_caveat','retest'],
        'chapter_paths': ['chapters/02_plan_execute_accept.md'],
        'operator_reference_paths': ['references/operator/rollback_recovery.md'],
        'asset_paths': ['templates/03_event_plan_contract.md','templates/06_incident_recovery_log.md','templates/08_baseline_snapshot.md'],
        'judgment': '判断何时恢复到最后批准的安全状态、何时事故状态不可简单回滚而必须升级。',
        'execution': '记录 rollback target、恢复动作、incident evidence 与 retest。',
        'validation': '恢复后使用原 acceptance rule 重跑检查，不用主观“看起来好了”替代。',
        'failure_recovery': '再次失败时停止重复尝试并升级，保留所有前后证据。',
        'completion': '只有 rollback target、恢复方法、stateful caveat 和 retest result 全部可复核时才关闭。',
    },
]

"""+marker
s=s.replace(marker,insert)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_PROMISE_RESPONSIBILITY_PATCH_V2_APPLIED')
