from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = "https://github.com/llhzx2018/vf-seo.git"
BRANCH = "docs/v124-production-closure-20260903"
BASE = "548257ea3d45234ebaafdeab6ab0a164c5c192a9"
RELEASE_SOURCE = "f752c13b44fb624924926a49197ebe9519ec3f28"
RELEASE_TREE = "33c67dedfc25143c9e675c97dec903a8ef1c4134"
FULL_SHA = "f318f75a34c1a7b0f731c0e7ab81e42846cf43aaee1b16ec38f0fd94606741c4"
UPDATE_SHA = "78ef2f2682958769604b999f8edc7ac5bd9091697e2abe8645cf31621182fedd"
WORK = Path("/tmp/vf-seo-v124-closure")


def run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else ""


def replace_first_fenced_block(path: Path, heading: str, body: str) -> None:
    s = path.read_text()
    marker = heading + "\n\n```text\n"
    assert s.count(marker) == 1, (path, s.count(marker))
    start = s.index(marker) + len(marker)
    end = s.index("\n```", start)
    path.write_text(s[:start] + body + s[end:])


subprocess.run(["rm", "-rf", str(WORK)], check=True)
run("git", "clone", "--quiet", REPO, str(WORK))
run("git", "fetch", "--quiet", "origin", BRANCH, cwd=WORK)
run("git", "checkout", "--quiet", "-B", BRANCH, f"origin/{BRANCH}", cwd=WORK)
assert run("git", "rev-parse", "HEAD", cwd=WORK, capture=True) == BASE

readme_truth = """Project: P05 · VF SEO
Repository: llhzx2018/vf-seo
Current Formal Release: v1.2.4 · RELEASED / PRODUCTION CLOSED
Release / Tag Source: f752c13b44fb624924926a49197ebe9519ec3f28
Release Tree: 33c67dedfc25143c9e675c97dec903a8ef1c4134
Production: v1.2.4 · MACHINE_RUNTIME_READBACK_PASS
Production Readback: 33715543004 / 100523841051 · PASS
Production Runtime: PHP 8.4.24 · SQLite · VF-SEO-SCHEMA@1 / 1 · DATABASE READY · PROCESS READY
Production Root / Legacy Bridge: HTTP 200 / legacy bridge 404 · PASS
Atomic Upgrade Gate: 33688237965 / 100440700253 · PASS · v1.2.3 → v1.2.4
Atomic Publication: 33688475774 / 100441463821 · PASS
Online Update Discovery: 33715282219 / 100523053944 · AVAILABLE + VERIFIED
Current Engineering Main: 548257ea3d45234ebaafdeab6ab0a164c5c192a9
Engineering State: UNRELEASED · PR #211 v1.2.5 readability CSS is on main but NOT in v1.2.4 Release/Production
Latest Engineering PR: #211 · MERGED · UNRELEASED
VERSION: 1.2.4
Schema: VF-SEO-SCHEMA@1 / 1
Default Database: SQLite
Next Action: keep v1.2.4 Production frozen; handle v1.2.5 readability release as a separate future closure"""
replace_first_fenced_block(WORK / "README.md", "## Current Truth", readme_truth)

state_truth = """Current Formal Release: v1.2.4 · RELEASED / PRODUCTION CLOSED
Release / Tag Source: f752c13b44fb624924926a49197ebe9519ec3f28
Release Tree: 33c67dedfc25143c9e675c97dec903a8ef1c4134
Formal FULL: VF_SEO_V1.2.4_FULL.zip · Asset 541815708 · 357053 bytes · SHA-256 f318f75a34c1a7b0f731c0e7ab81e42846cf43aaee1b16ec38f0fd94606741c4
Production: v1.2.4 · MACHINE_RUNTIME_READBACK_PASS
Production Machine Readback: 33715543004 / 100523841051 · PASS
Production Runtime: PHP 8.4.24 · SQLite · Schema 1 · DATABASE READY · PROCESS READY
Production Root / Legacy Bridge: HTTP 200 / 404 · PASS
Atomic Upgrade Gate: 33688237965 / 100440700253 · PASS
Atomic UPDATE: VF_SEO_V1.2.4_UPDATE.zip · Asset 541819551 · 789778 bytes · SHA-256 78ef2f2682958769604b999f8edc7ac5bd9091697e2abe8645cf31621182fedd
Atomic Publication: 33688475774 / 100441463821 · PASS
Online Discovery Readback: 33715282219 / 100523053944 · AVAILABLE + VERIFIED
Current Engineering Main: 548257ea3d45234ebaafdeab6ab0a164c5c192a9
Engineering State: MAIN_AHEAD_OF_PRODUCTION · PR #211 v1.2.5 readability CSS merged, UNRELEASED / NOT_DEPLOYED
Schema: VF-SEO-SCHEMA@1 / 1
Release Authorization: NONE_OPEN
Production Authorization: NONE_OPEN
Next Action: V1.2.4_PRODUCTION_CLOSED → future v1.2.5 readability release handled separately"""
replace_first_fenced_block(WORK / "docs/handoff/CURRENT_STATE.md", "# P05 · VF SEO · Current State", state_truth)

