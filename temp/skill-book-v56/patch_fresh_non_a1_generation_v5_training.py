from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')
marker="# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.\n"
assert s.count(marker)==1
insert=r"""# Reader-facing training loops: make expected output, judgment, error diagnosis,
# correction, retry and completion observable in the chapters/linked assets themselves.
append_runtime('chapters/01_evidence_and_decision.md', r'''
## 训练回路：把一句参与者原话变成可用于决策的证据
**预期输出**：完成 1 条 evidence record，至少包含 source、date/context、raw statement、interpretation、confidence、counter-evidence/UNKNOWN 与 linked decision。**参考判断**：如果“19:00 前很难到”只来自 P07，它可以支持为 P07 设计缓冲签到，但不能单独支持把全场开始时间改到 19:15。**错误类型**：把 interpretation 写成 raw fact、丢掉来源、用“大家都”扩大证据范围，或没有任何反证检查。**纠错**：回到原始来源，把事实与解释拆开，并补一条“这份证据不能证明什么”。**重试**：用修正后的 evidence 再走一次 venue/format decision rule，检查结论是否仍成立。**完成条件**：另一位组织者能从记录重建“谁提供了什么证据、它支持哪个判断、边界在哪里”，才算完成。
''')
append_runtime('chapters/02_plan_execute_accept.md', r'''
## 训练回路：把 18:50 的突发缺席变成可交接操作
**预期输出**：写出一条 owner-change record，加上一轮重新执行的 readiness evidence；不能只写“B 已接手”。**参考判断**：access、host、materials、safety 四个 critical preconditions 若全部可由 B 验证，才允许继续；任何一个 critical state UNKNOWN，都应保持 NOT_READY 或 PAUSE。**错误类型**：只改负责人姓名、跳过 impact/revalidation、失败后重复同一步、或把参与者已经在路上当成必须继续的理由。**纠错**：补 change reason、impact、rollback target、failure diagnosis 与 retest evidence，再重新做 READY/NOT_READY 判断。**重试**：只有造成失败的 precondition 已被纠正并留下新证据时，才重新执行原 acceptance check。**完成条件**：备用志愿者无需口头补充，就能从 plan、execution log 与 acceptance record 接着执行，并知道何时继续、暂停或停止。
''')
append_runtime('chapters/03_iterate_next.md', r'''
## 训练回路：面对矛盾反馈，不急着“优化”
**预期输出**：完成一条 baseline → raw signals → interpretation → options → decision rule → selected outcome → uncertainty → revisit trigger → next action 的 iteration trace。**参考判断**：5 人迟到、4 条“太赶”与 7 条“19:00 最方便”同时存在时，当前证据更支持先改 onboarding 流程而不是直接延后 baseline time。**错误类型**：只挑支持自己直觉的反馈、把匿名情绪当高置信证据、或在原因仍 UNKNOWN 时直接改规则。**纠错**：把 supporting 与 counter-evidence 并列，写清当前不能区分的原因，并设计下一次可区分原因的 observation。**重试**：下一场按同一 criteria 重新收集到场时间与拆分后的反馈问题，再判断 KEEP / REVISE / STOP。**完成条件**：另一个组织者可以从 trace 重建为什么这次不改时间、什么新证据会触发重审，以及下一步具体收集什么。
''')

"""
s=s.replace(marker,insert+marker)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_TRAINING_FEEDBACK_PATCH_V5_APPLIED')
