from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')
marker="# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.\n"
assert s.count(marker)==1
insert=r"""# Fresh-generation PRE_FREEZE strengthening: make the actual reader-facing bytes self-sufficient,
# rather than satisfying only the PRE_DRAFT responsibility declaration.
def append_runtime(rel: str, body: str) -> None:
    fp=OUT/rel
    fp.write_text(fp.read_text(encoding='utf-8').rstrip()+"\n\n"+body.strip()+"\n",encoding='utf-8')

append_runtime('templates/01_participant_evidence_capture.md', r'''
## Operator Judgment / Validation
Decision rule: evidence may inform a group decision only when its source and scope are known; an isolated preference remains bounded to that participant. Validation: compare raw statement with interpretation before handoff. Failure: if provenance or confidence is missing, recovery is to return to the source, correct the record, and retry the evidence check. Completion state: output is ready only when the evidence ID links to a named decision or next action.
''')
append_runtime('templates/02_venue_format_decision_record.md', r'''
## Execute / Validate / Recover
Execution step: apply the stated criteria to every option using the same evidence set. Validation: a second organizer should be able to reproduce the selected decision from the rule, inputs and rationale. Failure / recovery: if two options tie or a critical UNKNOWN remains, do not force acceptance; gather the missing evidence and retry. Completion state: record the output decision, boundary, revisit condition and next action.
''')
append_runtime('templates/03_event_plan_contract.md', r'''
## Failure Recovery / Retry
Failure: if a proposed change invalidates access, owner coverage or timing, stop execution of that change. Recovery: restore the baseline plan or rollback target, record the reason, and re-run the same readiness validation. Retry only when the failed precondition is corrected. Completion: the plan output is executable only when change state, validation result and next handoff are explicit.
''')
append_runtime('templates/05_readiness_acceptance_record.md', r'''
## Decision Rule and Failure Path
Decision rule: READY only when every critical expected state has verified actual evidence; one unresolved critical defect makes the output NOT_READY. Execution step: inspect, record evidence, then decide. Failure: diagnose the first failed check, assign recovery/rework, and retry the same validation. Boundary: UNKNOWN is not PASS. Completion state: acceptance closes only with a reproducible decision and next action.
''')
append_runtime('templates/07_post_event_iteration_log.md', r'''
## Execute the Next-decision Loop
Input: baseline snapshot plus linked event evidence. Execution steps: 1. group signals by evidence ID; 2. distinguish raw result from interpretation; 3. apply the rule to KEEP / REVISE / STOP; 4. record the output decision and next action. Validation: another organizer should reach the same decision from the same evidence. Failure / recovery: if signal quality is weak or contradictory, keep UNKNOWN, collect additional evidence and retry; stop changing the format when repeated tests do not resolve the uncertainty. Completion state: the iteration closes only after decision, validation, boundary and handoff are traceable.
''')
append_runtime('templates/08_baseline_snapshot.md', r'''
## Use / Validate / Recover the Baseline
Input: approved plan, venue agreement and confirmed participant state. Decision rule: compare later evidence only against the active baseline version. Execution step: capture the baseline before the event and freeze its scope. Validation: verify source, timestamp, owner and current state before using it in a decision. Failure / recovery: if the snapshot is incomplete or superseded, do not compare; restore the last valid baseline or create a corrected version, then retry validation. Boundary: an UNKNOWN baseline cannot authorize a change. Completion output: a reproducible baseline linked to the next decision and rollback path.
''')

append_runtime('chapters/02_plan_execute_accept.md', r'''
## 为什么“计划写得很全”仍然可能不能执行
真正的 plan 不只是时间表，而是一组可交接的状态转换。组织者需要先判断哪些输入是固定 baseline，哪些可以现场调整。比如主持人临时请假不是“把名字改掉”这么简单：它会改变主持负担、分组方式、开场节奏和可能的结束时间，因此 proposed change 必须带 impact，再做 revalidation。只有这样，第二位志愿者接手时才知道哪些状态仍然有效。

执行阶段同样不能把“发生过”当成“完成”。每个 action 都要留下 output 与 validation。签到完成的验证不是“看起来人差不多齐了”，而是名单、到场人数和特殊需求的 actual state；音量测试也要用后排能否听清这一明确 expected state。若实际结果不满足规则，先进入 failure diagnosis，再选择 recovery，不允许直接把 FAIL 改成 PASS。

事故恢复尤其需要边界。若只是投影设备不可用，rollback 可以是恢复到无投影讨论方案；若是消防通道受阻或参与者身体不适，状态具有 stateful caveat，不能靠恢复时间表抹掉事故。此时 execution output 是“停止/升级并保存 evidence”，而不是“活动继续了所以问题解决”。Retry condition 必须与原失败原因对应，post-retry evidence 也必须重新验证原 acceptance rule。

最后的 handoff 把计划、执行日志、就绪验收和 incident record 串起来。Completion 不是所有格子都填满，而是关键状态都有 evidence、UNKNOWN 没有被隐藏、失败有 recovery 或明确 stop、下一位 operator 知道下一 action。这样的闭环才能让活动在组织者临时离场时仍可运行。
''')
append_runtime('chapters/03_iterate_next.md', r'''
## 从“复盘感想”走到可重建的下一决策
复盘最危险的快捷方式，是把情绪强度当作 signal strength。一个人强烈抱怨节奏，并不自动等于全体体验失败；同样，现场气氛热烈也不能证明所有参与者都获得价值。先回到 baseline：这次原本希望发生什么，哪些 expected state 有明确定义，然后再看 actual evidence。Signal interpretation 必须把原始观察与解释分开，并保留反证和 UNKNOWN。

下一步是 change control。假设迟到率高于预期，候选 options 可能是延后开场、保留开场但增加缓冲签到、或不改变。Criteria 要在看结果之前尽量明确：迟到人数、迟到时长、是否影响核心讨论、改变时间对其他人的成本。Decision 输出 KEEP / REVISE / STOP 时，要写 rationale 与 tradeoff，而不是只留下结论。Revisit trigger 说明什么新证据会让这个判断失效。

Iteration log 还必须能承接失败。若反馈样本太少，failure 不是“没有结果”，而是 evidence insufficiency。Recovery 是补采样或换一种观察方式；Retry 仍使用同一判断规则，除非你明确记录了为什么规则本身需要 revision。若连续两轮都无法获得足够信号，stop condition 可以是暂不修改流程，而不是无限收集数据。

真正的 completion evidence 是一个别人能重建的 trace：baseline version → evidence IDs → result → interpretation → decision rule → selected outcome → next action。下一次组织者打开日志时，不需要问“上次为什么改成这样”。这才是复盘资产的 Reader Outcome：读者不只是会写记录，而是能利用记录做出新的、可解释的判断。
''')

# Promise-level operator references need reading structure as well as raw signals.
obs=OUT/'references/operator/observability_decision.md'
obs.write_text(r'''# Observability Decision Operator Reference
## Judge the Signal
Baseline: use the approved event plan and baseline snapshot. Signal interpretation separates raw result from explanation. Decision / rule: KEEP, REVISE or STOP only when evidence scope supports the decision scope; UNKNOWN remains explicit.
## Execute and Control Change
Input: linked evidence IDs. Execution steps: compare signal to baseline, state proposed change, impact and next action. Change control requires rationale and a revisit trigger rather than reacting to one emotional comment.
## Validate, Recover, Complete
Validation: another organizer can reproduce the output decision from the evidence. Failure / recovery: contradictory feedback stays UNKNOWN; collect another independent sample and retry under the same rule. Boundary: do not erase counter-evidence. Completion state: baseline, interpretation, decision, validation and handoff are linked.
''' + '\n' + obs.read_text(encoding='utf-8'),encoding='utf-8')
rb=OUT/'references/operator/rollback_recovery.md'
rb.write_text(r'''# Rollback / Recovery Operator Reference
## Judge the Recovery Boundary
Rollback target is the last approved safe state. Decision rule: rollback only when it reduces risk without hiding incident evidence. Stateful caveat: safety/access incidents survive schedule restoration.
## Execute the Recovery
Input: failure trigger and incident record. Execution steps: diagnose, stop affected action, apply rollback/recovery, record output and prepare retest. Owner and next action stay explicit.
## Validate, Retry, Complete
Validation uses the same acceptance rule that failed. Failure / recovery: if retest fails again, stop repeated retries and escalate. Completion state requires rollback target, method, post-retry evidence, boundary and handoff.
''' + '\n' + rb.read_text(encoding='utf-8'),encoding='utf-8')

"""
s=s.replace(marker,insert+marker)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_PREFREEZE_SELF_SUFFICIENCY_PATCH_V3_APPLIED')
