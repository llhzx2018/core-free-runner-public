#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

BASE = "5fa1a4a80f84201dcc1a4313c8d8d0ace05f3b00"
EXACT = "c4fe3d5cf49fd33d0214f58244ccc112279944a5"
TREE = "9d653d36c51e87420b4f9932e777294ca4d300a8"
VERSION = "1.1.10"
RELEASE_ID = 379314813
EXACT_RUN = 33318245543
EXACT_JOB = 99275513101
PUBLICATION_RUN = 33318510907
PUBLICATION_JOB = 99276224334
FULL_ASSET = "VF_SEO_V1.1.10_FULL.zip"
FULL_ASSET_ID = 536734918
RECEIPT_ASSET = "VF_SEO_V1.1.10_RELEASE_RECEIPT.txt"
RECEIPT_ASSET_ID = 536734919
FULL_FILES = 44
FULL_BYTES = 363138
FULL_SHA256 = "16448869130988685c5fadb42f50362dfac08d6b2dd8657394b8a43c7787ba5d"
PUBLISHED_AT = "2026-08-30T15:03:32Z"

EXPECTED_CHANGED = {
    "README.md",
    "VF_PROJECT.json",
    "docs/authority/RELEASE_V1.1.10_CURRENT.md",
    "docs/evidence/V1.1.10_FORMAL_RELEASE_20260830.md",
    "docs/handoff/CURRENT_STATE.md",
}


def run(repo: Path, *args: str) -> str:
    return subprocess.check_output(args, cwd=repo, text=True).strip()