p = WORK / "docs/handoff/CURRENT_STATE.md"
s = p.read_text()
anchor = "## Post-release Engineering Current Truth\n"
assert s.count(anchor) == 1
closure_section = """## v1.2.4 Production Closure

Formal v1.2.4 Release is closed at exact Release Source `f752c13b44fb624924926a49197ebe9519ec3f28` / tree `33c67dedfc25143c9e675c97dec903a8ef1c4134`. The deterministic FULL asset is `VF_SEO_V1.2.4_FULL.zip` (asset `541815708`, `357053` bytes, SHA-256 `f318f75a34c1a7b0f731c0e7ab81e42846cf43aaee1b16ec38f0fd94606741c4`). Atomic v1.2.3 → v1.2.4 upgrade Gate `33688237965 / 100440700253` passed actual upgrade, data preservation, idempotence, rollback, interruption recovery, browser single-PHP and reverse-proxy same-origin. Atomic publication `33688475774 / 100441463821` published the sealed UPDATE asset `541819551` (`789778` bytes / SHA-256 `78ef2f2682958769604b999f8edc7ac5bd9091697e2abe8645cf31621182fedd`).

The exact v1.2.3 formal updater client then performed a credentialed online-discovery readback using the established `VF_PRIVATE_READ_TOKEN` path: `33715282219 / 100523053944 · PASS`, returning `AVAILABLE` for v1.2.4 and `VERIFIED` for the real UPDATE package. A separate read-only Production probe `33715543004 / 100523841051 · PASS` read `https://seo.kewaro.com/api/health` as v1.2.4 / Schema 1 / SQLite / PHP 8.4.24 / DATABASE READY / PROCESS READY; root returned HTTP 200 and the retired v1.2.2 bridge returned 404. That probe performed `Production write = 0`. The exact deployment mechanism is not inferred from readback alone.

Engineering `main` is now intentionally ahead at `548257ea3d45234ebaafdeab6ab0a164c5c192a9` because PR #211 merged an Owner-visible readability CSS change intended for future v1.2.5. That CSS is **not** part of the immutable v1.2.4 Release Source and is **not** claimed as deployed. Any older statements below that say Production remains v1.2.3 are historical pre-v1.2.4 engineering notes and are superseded for Release/Production truth by this closure section and `docs/authority/RELEASE_V1.2.4_PRODUCTION_CLOSURE.md`.

"""
p.write_text(s.replace(anchor, closure_section + anchor, 1))

