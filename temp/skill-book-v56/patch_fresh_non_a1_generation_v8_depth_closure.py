from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')
marker="# GOOD fresh-generation tree: broad generation responsibilities + depth + local-value gates.\n"
assert s.count(marker)==1
insert=r"""# Close exact Practical Asset Depth findings without changing the verifier.
append_runtime('templates/01_participant_evidence_capture.md', r'''
## Evidence Verification
Expected: provenance, raw statement, interpretation boundary, confidence/UNKNOWN and linked action are all present. Actual: ____ . Verification method: second organizer compares the record with the original registration/interview source. Verification evidence: source reference ____ . PASS / FAIL / PARTIAL: ____ . Defect / rework: ____ . Closure / acceptance decision: ____ .
## Evidence Failure Recovery
Failure trigger / anomaly: source cannot be verified, interpretation is written as fact, or confidence is unsupported. Diagnosis / likely cause: ____ . Recovery action: return to the original participant/source and correct the record without deleting the failed version. Retry condition: source and boundary can now be checked. Post-retry evidence / retry result: ____ . Escalate / pause / stop when the source cannot be recovered or the evidence remains contradictory.
''')
append_runtime('templates/02_venue_format_decision_record.md', r'''
## Decision Validation
Expected: the same evidence set and rule reproduces the selected option. Actual: ____ . Verification method: independent organizer re-scores every surviving option. Verification evidence: decision replay ID ____ . PASS / FAIL / PARTIAL: ____ . Defect / rework: ____ . Closure: ____ .
## Decision Failure Recovery
Failure trigger: options tie, a critical UNKNOWN changes eligibility, or replay yields a different outcome. Diagnosis / likely cause: missing evidence, ambiguous threshold, or inconsistent option comparison. Recovery action: collect the missing evidence or clarify the rule before choosing. Retry condition: the disputed criterion can be evaluated consistently. Post-retry evidence: ____ . Escalate / pause / stop when a critical participation constraint cannot be resolved.
''')
append_runtime('templates/03_event_plan_contract.md', r'''
## Plan Input Evidence
Evidence item / observation: approved venue decision and participant constraints. Source / provenance: decision record ID ____ and venue agreement ____ . Date / version: ____ . Confidence / UNKNOWN: ____ . Raw fact vs interpretation: ____ . Linked decision / action: baseline plan RC-PLAN-____.
## Plan Decision Rule
Options: ACCEPT CHANGE / REJECT CHANGE / DEFER. Criteria / threshold: proposed change may proceed only when critical access, owner coverage, timing and safety assumptions remain valid after impact review. Evidence source: change evidence ID ____ . Selected decision / outcome: ____ . Rationale / tradeoff: ____ . Uncertainty: ____ . Revisit trigger: new evidence invalidates an affected assumption.
## Plan Recovery Detail
Failure trigger: revalidation of any critical assumption fails. Diagnosis / likely cause: ____ . Recovery action / rollback: restore the last approved baseline or isolate the failed change. Retry condition: failed precondition corrected. Post-retry evidence / retry result: ____ . Escalate / pause / stop when the safe baseline cannot be restored or repeated retest fails.
''')
append_runtime('templates/05_readiness_acceptance_record.md', r'''
## Acceptance Execution Steps
Owner: second volunteer verifier. Inputs: approved plan, venue state and readiness evidence. 1. Inspect each critical expected state. 2. Capture actual evidence before assigning PASS / FAIL / PARTIAL. Checkpoint: no critical field remains UNKNOWN. Exception path: if blocked, handoff to recovery owner rather than marking READY. Next action: authorize doors-open state or keep NOT_READY.
## Acceptance Failure Recovery
Failure trigger: any critical expected state is FAIL or UNKNOWN. Diagnosis / likely cause: ____ . Recovery action / correction: ____ . Retry condition: the identified defect has been reworked. Post-retry evidence / retry result: ____ . Escalate / pause / stop when the defect affects access/safety or fails the same check twice.
''')
append_runtime('templates/07_post_event_iteration_log.md', r'''
## Iteration Failure Recovery
Failure trigger: evidence sources conflict, sample quality is too weak, or the decision cannot be reproduced. Diagnosis / likely cause: sampling bias, mixed causes or broken evidence linkage. Recovery action: preserve UNKNOWN, collect a discriminating signal, or correct the linkage. Retry condition: the missing signal is available under the same decision rule. Post-retry evidence / retry result: ____ . Escalate / pause / stop when repeated observations still cannot distinguish the competing explanations; do not change the baseline merely to create movement.
''')
append_runtime('templates/08_baseline_snapshot.md', r'''
## Baseline Decision Rule
Options: KEEP ACTIVE / SUPERSEDE / INVALIDATE. Criteria / threshold: only a source-verified snapshot with complete time/version context can remain ACTIVE. Evidence source / supporting evidence: ____ . Selected decision / outcome: ____ . Rationale / tradeoff: ____ . Uncertainty: ____ . Revisit trigger: source, scope or approved plan changes.
## Baseline Change Control
Baseline version: ____ . Proposed change: ____ . Change reason / evidence: ____ . Owner / authority: ____ . Impact / affected assumptions: ____ . Revalidation: ____ . Accept / Reject / Defer: ____ . Superseded version / rollback target / freeze state: ____ .
## Baseline Validation
Expected: active snapshot matches the approved plan and traceable sources. Actual: ____ . Verification method: compare source IDs, timestamps and frozen scope. Verification evidence: ____ . PASS / FAIL / PARTIAL: ____ . Defect / rework: ____ . Closure / acceptance decision: ____ .
## Baseline Failure Recovery
Failure trigger: baseline is incomplete, superseded or source cannot be verified. Diagnosis / likely cause: ____ . Recovery action: restore last verified baseline or recapture corrected state. Retry condition: source/version mismatch is resolved. Post-retry evidence / retry result: ____ . Escalate / pause / stop when no verified baseline exists; later comparison must remain blocked.
''')

"""
s=s.replace(marker,insert+marker)

