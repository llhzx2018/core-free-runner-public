# P07 · USER ACCEPTANCE

Last reconciled: 2026-10-16

> This file is the Authority for **real user usability**. Machine PASS does not imply Owner Real PASS. One real migration path PASS also does not imply every P07 capability is Owner-accepted.

## Current status

```text
Engineering / Machine regression layer       release85 migration machine evidence PASS (not all independent CI)
Full-server Migration Owner Real Path        REAL_PASS / PRODUCTION_PASS
Full-server Migration DNS Cutover            OWNER_MANUAL_PASS
Full-server Migration Source Recovery Copy   RETAINED
Old-server Decommission Safety               NOT_PROVEN / DELETE_DENIED
Other P07 real-user capability paths         MIXED / NOT blanket-proven
P07 User Acceptance                          PARTIAL / NOT_BLANKET_PASS
release69+ Hardening Owner Real               NOT_RUN
release85 MariaDB 10.11 new VPS Owner Real     NOT_RUN
release85 MySQL 8.4 -> MariaDB 10.11 Owner Real NOT_RUN
System Care rc54 real-mutation workflow        HISTORICAL_FAILURE / R2_FIX_PENDING_PROOF
```

## Release85 identity and evidence separation · 2026-10-16

Release85 is the current **published baseline** (product `BUILD_ID=0.1.0-release85`, public Toolbox Slot3, System Care rc54). Its MariaDB 10.11 default installation and target-side migration guard were validated by synthetic machine tests; no real new VPS MySQL/Percona → MariaDB migration has been observed.

The 2026-10-05 **release68** real 16-site migration remains a genuine historical Owner PASS for that exact old-engine environment, not release85 MariaDB compatibility proof.

Round 1 hardening work is an **unmerged candidate** on product PR #196, with 143/143 isolated exact-source regressions PASS. Candidate PASS does not update released byte identities or Owner Real status.

System Care real-mutation workflow failure on release85 is a distinct CI finding, not an assertion that cleanup actually failed; its release85 workflow checks obsolete success wording. Keep this non-PASS until rerun evidence confirms the corrected workflow.

## Current real Owner result · 2026-10-05

A genuine 16-site SOURCE → TARGET full-server migration completed through the public P07 Toolbox path.

```text
migration_id = pull-20261005T062015Z-04275579
source        = 24.199.108.229
target        = 45.76.171.57
site_count    = 16
closure_build = 0.1.0-release68
```

Observed real closure:

```text
final incremental synchronization PASS
target-local verification          16/16 PASS
Owner manual DNS switch            PASS
public route verification          PASS
Production verification            PASS
old server retained                YES
automatic DNS mutation             NO
old server deletion                NO
```

Canonical evidence:
`docs/evidence/P07_FULL_SERVER_MIGRATION_REAL_PRODUCTION_PASS_20261005.md`.

The real run exposed and closed field defects across release62-release68. The decisive release68 issue was a hidden VF Press Runtime directory outside Web Root that existed on SOURCE but was absent from the original migration external-assets list. After exact root-cause repair and same-task resume, all 16 target sites and public Production verification passed.

## Evidence separation

The release68 real result supersedes the 2026-09-06 RC2 failure **only for the full-server TARGET_PULL migration path**.

Historical evidence remains valid for the exact bytes and capabilities it tested:

- RC1 field failures remain historical failures.
- RC2 incomplete migration remains historical evidence that those older bytes did not prove the path.
- historical engineering Real Gate evidence remains valid for its exact older identities.
- release68 is the current real Owner evidence for full-server TARGET_PULL migration.
- release69 is post-PASS hardening and has no independent Owner Real run unless a later real migration proves it.

The following claims remain prohibited:

```text
"P07 User Acceptance PASS"              without qualifying the capability
"all backup/restore/storage paths PASS" from the migration result
"old server can be deleted"             before separate decommission audit
"release69+ Owner Real PASS"            without a fresh real run
"release85 MariaDB new-VPS Real PASS"     without an actual MariaDB server run
```

## Current identities

```text
current released product build         0.1.0-release85 (source/main; public distributor)
formal public release                  p07-v0.1.0-release85-mariadb-1011
system care package                    0.1.0-rc54
2026-10-05 real migration build        0.1.0-release68 (historical exact-source evidence)
release68 source main                  68738ec8a1f3651d84db86b103cfa52b57653f8f
release68 public main                  6496f6b3c80f9e7c8b499d02df3a363708ec489f
release69 former candidate             0.1.0-release69 (historical only)
release85 MariaDB Owner real           NOT_RUN
overall P07 Owner real                 PARTIAL / NOT_BLANKET_PASS
```

## Historical RC1 field result

RC1 remains retired after the earlier Owner field test exposed installation-root, Inventory and beginner-UX defects.

```text
RC1_ENGINEERING_CORE = PASS
RC1_PUBLIC_INSTALL_USER_PATH = FAIL
RC1_USER_ACCEPTANCE = FAIL
RC1_STATUS = RETIRED
```

## Remaining real-user acceptance work

The successful full-server migration does not close unrelated P07 capabilities. Remaining real-user evidence may still be required for:

```text
Restore-As / new-domain recovery paths
remote backup/storage onboarding paths
guarded scheduler paths
old-server non-site service decommission audit
future release69+ hardening real migration
```

These are independent of the completed release68 full-server migration.

## Safety boundary after Production PASS

```text
automatic DNS mutation       DENY
automatic old-server delete  DENY
unrelated TARGET overwrite   DENY
secret output                DENY
old server Recovery Copy     RETAIN
old-server decommission      separate audit required
```

The full-server migration Production PASS does not authorize deletion of the old server.