p = WORK / "CHANGELOG.md"
s = p.read_text()
anchor = "# 变更记录\n\n"
assert s.startswith(anchor)
section = """## v1.2.4 · Released / Production Closed（2026-09-03）

- 正式 Release Source=`f752c13b44fb624924926a49197ebe9519ec3f28` / tree=`33c67dedfc25143c9e675c97dec903a8ef1c4134`；FULL asset `541815708`，`357053` bytes，SHA-256 `f318f75a34c1a7b0f731c0e7ab81e42846cf43aaee1b16ec38f0fd94606741c4`。
- v1.2.3 → v1.2.4 Atomic Gate `33688237965 / 100440700253` PASS；UPDATE asset `541819551`，`789778` bytes，SHA-256 `78ef2f2682958769604b999f8edc7ac5bd9091697e2abe8645cf31621182fedd`；Atomic Publication `33688475774 / 100441463821` PASS。
- v1.2.3 正式更新客户端按既有 `VF_PRIVATE_READ_TOKEN` 路径执行 Online Discovery Readback `33715282219 / 100523053944`：v1.2.4=`AVAILABLE`，真实 UPDATE package=`VERIFIED`。
- Production Readback `33715543004 / 100523841051` PASS：线上为 v1.2.4 / Schema 1 / SQLite / PHP 8.4.24，DATABASE/PROCESS 均 READY，根路径 HTTP 200，旧 v1.2.2 bridge=404；本 readback 无 Production 写入。
- PR #211 的 v1.2.5 readability CSS 已进入后续 Engineering main=`548257ea3d45234ebaafdeab6ab0a164c5c192a9`，但不属于 v1.2.4 Release/Production。下方原 `Unreleased` 条目保留发布前工程流水语义，其 Release/Production 状态由本节统一收口。

"""
if "## v1.2.4 · Released / Production Closed" not in s:
    p.write_text(anchor + section + s[len(anchor):])

p = WORK / "VF_PROJECT.json"
data = json.loads(p.read_text())
data.update({
    "status": "V1.2.4_RELEASED_PRODUCTION_CLOSED / MAIN_AHEAD_V1.2.5_READABILITY_ENGINEERING_UNRELEASED",
    "version": "1.2.4",
    "production_version": "1.2.4",
    "target_version": "1.2.4",
    "working_version": "1.2.4",
    "version_change": False,
    "formal_release": "v1.2.4",
    "formal_release_state": "RELEASED_PRODUCTION_MACHINE_READBACK_PASS",
    "formal_release_candidate_commit": "39fd625dcf79a58f7882a57c292568d76066b5a1",
    "formal_release_candidate_tree": RELEASE_TREE,
    "formal_release_asset": "VF_SEO_V1.2.4_FULL.zip",
    "formal_release_asset_files": 70,
    "formal_release_asset_bytes": 357053,
    "formal_release_asset_sha256": FULL_SHA,
    "runtime_recovery_candidate": "V1.2.4_ATOMIC_R1_PASS_CLOSED",
    "runtime_recovery_release": "RELEASED_V1.2.4",
    "production_source_upload": "DEPLOYMENT_METHOD_NOT_ASSERTED / MACHINE_READBACK_CONFIRMED_V1.2.4",
    "production_runtime_acceptance": "MACHINE_HEALTH_READBACK_V1.2.4_PASS / OWNER_OBSERVED_V1.2.4_SCREENSHOT_REFERENCED_BY_PR_211",
    "production_deployment": "DEPLOYED_V1.2.4_MACHINE_READBACK_VERIFIED",
    "working_branch": "main",
    "owner_real_use_review": "V1.2.4_OWNER_OBSERVED_SCREENSHOT_REFERENCED_BY_PR_211 / MACHINE_RUNTIME_READBACK_PASS",
    "owner_real_use_pass": "PASS / MACHINE_RUNTIME_READBACK + OWNER_OBSERVED_REFERENCE",
    "candidate_authorization": "CONSUMED_V1.2.4",
    "release_authorization": "OWNER_AUTHORIZED_V1.2.4 / EXECUTED_CLOSED",
    "production_deployment_authorization": "OBSERVED_V1.2.4_DEPLOYED / NO_NEW_PRODUCTION_WRITE_AUTHORIZED",
    "runtime_evidence": "docs/authority/RELEASE_V1.2.4_PRODUCTION_CLOSURE.md",
    "next_action": "V1.2.4_PRODUCTION_CLOSED / V1.2.5_READABILITY_ENGINEERING_UNRELEASED",
    "deployment_readiness": "V1.2.4_PRODUCTION_CLOSED / V1.2.5_ENGINEERING_UNRELEASED",
    "formal_release_id": 381599672,
    "formal_release_asset_id": 541815708,
})
data["authority"]["release"] = "docs/authority/RELEASE_V1.2.4_PRODUCTION_CLOSURE.md"
data["release_publication"] = {
    "tag": "v1.2.4",
    "release_id": 381599672,
    "release_name": "P05 · VF SEO v1.2.4 · Product Optimization Patch",
    "target_commit": RELEASE_SOURCE,
    "target_tree": RELEASE_TREE,
    "published_at": "2026-09-02T21:59:28Z",
    "full_asset": "VF_SEO_V1.2.4_FULL.zip",
    "full_asset_id": 541815708,
    "full_files": 70,
    "full_bytes": 357053,
    "full_sha256": FULL_SHA,
    "receipt_asset": "VF_SEO_V1.2.4_RELEASE_RECEIPT.txt",
    "receipt_asset_id": 541815710,
    "exact_candidate_source": "39fd625dcf79a58f7882a57c292568d76066b5a1",
    "exact_candidate_run": 33687064306,
    "exact_candidate_job": 100437992318,
    "publication_run": 33688012617,
    "publication_job": 100439992986,
    "state": "PASS_CLOSED",
    "real_endpoint": "MACHINE_READBACK_V1.2.4",
    "production": "DEPLOYED_MACHINE_VERIFIED",
}
data["v1_2_4_production_closure"] = {
    "state": "PASS_CLOSED",
    "release_source": RELEASE_SOURCE,
    "release_tree": RELEASE_TREE,
    "full_asset_id": 541815708,
    "full_asset_bytes": 357053,
    "full_asset_sha256": FULL_SHA,
    "atomic_gate_run": 33688237965,
    "atomic_gate_job": 100440700253,
    "update_asset_id": 541819551,
    "update_asset_bytes": 789778,
    "update_asset_sha256": UPDATE_SHA,
    "atomic_publication_run": 33688475774,
    "atomic_publication_job": 100441463821,
    "online_discovery_run": 33715282219,
    "online_discovery_job": 100523053944,
    "online_discovery": "AVAILABLE_AND_VERIFIED",
    "production_readback_run": 33715543004,
    "production_readback_job": 100523841051,
    "production_version": "1.2.4",
    "schema_version": 1,
    "database_provider": "sqlite",
    "runtime": "php",
    "php_version": "8.4.24",
    "database": "READY",
    "process": "READY",
    "root_http": 200,
    "legacy_bridge_http": 404,
    "production_write": 0,
    "engineering_main_after_closure": BASE,
    "engineering_main_note": "PR #211 v1.2.5 readability CSS merged after v1.2.4 Release Source; unreleased and not claimed deployed",
}
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

