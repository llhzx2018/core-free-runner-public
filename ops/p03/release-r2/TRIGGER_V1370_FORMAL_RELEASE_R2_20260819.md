P03 V1.37.0 Formal Release Bridge R2 trigger.
Verified Candidate: llhzx2018/vf-forge@11909e07b682765346d4ef890402b4ce00b91291
Production baseline: V1.36.2 / main 3962a68bbbcfbfc5aece6a338effebcafac759a9 / Schema30.
R2 is idempotent if main/tag/release were partially advanced by an earlier attempt.
Authorized flow: Atomic Gate -> non-force main fast-forward -> exact-main rebuild -> v1.37.0 Release Asset -> core-updates -> remote readback.
Production Upgrade excluded. Production Write=0.
