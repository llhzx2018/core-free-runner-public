# P07 · USER ACCEPTANCE

Last reconciled: 2026-10-17

> This file is the Authority for **real user usability**. Machine PASS does not imply Owner Real PASS. One real migration path PASS also does not imply every P07 capability is Owner-accepted.

## Current status

```text
Engineering / Machine regression layer       release87 exact-source 669/669 PASS (56 modules, six jobs); native CI BLOCKED_INFRA_JOB_START
Full-server Migration Owner Real Path        REAL_PASS / PRODUCTION_PASS
Full-server Migration DNS Cutover            OWNER_MANUAL_PASS
Full-server Migration Source Recovery Copy   RETAINED
Old-server Decommission Safety               NOT_PROVEN / DELETE_DENIED
Other P07 real-user capability paths         MIXED / NOT blanket-proven
P07 User Acceptance                          PARTIAL / NOT_BLANKET_PASS
release69+ Hardening Owner Real               NOT_RUN
release87 MariaDB 10.11 new VPS Owner Real     NOT_RUN
release87 MySQL 8.4 -> MariaDB 10.11 Owner Real NOT_RUN
System Care rc56 published; Owner runtime        UNKNOWN
release87 direct --build-id and menu             OWNER_VERSION_ONLY_PASS
System Care rc55 historical isolated mutation  MACHINE_PASS / runner 38992499233
```

## Current release87 identity · 2026-10-17

- Published release: [release87-security-hardening](https://github.com/llhzx2018/core-free-runner-public/releases/tag/p07-v0.1.0-release87-security-hardening), not draft/prerelease; [formal workflow](https://github.com/llhzx2018/core-free-runner-public/actions/runs/39018906649) SUCCESS. Product `main`: `2507e4d713784f3db476308135a97c0df4fe86a7`. Public `main`: `ecaefcf0435105ee29097799ad244d652aa1efb3`.
- Published modules: Slot3 `0.1.0-release87`, System Care `0.1.0-rc56`. Toolbox public version remains `V0.1.0`, five visible menus / four installable modules.
- Independent [exact-source workflow](https://github.com/llhzx2018/core-free-runner-public/actions/runs/39016204444): six jobs SUCCESS, with 56 modules / 669-of-669 tests reported PASS. Product-native CI pre-job startup failure is `BLOCKED_INFRA_JOB_START`, **not** native-CI PASS.
- OWNER real terminal directly returned `vfops --build-id = 0.1.0-release87` and opened the five-option menu: **installed identity and menu opening only**. No release87 MariaDB initialization, MySQL/Percona-to-MariaDB transfer, backup, restore or whole-product functional acceptance proven; no separate System Care rc56 installed readback (`UNKNOWN`).
- **CloudPanel residual security**: release87 suppresses sensitive exception context, but official `clpctl` still places site/database/user passwords in OS-visible process arguments. `PARTIAL_HARDENING / RESIDUAL_ARGV_RISK / NOT_FULL_PASS`. No unverified CLI-interface rewrites.
- All prior release68 Owner 16-site migration PASS and release86 machine PASS remain historical and exact-source scoped. Old VPS retention, manual DNS and separate production data-write authorization remain mandatory.

## Historical Release86 published identity · 2026-10-17

The previously published release86 software was P07 `0.1.0-release86` with System Care `0.1.0-rc55`, tag `p07-v0.1.0-release86-mariadb-1011` and public commit `55ec3edd764e5294044ec05e55d88c564df94a92`. Official formal publication and remote distribution readback [run 38992499359](https://github.com/llhzx2018/core-free-runner-public/actions/runs/38992499359) PASS; full exact-source synthetic 451/451 [run 38992078210](https://github.com/llhzx2018/core-free-runner-public/actions/runs/38992078210) PASS; System Care real-mutation disposable runner [run 38992499233](https://github.com/llhzx2018/core-free-runner-public/actions/runs/38992499233) PASS.

These are **machine and publication** facts only. There is still **no** Owner new-VPS MariaDB 10.11 or MySQL/Percona-to-MariaDB field acceptance. These release86 machine records alone cannot establish an installed Production version; the newer release87 Owner build-id readback is recorded in the Current section above. Source old VPS must remain available.

## Historical release85 evidence · 2026-10-16

Release85 was the prior **published baseline** (product `BUILD_ID=0.1.0-release85`, public Toolbox Slot3, System Care rc54). Its MariaDB 10.11 default installation and target-side migration guard were validated by synthetic machine tests; no real new VPS MySQL/Percona → MariaDB migration has been observed.

The 2026-10-05 **release68** real 16-site migration remains a genuine historical Owner PASS for that exact old-engine environment, not release85 MariaDB compatibility proof.

Round 1 and Round 2 hardening PR #196/#197 were merged before the release86 source candidate #198 was promoted; independent R3 exact-source and formal published-byte checks PASS. None of this changes the Owner Real `NOT_RUN` status.

System Care rc54 real-mutation workflow previously failed because CI expected retired success wording. The corrected **workflow-only** public main change (PR #2757) ran on GitHub-hosted Ubuntu 24.04 and passed [run 38914624486](https://github.com/llhzx2018/core-free-runner-public/actions/runs/38914624486), including real APT cache cleanup, journal cleanup and negative safety gates. This is independent machine evidence, **not** an Owner VPS approval or a new System Care binary release.

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
"release86 MariaDB new-VPS Real PASS"     without an actual MariaDB server run
```

## Current identities

```text
current published build                0.1.0-release87 (product + distributor)
formal release tag                     p07-v0.1.0-release87-security-hardening
system care published package          0.1.0-rc56 / Owner installed UNKNOWN
2026-10-17 Owner build-id              0.1.0-release87 / version-only proof
release87 MariaDB Owner real           NOT_RUN
release87 backup/restore Owner real    NOT_RUN (no current exact-source field proof)
overall P07 Owner real                 PARTIAL / NOT_BLANKET_PASS
```

Historical release68 / release86 exact-source identities and evidence remain in earlier sections; neither proves current release87 migration, backup or restore Real PASS.

## Historical RC1 field result

RC1 remains retired after the earlier Owner field test exposed installation-root, Inventory and beginner-UX defects.

```text
RC1_ENGINEERING_CORE = PASS
RC1_PUBLIC_INSTALL_USER_PATH = FAIL
RC1_USER_ACCEPTANCE = FAIL
RC1_STATUS = RETIRED
```

## Outstanding release87 Owner gates

```text
release87 current installed build ID   OWNER_VERSION_ONLY_PASS
release87 new VPS MariaDB 10.11        NOT_RUN
release87 cross-engine migration       NOT_RUN
release87 backup / restore             NOT_RUN (current exact real proof absent)
System Care rc56 Owner installed       UNKNOWN
CloudPanel credential process argv     RESIDUAL_RISK_NOT_FULL_PASS
full product Owner acceptance          PARTIAL / NOT_BLANKET_PASS
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