closure = WORK / "docs/authority/RELEASE_V1.2.4_PRODUCTION_CLOSURE.md"
assert not closure.exists()
closure.write_text("""# P05 · VF SEO v1.2.4 Production Closure

Status: `RELEASED / PRODUCTION_MACHINE_READBACK_PASS / CLOSED`

## Formal Release Authority

- Release: `v1.2.4`
- Release ID: `381599672`
- Release Source: `f752c13b44fb624924926a49197ebe9519ec3f28`
- Release Tree: `33c67dedfc25143c9e675c97dec903a8ef1c4134`
- Exact clean candidate: `39fd625dcf79a58f7882a57c292568d76066b5a1`
- Candidate Native CI: `33687064306 / 100437992318 · PASS`
- Formal publication: `33688012617 / 100439992986 · PASS`
- FULL: `VF_SEO_V1.2.4_FULL.zip`
- FULL Asset ID: `541815708`
- FULL bytes: `357053`
- FULL SHA-256: `f318f75a34c1a7b0f731c0e7ab81e42846cf43aaee1b16ec38f0fd94606741c4`
- Schema: `VF-SEO-SCHEMA@1 / 1` · no migration

## Atomic Update Authority

- Supported path: `v1.2.3 → v1.2.4` only
- Atomic Gate: `33688237965 / 100440700253 · PASS`
- Verified: actual upgrade, data preservation, idempotence, rollback, hard interruption recovery, browser single-PHP, reverse-proxy HTTPS same-origin
- Atomic Publication: `33688475774 / 100441463821 · PASS`
- UPDATE: `VF_SEO_V1.2.4_UPDATE.zip`
- UPDATE Asset ID: `541819551`
- UPDATE bytes: `789778`
- UPDATE SHA-256: `78ef2f2682958769604b999f8edc7ac5bd9091697e2abe8645cf31621182fedd`
- Repair Asset ID: `541819555`
- Repair SHA-256: `fbcdf51321da52f4f2b268aa305313e466df219213381e87af3bb14bfa06b162`

## Online Discovery Readback

The exact updater client extracted from the sealed v1.2.3 FULL package was executed through its normal credentialed path using the established read-only `VF_PRIVATE_READ_TOKEN`.

- Run / Job: `33715282219 / 100523053944 · PASS`
- Current version: `1.2.3`
- Target: `1.2.4`
- Discovery: `AVAILABLE`
- Real UPDATE package: `VERIFIED`
- Asset identity / bytes / SHA-256: exact match to the v1.2.4 Release
- Production write: `0`

## Production Machine Readback

A separate disposable read-only probe reused the proven v1.2.3 Production health contract. It did not execute an update or any Product mutation.

- Run / Job: `33715543004 / 100523841051 · PASS`
- `https://seo.kewaro.com/api/health` → `version=1.2.4`
- Schema: `1`
- Database provider: `sqlite`
- Runtime: `php`
- PHP: `8.4.24`
- Database: `READY`
- Process: `READY`
- Public root: HTTP `200`
- Retired v1.2.2 bridge: HTTP `404`
- Probe Production write: `0`

This readback proves the observed live runtime is v1.2.4 and healthy. It does **not** infer or fabricate the exact deployment mechanism. PR #211 separately records that an Owner-observed v1.2.4 Production screenshot existed.

## Engineering-main boundary

After the v1.2.4 Release Source was frozen, PR #211 merged one Owner-visible readability CSS change to Engineering `main`, which is now `548257ea3d45234ebaafdeab6ab0a164c5c192a9`. That work is intended for future v1.2.5 and is **not part of v1.2.4 Release Source** and **not claimed as deployed**. PR #212, an attempted v1.2.5 version-lock workflow, safe-failed and closed without merge.

Therefore:

- Formal Release Truth: `v1.2.4`
- Production Truth: `v1.2.4 · CLOSED`
- Engineering main may lead Production.
- Future v1.2.5 release/deployment requires a separate formal closure.
""")

