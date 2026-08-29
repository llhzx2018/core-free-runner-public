from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')
start=s.index("thin_iteration = r'''\n# Post-event Iteration Log / Next Decision — intentionally shallow trace")
end=s.index("'''\niter_path.write_text(thin_iteration.strip() + '\\n', encoding='utf-8')", start)
replacement=r"""thin_iteration = r'''
# Post-event Iteration Log / Next Decision — intentionally shallow trace
## Context
Task: write one post-event next decision for the next reading-club session. Owner: organizer. Input: participant feedback and event notes. Scope: session format only. Output: one keep/revise/stop choice for handoff.
## Evidence Notes
Source: participant survey and organizer notes. Record: ____ . Evidence: ____ . Raw observation: ____ . Confidence / UNKNOWN: ____ . The notes are kept for later review, but this tool does not create a reconstructable trace across observations and decisions.
## Decision Rule
Options: KEEP / REVISE / STOP. Criteria: revise when repeated friction is material and the change cost is acceptable. Supporting evidence: survey plus organizer notes. Selected outcome: ____ . Rationale / tradeoff: ____ . Uncertainty: ____ . Revisit trigger: a later cohort shows a materially different pattern.
## Validation
Expected output: one explicit next decision. Validation: a second organizer checks whether the choice follows the stated criteria. PASS / FAIL: ____ . Gap / rework: ____ . Completion: ____ .
## Failure Recovery
Failure: feedback is unclear or contradictory. Recovery: collect another sample. Retry: review again after more feedback. The recovery note remains deliberately generic and does not preserve a diagnostic or post-retry trail.
## Worked Example
Example: two people say the session felt rushed. Reference judgment: keep the issue open rather than changing immediately because the evidence is weak. Why: one small sample should not redefine the whole group. Common error: treat a loud comment as group truth. Correction: ask the same question again. Adaptation: use a different feedback channel when response rate is low.
## Training Instrument
- 预期输出：写出 KEEP / REVISE / STOP 之一。
- 参考判断：UNKNOWN 不能直接当 PASS。
- 常见错误：只写结论，不写标准。
- 纠错：补充标准和证据。
- 重试：获得新样本后再做一次判断。
## Completion
Completion: close when the decision, validation and next action are present. Blocker / UNKNOWN: ____ . Next action / handoff: ____ .
'''
"""
s=s[:start]+replacement+s[end+4:]
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_ADVERSARIAL_TRUTH_PATCH_V10_APPLIED')
