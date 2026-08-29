from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')
marker="# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.\n"
assert s.count(marker)==1
insert=r"""# Promise-depth strengthening driven by the fresh PRE_FREEZE report.
append_runtime('chapters/02_plan_execute_accept.md', r'''
## Worked Scenario：18:50 主组织者突然不能到场
假设 baseline 规定 19:00 开场，主组织者负责场地钥匙、主持人与物料确认；18:50 他因交通事故无法到场。第一步不是“群里找个人顶上”，而是先判断 change 是否 reversible。Evidence input 包括：备用志愿者已经到场、场地方确认可以由备用联系人取钥匙、主持人已到、付款和紧急联系人信息可访问。Decision rule 是：只有 access、host、materials、safety 四个 critical preconditions 都能由新 owner 接手，才允许执行 owner change；否则 event state 应进入 PAUSE。

接着做 change control：记录 proposed change = floor lead 从 A 改为 B；reason = A 无法在开场前到达；impact = 钥匙领取、签到、现场异常升级人发生变化；authority = 预先授权的 backup lead；rollback target = 原 baseline plan 中未改变的时间、场地和主持安排。Execution 不是一句“B 接手”，而是 B 按 run-of-show 重新执行 access check、host check、materials check，并把 actual result 写入 evidence log。

若 access check FAIL，例如场地方拒绝备用联系人取钥匙，failure diagnosis 是身份授权不足，而不是“时间来不及”。Recovery action 是联系场地方授权人或切换到事先批准的备用场地；retry condition 是新的访问权限已有可验证证据。若两条 recovery path 都失败，stop condition 是取消或延期，不能因为已有参与者在路上就把 NOT_READY 强行改成 READY。

最后再做 acceptance：Expected 是四个 critical preconditions 全部可验证，Actual 逐项记录，Verification method 由另一位志愿者复核。这样读者可以看到完整链条：evidence → change decision → execution → failure diagnosis → rollback/recovery → retest → acceptance。练习：把“主持人迟到 10 分钟”代入同一链条，判断哪些状态可以局部调整，哪些会触发 PAUSE，并写出你的 next action。
''')
append_runtime('chapters/03_iterate_next.md', r'''
## Worked Scenario：五个迟到、四条“太赶”的反馈，到底要不要改时间？
这次 baseline 是 19:00 开场、90 分钟讨论，共 18 人确认。活动结束后得到四类 raw signals：5/18 人迟到超过 8 分钟；4 份匿名反馈写“开头太赶”；主持人记录前 15 分钟需要重复说明两次；但另有 7 人明确表示 19:00 对下班后到场最方便。这些都是 evidence，不是结论。先保留 counter-evidence：迟到可能来自当天交通异常，匿名反馈也不知道是否来自迟到者。

Interpretation 可以写成：“开场节奏存在摩擦，但尚不能证明整体开始时间错误。” Options 至少有三项：A 延后到 19:15；B 保持 19:00，但增加 10 分钟缓冲签到并把核心讨论放到 19:10 后；C 完全不改。Decision rule 预先约定：只有两种独立证据都显示开始时间本身造成持续损失，才改 baseline time；若问题更像 onboarding friction，则优先改流程而不是改时间。

按这个 rule，当前 selected decision 更适合 B。Rationale 是迟到和“太赶”支持 onboarding friction，但 7 条 counter-evidence 说明直接延后可能伤害另一批参与者。Uncertainty 保留：当天交通是否异常、匿名反馈是否集中于迟到者。Revisit trigger 是下一场仍有 >=4 人迟到且结构化反馈继续指向开始时间；next action 是下一场固定记录到场时间，并在问卷中把“开始时间不合适”和“开场流程太赶”拆成两个问题。

训练：如果下一次只有 2 人迟到，但 8 人说“讨论结束太晚”，不要把旧结论机械复用。先把新 evidence 与原 baseline 分开，再重新判断问题到底是 start time、session length 还是 discussion control。Reference judgment：当 evidence 不能区分原因时，正确状态是 UNKNOWN；Recovery 是设计一个能区分原因的下一轮观察，而不是为了显得果断立刻改时间。Completion evidence 应能让另一个组织者重建：baseline → raw signals → interpretation → options → rule → selected decision → uncertainty → revisit trigger → next action。
''')

"""
s=s.replace(marker,insert+marker)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_PROMISE_CHAPTER_DEPTH_PATCH_V4_APPLIED')
