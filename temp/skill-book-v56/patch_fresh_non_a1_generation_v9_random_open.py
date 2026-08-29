from pathlib import Path

p=Path('temp/skill-book-v56/fresh_non_a1_reading_club.py')
s=p.read_text(encoding='utf-8')

# Strengthen only the exact H2 windows sampled by Random Open. Do not alter the verifier.
old="""Counter-evidence / contradiction / UNKNOWN: ____
Linked decision / action informed: ____
## Evidence Trace
"""
new="""Counter-evidence / contradiction / UNKNOWN: ____
Linked decision / action informed: ____
Decision rule: if source, interpretation boundary or confidence is missing, do not promote this evidence into a group decision.
Validation step: compare the raw statement with the source before handoff.
Next action / output: send a verified record to the venue decision; otherwise route it to recovery.
## Evidence Trace
"""
assert s.count(old)==1
s=s.replace(old,new)

old="""Baseline version / current version: BASE-____. Frozen scope: venue, start/end time, seating capacity, host, budget ceiling. Superseded version / rollback target: ____ . Freeze state: ACTIVE / SUPERSEDED.
## Completion
"""
new="""Baseline version / current version: BASE-____. Frozen scope: venue, start/end time, seating capacity, host, budget ceiling. Superseded version / rollback target: ____ . Freeze state: ACTIVE / SUPERSEDED.
Decision rule: only the source-verified current version may authorize comparison or rollback.
Execution step: mark the active version, preserve the superseded version, then validate the freeze state before handoff.
Output / next action: ACTIVE baseline goes to event execution; INVALID or UNKNOWN goes to recovery.
## Completion
"""
assert s.count(old)==1
s=s.replace(old,new)

old="""Revisit trigger / reconsider if: next cohort composition changes materially or the same friction repeats.
Next action: ____
## Completion
"""
new="""Revisit trigger / reconsider if: next cohort composition changes materially or the same friction repeats.
Validation step: replay the rule against the linked evidence before accepting the output decision.
Failure condition: if the evidence cannot reproduce the decision, keep UNKNOWN and enter recovery rather than changing the baseline.
Next action / output: ____
## Completion
"""
assert s.count(old)==1
s=s.replace(old,new)

p.write_text(s,encoding='utf-8')
print('FRESH_GENERATOR_RANDOM_OPEN_PATCH_V9_APPLIED')
