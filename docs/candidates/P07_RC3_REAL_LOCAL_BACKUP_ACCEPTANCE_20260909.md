# P07 · VF Server Ops RC3 — guided-init7 Real Local Backup Acceptance

Date: 2026-09-09 / 2026-09-10 UTC
Scope: Slot 3 · CloudPanel backup / restore / migration
Build: `0.1.0-rc3-guided-init7`
Public release commit: `b45880df7803450144943fcbff192936715a4d5b`

## Classification

This record contains **Real VPS / Real User** evidence. It must not be confused with Machine/GitHub/Runner PASS.

Current Slot 3 overall status remains **TESTING / PARTIAL REAL PASS**.

## Real environment observed

- OS: Debian GNU/Linux 13 (trixie)
- CloudPanel CLI: 6.0.8
- CloudPanel sites: 44
- MySQL databases: 34
- SQLite files: 43
- Test site: `www.123.com`
- Test-site DB shape: MySQL=1, SQLite=0

No credential value, OAuth secret, Recovery Key, database password, or private application configuration is recorded here.

## A. Toolbox upgrade to guided-init7

The ordinary permanent Toolbox entry was used. On choosing Slot 3, the installed RC3 was upgraded through the normal distribution chain. The installer completed its pre-install checks, installation, post-install checks, and entered the CloudPanel Ops menu.

Result: **REAL TOOLBOX UPGRADE PASS**.

Safety statements shown by the product included:

- CloudPanel scheduled jobs are not modified.
- DNS is not automatically changed.
- The old/source server is not automatically deleted.

## B. Real local backup — `www.123.com`

The user selected:

`P07 Toolbox -> 3. CloudPanel backup/restore/migration -> 2. Backup website -> www.123.com`

Observed result:

- backup completed successfully;
- backup id: `www.123.com_20260910T042037Z`;
- reported size: `34M`;
- product status: verified and recoverable;
- local path: `/var/backups/vf-server-ops/www.123.com_20260910T042037Z`;
- remote copy: not configured.

Result: **REAL LOCAL MYSQL SITE BACKUP PASS**.

This closes the prior guided-init6 defect in which the same site failed at `DATABASE / UNCLASSIFIED_FAILURE` because current CloudPanel v2 database metadata does not provide portable DB username/password columns.

## C. Restore-plan validation

The newly created `www.123.com` backup appeared in the recoverable-backup list. The product executed restore preflight without writes and returned:

`恢复前检查：PASS`

Result: **REAL BACKUP RESTORE-PLAN PASS**.

This proves the package passed the product's restore-plan gate. It does **not** prove a full restore to a fresh target.

## D. Same-host / same-domain overwrite protection

The user then deliberately continued restore on the SOURCE where `www.123.com` already exists.

The apply phase stopped with:

- stage: `RESTORE`
- blocker: `TARGET_STATE_CONFLICT`
- user message: target already has conflicting site/files; P07 stopped writing.

The product also stated that the original site and existing data were not deleted.

Result: **REAL SAME-DOMAIN OVERWRITE GUARD PASS**.

This is expected fail-closed behavior, not a restore failure that should be fixed.

## What is now closed

- guided-init7 ordinary Toolbox distribution to the Real VPS: PASS.
- current CloudPanel schema compatibility for the tested real MySQL site: PASS.
- local backup creation and verification for `www.123.com`: PASS.
- backup visibility in recoverable inventory: PASS.
- restore-plan preflight for that package: PASS.
- same-domain overwrite refusal on an existing target: PASS.
- SOURCE retention on the refusal path: PASS.

## What remains open

The following must remain OPEN and must not be promoted from Machine evidence:

- Fresh Google Device OAuth + B2 setup on the real VPS.
- Recovery Key real TTY flow.
- real Local + Google + B2 first verification for the current complete CloudPanel site set.
- guarded Scheduler enable only after the first dual-remote verification passes.
- final scheduler/status readback.
- successful restore to a genuinely fresh CloudPanel target.
- successful cross-VPS migration to a target with no same-domain site.

## Safety boundaries still in force

- Do not change DNS automatically.
- Do not delete SOURCE.
- Do not overwrite an existing same-domain TARGET site.
- Do not modify foreign/CloudPanel Cron; P07 owns only `/etc/cron.d/vf-server-ops-auto-backup`.
- Collision, busy, ambiguous, or stale verification state must fail closed.
- Do not store or publish secrets in Git, docs, evidence, or normal logs.
- Ordinary users continue to use only the permanent P07 Toolbox entry.

## Current decision

`REAL_LOCAL_BACKUP = PASS`

`REAL_RESTORE_PLAN = PASS`

`REAL_SAME_DOMAIN_OVERWRITE_GUARD = PASS`

`REAL_DUAL_REMOTE = NOT_RUN`

`REAL_GUARDED_SCHEDULER = NOT_RUN`

`REAL_FRESH_TARGET_RESTORE = NOT_RUN`

`REAL_CROSS_VPS_MIGRATION = NOT_RUN`

`SLOT3 = TESTING / PARTIAL_REAL_PASS`