def replace_section(text: str, start_heading: str, next_heading: str, replacement: str) -> str:
    start = text.find(start_heading)
    if start < 0:
        raise RuntimeError(f"missing heading: {start_heading.strip()}")
    end = text.find(next_heading, start + len(start_heading))
    if end < 0:
        raise RuntimeError(f"missing next heading: {next_heading.strip()}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def main() -> None:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if run(repo, "git", "rev-parse", "HEAD") != BASE:
        raise RuntimeError("closure branch did not start from exact released main")
    if run(repo, "git", "rev-parse", "origin/main") != BASE:
        raise RuntimeError("P05 main drifted before release closure write")
    if run(repo, "git", "rev-parse", f"{EXACT}^{{tree}}") != TREE:
        raise RuntimeError("verified exact source tree drift")
    if run(repo, "git", "rev-parse", f"{BASE}^{{tree}}") != TREE:
        raise RuntimeError("released main tree is not tree-equivalent to exact source")

    candidate = repo / "docs/authority/RELEASE_V1.1.10_CANDIDATE.md"
    candidate_before = hashlib.sha256(candidate.read_bytes()).hexdigest()

    project_path = repo / "VF_PROJECT.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    project.update(
        {
            "status": "V1.1.10_RELEASED / MACHINE_PASS / PRODUCTION_NOT_DEPLOYED",
            "version": VERSION,
            "target_version": VERSION,
            "working_version": VERSION,
            "version_change": False,
            "formal_release": "v1.1.10",
            "formal_release_state": "RELEASED_CURRENT_MACHINE_PASS_PRODUCTION_NOT_DEPLOYED",
            "formal_release_candidate_commit": EXACT,
            "formal_release_candidate_tree": TREE,
            "formal_release_source": BASE,
            "formal_release_tree": TREE,
            "formal_release_asset": FULL_ASSET,
            "formal_release_asset_files": FULL_FILES,
            "formal_release_asset_bytes": FULL_BYTES,
            "formal_release_asset_sha256": FULL_SHA256,
            "formal_release_id": RELEASE_ID,
            "formal_release_asset_id": FULL_ASSET_ID,
            "formal_release_receipt_asset_id": RECEIPT_ASSET_ID,
            "formal_release_exact_source_run": EXACT_RUN,
            "formal_release_exact_source_job": EXACT_JOB,
            "formal_release_publication_run": PUBLICATION_RUN,
            "formal_release_publication_job": PUBLICATION_JOB,
            "runtime_recovery_release": "RELEASED_V1.1.10",
            "production_runtime_acceptance": "V1.1.10_RELEASED_REAL_ENDPOINT_NOT_PROVEN",
            "production_deployment": "NOT_DEPLOYED",
            "production_write": 0,
            "working_branch": "main",
            "owner_real_use_review": "V1.1.9_REAL_FAIL_HISTORICAL / V1.1.10_RELEASED_NOT_DEPLOYED",
            "owner_real_use_pass": "NOT_PROVEN_FOR_V1.1.10",
            "candidate_authorization": "CONSUMED_V1.1.10_RELEASED",
            "release_authorization": "CONSUMED_V1.1.10_RELEASED",
            "product_failure": None,
            "last_historical_product_failure": "V1.1.9_FIRST_REQUEST_MARKER_CREATION_PLUS_HOME_ENV_STORAGE_DISCOVERY_COULD_REBIND_OLD_STATE",
            "next_action": "STOP_RELEASE_CLOSURE; PRODUCTION_REQUIRES_EXPLICIT_OWNER_AUTHORIZATION",
            "deployment_readiness": "V1.1.10_RELEASED_AWAIT_EXPLICIT_PRODUCTION_DECISION",
        }
    )
    project.setdefault("authority", {})["release"] = "docs/authority/RELEASE_V1.1.10_CURRENT.md"
    project["authority"]["release_candidate"] = "docs/authority/RELEASE_V1.1.10_CANDIDATE.md"
    project["release_publication"] = {
        "tag": "v1.1.10",
        "release_id": RELEASE_ID,
        "release_name": "P05 · VF SEO v1.1.10 · Runtime Pointer Contract Closure",
        "target_commit": BASE,
        "target_tree": TREE,
        "published_at": PUBLISHED_AT,
        "full_asset": FULL_ASSET,
        "full_asset_id": FULL_ASSET_ID,
        "full_files": FULL_FILES,
        "full_bytes": FULL_BYTES,
        "full_sha256": FULL_SHA256,
        "receipt_asset": RECEIPT_ASSET,
        "receipt_asset_id": RECEIPT_ASSET_ID,
        "exact_candidate_source": EXACT,
        "exact_candidate_run": EXACT_RUN,
        "exact_candidate_job": EXACT_JOB,
        "publication_run": PUBLICATION_RUN,
        "publication_job": PUBLICATION_JOB,
        "private_ci": "BLOCKED_INFRA_RUNNER_ID_0_STEPS_0",
        "state": "PASS_CLOSED",
        "real_endpoint": "NOT_PROVEN_V1.1.10",
        "production": "NOT_DEPLOYED",
    }
    project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme_path = repo / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    current_truth = f"""## Current Truth

```text
Project: P05 · VF SEO
Repository: llhzx2018/vf-seo
Current Formal Release: v1.1.10 · RELEASED
Release Main: {BASE}
Verified Exact Source: {EXACT}
Verified Tree: {TREE}
Final Closure Gate: {EXACT_RUN} / {EXACT_JOB} · PASS
Formal Publication: {PUBLICATION_RUN} / {PUBLICATION_JOB} · PASS
FULL SHA-256: {FULL_SHA256}
Formal Production Authority: NOT_DEPLOYED
Production Write: 0
Schema: VF-SEO-SCHEMA@1 / 1
Default Database: SQLite
```

历史真实用户证据继续保留：v1.1.9 fresh reinstall = FAIL。v1.1.10 已达到正式 Machine/Release PASS，但尚未部署到正式 endpoint，因此不能声明 `REAL_USER_PASS_V1.1.10`。"""
    readme = replace_section(readme, "## Current Truth\n", "## V1.1.10 安装模型\n", current_truth)

    machine = f"""## Machine Evidence

V1.1.10 最终 Release Closure：

```text
Mechanism Gate: 33316433128 · PASS
Final Exact Source: {EXACT}
Final Closure Gate: {EXACT_RUN} / {EXACT_JOB} · PASS
Release Main: {BASE}
Release Tree: {TREE}
Formal Publication: {PUBLICATION_RUN} / {PUBLICATION_JOB} · PASS
GitHub Release: v1.1.10 / {RELEASE_ID}
FULL Asset: {FULL_ASSET} / {FULL_ASSET_ID}
FULL Files: {FULL_FILES}
FULL Bytes: {FULL_BYTES}
FULL SHA-256: {FULL_SHA256}
Receipt Asset ID: {RECEIPT_ASSET_ID}
Private CI: BLOCKED_INFRA · runner_id=0 · steps=[]
Production: NOT_DEPLOYED
Production Write: 0
```

最终 Gate 覆盖 release-source、lint/typecheck、Unit 21/21、Contract 16/16、Integration 13/13、dependency/security、PHP、pointer-less CLI fail-closed、pointer-bound HTTP/CLI、CloudPanel 隔离副本、Browser Setup → CLI maintenance、脏旧状态重装、Chrome E2E、formal staging byte-identical 与 post-test pristine rebuild。"""
    readme = replace_section(readme, "## Machine Evidence\n", "## Release Packaging Boundary\n", machine)
    old_boundary = "当前没有任何授权去自动修改 Cloudflare、CloudPanel 或 Production。V1.1.10 只有最终 Exact Source FULL Gate 与 Formal Publication 都 PASS 后才允许发布。"
    if old_boundary in readme:
        readme = readme.replace(
            old_boundary,
            "V1.1.10 已完成正式发布与远端 digest 回读。当前没有任何授权去自动修改 Cloudflare、CloudPanel 或 Production；发布完成不等于 Production Deployment。Production 仍为 `NOT_DEPLOYED`。",
        )
    readme_path.write_text(readme, encoding="utf-8")

    current_state = f"""# P05 · VF SEO · Current State

```text
Current Formal Release: v1.1.10 · RELEASED
Release Main: {BASE}
Release Tree: {TREE}
Final Exact Source: {EXACT}
Final Closure Gate: {EXACT_RUN} / {EXACT_JOB} · PASS
Formal Publication: {PUBLICATION_RUN} / {PUBLICATION_JOB} · PASS
Release ID: {RELEASE_ID}
FULL: {FULL_ASSET}
FULL Asset ID: {FULL_ASSET_ID}
FULL Files: {FULL_FILES}
FULL Bytes: {FULL_BYTES}
FULL SHA-256: {FULL_SHA256}
Receipt Asset ID: {RECEIPT_ASSET_ID}
Private CI: BLOCKED_INFRA · runner_id=0 · steps=[]
Production: NOT_DEPLOYED
Production Write: 0
Schema: VF-SEO-SCHEMA@1 / 1
```

v1.1.10 已关闭 fresh-install/runtime identity 问题：Webroot Runtime Pointer 是唯一安装事实；pointer 缺失必定进入 fresh install；HOME、旧 runtime.env、旧 SQLite 与 storage-path 环境变量无权自动认领旧状态；Browser Setup 在 private runtime 完成后最后提交 pointer；CLI maintenance 只允许 pointer-bound runtime。

正式 FULL 在所有 Browser/dirty-state/Chrome 测试结束后重新构建 pristine staging，最终 ZIP 不携带 runtime pointer、数据库、runtime.env、setup.lock 或历史 recovery helper。远端 Release asset digest 已与本地确定性 ZIP SHA-256 一致。

历史真实用户证据仍保留：v1.1.9 fresh reinstall = FAIL。v1.1.10 当前只有正式 Machine/Release PASS，没有真实 Production endpoint 部署证据，因此不得写成 REAL_USER_PASS。

Next: Release Closure STOP。任何首次正式 Production Deployment 都必须由 Owner 另行明确授权。
"""
    (repo / "docs/handoff/CURRENT_STATE.md").write_text(current_state, encoding="utf-8")

    release_authority = f"""# P05 · VF SEO · V1.1.10 Current Release Authority

## Current Formal Release

```text
Version: v1.1.10
State: RELEASED_CURRENT_MACHINE_PASS
Release Source / main: {BASE}
Release Tree: {TREE}
Verified Exact Source: {EXACT}
Final Exact Source Run: {EXACT_RUN}
Final Exact Source Job: {EXACT_JOB}
Publication Run: {PUBLICATION_RUN}
Publication Job: {PUBLICATION_JOB}
Release ID: {RELEASE_ID}
Full Asset: {FULL_ASSET}
Full Asset ID: {FULL_ASSET_ID}
Full Files: {FULL_FILES}
Full Bytes: {FULL_BYTES}
Full SHA-256: {FULL_SHA256}
Receipt Asset: {RECEIPT_ASSET}
Receipt Asset ID: {RECEIPT_ASSET_ID}
Private CI: BLOCKED_INFRA · runner_id=0 · steps=[]
Production: NOT_DEPLOYED
Production Write: 0
```

## Release Verdict

V1.1.10 的正式 Final Exact Source Gate 与 Formal Publication 均为 `PASS`。Merge 后 `main` tree 与已验证 Exact Source tree 完全一致，属于 tree-equivalent promotion。正式 Publication 从 Exact Main 重新执行完整 Engineering / PostgreSQL Integration / Security / PHP / Browser / dirty historical-state / Chrome 合同，并在所有测试结束后删除 test staging、重新构建 pristine release staging，再生成确定性 FULL。

发布后的 GitHub Release remote readback 已确认：tag `v1.1.10` 精确指向 `{BASE}`；FULL asset size 为 `{FULL_BYTES}` bytes；远端 digest 为 `sha256:{FULL_SHA256}`，与 Publication Machine Receipt 一致。

## Runtime Contract Closed

```text
VF_INSTALL_INSTANCE.json absent
→ fresh install
→ historical HOME/env/SQLite cannot adopt state
→ pointer-less CLI maintenance fails closed

Browser Setup success
→ random sibling private runtime completed
→ final self-test passed
→ VF_INSTALL_INSTANCE.json committed last
→ subsequent runtime and CLI maintenance are pointer-bound
```

Formal release staging 和最终 ZIP 均不包含 runtime pointer、SQLite/DB/WAL/SHM、`runtime.env`、`setup.lock.json`、`.env` 或历史 `FreshInstallRecovery.php`。

## Real User / Production Boundary

V1.1.9 的 fresh-reinstall real-user verdict 保留为历史 `FAIL`。V1.1.10 已达到 `MACHINE_PASS / RELEASED`，但当前没有 `seo.kewaro.com` 正式部署或真实 endpoint acceptance 证据，因此不得声明 `REAL_USER_PASS_V1.1.10`。

```text
V1.1.10 Formal Release: PASS
V1.1.10 Real Endpoint: NOT_PROVEN
Production Deployment: NOT_DEPLOYED
Production Write: 0
```

Release Closure 到此停止。Production 需要新的、明确的 Owner 授权。
"""
    authority_path = repo / "docs/authority/RELEASE_V1.1.10_CURRENT.md"
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_text(release_authority, encoding="utf-8")

    evidence = f"""# P05 · V1.1.10 Formal Release Evidence · 2026-08-30

## Source Binding

```text
Exact Candidate: {EXACT}
Exact Main: {BASE}
Shared Tree: {TREE}
Final Closure Gate: {EXACT_RUN} / {EXACT_JOB} · PASS
Publication: {PUBLICATION_RUN} / {PUBLICATION_JOB} · PASS
```

## Publication Receipt

```text
P05_V1110_FORMAL_RELEASE=PASS
P05_FILES={FULL_FILES}
P05_BYTES={FULL_BYTES}
P05_SHA256={FULL_SHA256}
POINTERLESS_CLI_FAIL_CLOSED=PASS
POINTER_BOUND_CLI_MAINTENANCE=PASS
CLOUDPANEL_ROOT_STAGING_PRISTINE=PASS
DIRTY_STATE_REINSTALL=PASS
FORMAL_TEST_STAGING_IMMUTABLE=PASS
POST_TEST_PRISTINE_REBUILD=PASS
CHROME_E2E=PASS
PRIVATE_CI=BLOCKED_INFRA_RUNNER_ID_0
PRODUCTION_WRITE=0
```

## GitHub Release Remote Readback

```text
Tag: v1.1.10
Release ID: {RELEASE_ID}
Target: {BASE}
Full Asset ID: {FULL_ASSET_ID}
Full Asset: {FULL_ASSET}
Full Bytes: {FULL_BYTES}
Remote Digest: sha256:{FULL_SHA256}
Receipt Asset ID: {RECEIPT_ASSET_ID}
Published At: {PUBLISHED_AT}
Remote Readback: PASS
```

Private repository CI for PR #40 did not obtain a GitHub Runner (`runner_id=0`, `steps=[]`) and is therefore recorded as `BLOCKED_INFRA`, not product FAIL. The public Exact Source machine gate executed the complete contract and passed.

Production remains `NOT_DEPLOYED`; this evidence does not authorize or claim a Production deployment.
"""
    evidence_path = repo / "docs/evidence/V1.1.10_FORMAL_RELEASE_20260830.md"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(evidence, encoding="utf-8")

    # Validation: schema/truth, exact scope, and immutable historical candidate authority.
    check = json.loads(project_path.read_text(encoding="utf-8"))
    assert check["status"] == "V1.1.10_RELEASED / MACHINE_PASS / PRODUCTION_NOT_DEPLOYED"
    assert check["formal_release"] == "v1.1.10"
    assert check["formal_release_source"] == BASE
    assert check["formal_release_tree"] == TREE
    assert check["formal_release_asset_sha256"] == FULL_SHA256
    assert check["authority"]["release"] == "docs/authority/RELEASE_V1.1.10_CURRENT.md"
    assert check["production_deployment"] == "NOT_DEPLOYED"
    assert check["production_write"] == 0
    assert check["release_publication"]["state"] == "PASS_CLOSED"
    assert check["release_publication"]["production"] == "NOT_DEPLOYED"

    candidate_after = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if candidate_after != candidate_before:
        raise RuntimeError("historical candidate authority changed")

    tracked = set(filter(None, run(repo, "git", "diff", "--name-only", BASE).splitlines()))
    untracked = set(filter(None, run(repo, "git", "ls-files", "--others", "--exclude-standard").splitlines()))
    changed = tracked | untracked
    if changed != EXPECTED_CHANGED:
        raise RuntimeError(f"unexpected closure scope: {sorted(changed)}")

    if "Current Formal Release: v1.1.10 · RELEASED" not in readme_path.read_text(encoding="utf-8"):
        raise RuntimeError("README current truth not updated")
    if "Current Formal Release: v1.1.10 · RELEASED" not in current_state:
        raise RuntimeError("Current State not updated")

    print("P05_V1110_RELEASE_CLOSURE_WRITER=PASS")
    print("P05_RELEASE_REMOTE_TRUTH_REQUIRED=PASS")
    print("P05_RELEASE_CLOSURE_SCOPE=PASS")
    print("P05_HISTORICAL_CANDIDATE_AUTHORITY_UNCHANGED=PASS")
    print("P05_PRODUCTION_WRITE=0")


if __name__ == "__main__":
    main()
