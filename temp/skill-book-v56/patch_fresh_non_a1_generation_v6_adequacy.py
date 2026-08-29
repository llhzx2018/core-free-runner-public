from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')

# The HIGH asset contract must declare the responsibility surface actually required by the tool.
marker="for i, path in enumerate(asset_paths):\n"
assert s.count(marker)==1
contract_patch=r"""role_dims.update({
    'evidence_capture': ['context_task','input_evidence','evidence_log','decision_rule','validation_acceptance','failure_recovery','completion','example_guidance'],
    'decision_record': ['input_evidence','decision_rule','validation_acceptance','failure_recovery','completion','example_guidance','state_boundary'],
    'plan_or_contract': ['context_task','input_evidence','decision_rule','change_control','validation_acceptance','failure_recovery','completion'],
    'execution_brief_or_log': ['context_task','input_evidence','execution_steps','evidence_log','failure_recovery','validation_acceptance','completion'],
    'acceptance_record': ['input_evidence','decision_rule','execution_steps','validation_acceptance','failure_recovery','completion','example_guidance'],
    'iteration_log': ['input_evidence','evidence_log','decision_rule','validation_acceptance','failure_recovery','completion','example_guidance'],
    'baseline_snapshot': ['input_evidence','evidence_log','decision_rule','change_control','validation_acceptance','failure_recovery','completion'],
})

"""
s=s.replace(marker,contract_patch+marker)

marker2="# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.\n"
assert s.count(marker2)==1
content_patch=r"""# Close the remaining Adequacy gaps with substantive reading core and self-contained training instruments.
append_runtime('chapters/01_evidence_and_decision.md', r'''
## Worked Scenario：三种相互冲突的“场地偏好”怎么处理
报名结束后有 18 人确认参加。P03 写“咖啡馆更轻松”，P08 说自己使用轮椅且需要无台阶入口，P12 表示公共空间太吵会影响参与讨论；另外 6 人没有填写场地偏好。最差的做法是把三条意见压缩成“大家偏好安静、轻松、无障碍”，因为这种总结抹掉了 evidence scope，也无法告诉你哪个条件是 preference、哪个是 participation blocker。

先建立 evidence ledger。P03 的 raw statement 是个人氛围偏好，confidence 对 P03 本人高，但对全体外推低；P08 的无障碍需求直接关联“能否参加”，属于 critical constraint；P12 的噪声担忧需要进一步观察场地实际声压或试坐体验。那 6 个空白不能被解释成“没有要求”，应保留为 UNKNOWN。Counter-evidence 也要记录：如果某家咖啡馆有独立包间，P12 的噪声担忧可能不成立；如果社区活动室有台阶但提供合规电梯，P08 的限制也需要重新验证，而不是仅凭场地标签判断。

接着把 evidence 转成 decision criteria。Options 可以是 A 图书馆活动室、B 咖啡馆包间、C 社区活动室。先给 criteria 排层级：第一层是 participation blockers，例如可达性与安全；第二层是讨论质量，例如噪声与私密性；第三层才是氛围和便利偏好。Decision rule 不是“票数最多”，而是任何 critical blocker 未解决的 option 不能进入最终比较。对于剩余 options，再比较预算、交通和讨论体验。这样读者学到的是如何让证据权重来自任务后果，而不是来自谁表达得更强烈。

假设实地核查后：A 无障碍 PASS、噪声 PASS、预算 PASS；B 无障碍 PASS，但周五 19:00 包间最低消费超预算；C 电梯在活动当晚维修，access UNKNOWN。Selected decision 应是 A，并把 B 作为费用条件变化时的备用方案。Rationale 要引用 evidence IDs，而不是写“综合考虑最好”。Revisit trigger 可以是 A 临时取消、B 取消最低消费，或 C 的电梯恢复并完成现场验证。

再做一次反事实检查：如果 P08 临时取消参加，是否就能忽略无障碍？不能自动这么做，因为新的参与者也可能有未披露的 access need；正确做法是回到活动的 accessibility baseline，判断它是全局质量标准还是仅针对单个已知 participant。这个 boundary 能防止 evidence-led decision 退化成“谁来谁说了算”。

### 练习：从证据到场地决策
给自己增加一条新证据：“P15 只能乘公共交通，C 比 A 少换乘一次。”先写 raw evidence、scope、confidence 与 counter-evidence，再判断它是否改变 selected option。预期不是必须换场地，而是能说明这条 evidence 位于哪个 criteria 层级、是否超过原 rule 的阈值、若不改变决定又应如何进入记录。最后让另一个人只看你的 ledger 和 decision record，检查是否能复现结论；如果不能，说明 trace 仍不够完整。
''')

TRAINING_TOOL_BLOCK=r'''
## Training Instrument
- **预期输出**：完成一份可复核记录，所有关键 input、decision/result 与 next action 都有明确位置。
- **参考判断**：UNKNOWN 不能当 PASS；证据范围必须与决定范围匹配，critical blocker 优先于普通偏好。
- **常见错误**：只填结论、忽略反证、把主观解释写成事实，或失败后直接重复原动作。
- **纠错**：回到 evidence / rule / validation 三处定位断点，只修导致 BLOCK 的责任链，并保留原失败记录。
- **重试**：使用同一 acceptance rule 重新检查修正后的输出；若仍失败则诊断新原因，不覆盖旧 evidence。
- **完成条件**：另一位 operator 能独立重建判断、执行下一步，并知道何时暂停、升级或重新评估。
'''
append_runtime('templates/02_venue_format_decision_record.md', TRAINING_TOOL_BLOCK)
append_runtime('templates/05_readiness_acceptance_record.md', TRAINING_TOOL_BLOCK)
append_runtime('templates/07_post_event_iteration_log.md', TRAINING_TOOL_BLOCK)

"""
s=s.replace(marker2,content_patch+marker2)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_ADEQUACY_PATCH_V6_APPLIED')
