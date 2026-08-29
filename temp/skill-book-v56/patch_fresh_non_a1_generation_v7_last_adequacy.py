from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')
marker="# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.\n"
assert s.count(marker)==1
insert=r"""# Final Adequacy closure from the exact report: one chapter shell boundary and baseline structure.
append_runtime('chapters/01_evidence_and_decision.md', r'''
## 什么时候应该停止继续收集证据
证据越多不一定越好。若所有 surviving options 已满足 critical constraints，新增证据只会重复同一判断，就应进入 decision，而不是无限采访。相反，只要一个 UNKNOWN 可能改变 option 的可参加性、安全或预算边界，就不能因为“多数意见已经够了”而提前关闭。一个可操作的 stop rule 是：先问“下一条证据是否可能改变 selected option 或 revisit trigger？”若答案是否定，就记录当前 uncertainty 并行动；若答案是肯定，就明确缺哪一条 evidence、由谁补、何时回到 decision。这样既避免凭印象过早决定，也避免把研究变成拖延。
''')
append_runtime('templates/08_baseline_snapshot.md', r'''
## Baseline Capture Checklist
- [ ] Source / evidence ID：____
- [ ] Capture date / time：____
- [ ] Owner / authority：____
- [ ] Active baseline version：____
- [ ] Frozen scope / assumptions：____
- [ ] UNKNOWN / exception：____
- [ ] Superseded version / rollback target：____
- [ ] Verification result — PASS / FAIL / PARTIAL：____
- [ ] Linked next decision / handoff：____

Decision rule: only a verified ACTIVE baseline may be used for later comparison. Failure / recovery: if any critical source, timestamp or version field is missing, mark the snapshot INVALID, recover the last verified state or recapture it, and retry validation before using it. Completion condition: checklist, evidence and next-decision linkage are all reviewable by another organizer.
''')

"""
s=s.replace(marker,insert+marker)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_LAST_ADEQUACY_PATCH_V7_APPLIED')