# Make the adversarial mutation a genuine old-Adequacy false green: large/structured and
# keyword-complete, but still missing evidence-log trace depth and a complete recovery loop.
mut_marker="iter_path.write_text(thin_iteration.strip() + '\\n', encoding='utf-8')\n"
assert s.count(mut_marker)==1
thin_override=r"""thin_iteration = r'''
# Post-event Iteration Log / Next Decision — intentionally shallow trace
## Context
Task: record the post-event iteration decision. Owner: organizer. Input: feedback and event notes. Scope: next-event format. Handoff: next action owner.
## Evidence Log
Source: participant survey. Date: ____ . Note / observation: ____ . UNKNOWN / confidence: ____ . Evidence is reviewed before decision. This log intentionally has no stable Record ID, no explicit result→interpretation pair, and no linked decision/change field.
## Decision Rule
Options: KEEP / REVISE / STOP. Criteria / threshold: revise when repeated friction appears material. Supporting evidence: survey and organizer notes. Decision / selected outcome: ____ . Rationale / why: ____ . Uncertainty: ____ . Revisit trigger: cohort or repeated friction changes.
## Validation
Expected: a next decision is named. Actual: ____ . Verification method: organizer review. Verification evidence: notes. PASS / FAIL / PARTIAL: ____ . Defect / rework: ____ . Closure: ____ .
## Failure / Recovery
Failure trigger: feedback is unclear. Recovery action: collect more feedback. Retry: try again after more notes. This intentionally omits diagnosis, post-retry evidence and a real escalation/stop boundary.
## Worked Example / Guidance
Example: two people say “too rushed”; reference judgment: keep the issue open rather than changing immediately because the evidence is weak. Common error: treating a loud comment as group truth. Correction: ask the same question next time. Adaptation: use a different feedback channel if response rate is low.
## Training Instrument
- 预期输出：写出一条下一决定。
- 参考判断：UNKNOWN 不能直接当 PASS。
- 常见错误：只写结论。
- 纠错：补一条证据。
- 重试：下次再检查。
## Completion
Completion: close when the note, decision and next action are present. Blocker / UNKNOWN: ____ . Next action / handoff: ____ .
'''
"""
s=s.replace(mut_marker,thin_override+mut_marker)
p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_DEPTH_CLOSURE_PATCH_V8_APPLIED')