run("python3", "-m", "json.tool", "VF_PROJECT.json", cwd=WORK)
assert (WORK / "VERSION").read_text().strip() == "1.2.4"
run("git", "diff", "--check", cwd=WORK)
changed = run("git", "diff", "--name-only", cwd=WORK, capture=True).splitlines()
expected = sorted([
    "CHANGELOG.md",
    "README.md",
    "VF_PROJECT.json",
    "docs/authority/RELEASE_V1.2.4_PRODUCTION_CLOSURE.md",
    "docs/handoff/CURRENT_STATE.md",
])
assert sorted(changed) == expected, (changed, expected)
assert run("git", "diff", "--name-only", "--", "VERSION", "src/client/product-site-views.css", cwd=WORK, capture=True) == ""
assert "Current Formal Release: v1.2.4 · RELEASED / PRODUCTION CLOSED" in (WORK / "README.md").read_text()
assert "Production Machine Readback: 33715543004 / 100523841051 · PASS" in (WORK / "docs/handoff/CURRENT_STATE.md").read_text()
assert json.loads((WORK / "VF_PROJECT.json").read_text())["production_version"] == "1.2.4"
assert "PR #211" in closure.read_text()

run("git", "config", "user.name", "VictorForge", cwd=WORK)
run("git", "config", "user.email", "llhzx2018@gmail.com", cwd=WORK)
run("git", "add", *expected, cwd=WORK)
run("git", "commit", "-m", "docs: close v1.2.4 Production truth", cwd=WORK)
run("git", "push", "--quiet", "origin", f"HEAD:{BRANCH}", cwd=WORK)
print("P05_V124_CLOSURE_DOCS_HEAD=" + run("git", "rev-parse", "HEAD", cwd=WORK, capture=True))
print("P05_V124_CLOSURE_DOCS_FILES=5")
print("P05_V124_CLOSURE_DOCS_BUILD=PASS")
print("P05_PRODUCTION_WRITE=0")
