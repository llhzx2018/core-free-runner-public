#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = "llhzx2018/vf-start"
BRANCH = "release/v2.38.0-authority-sync-20260902"
START = "44a13c13585e82c2061657e78d06055f0879a60f"
VERSION = "2.38.0"
PUBLISHED = "2.37.5"
OWNER_PROD = "2.37.4"
SCHEMA = "2026082901"
CANDIDATE = "869178a4c8144a0760ea489936c4bde5efa989d2"
READINESS = "33619802724"
FORMAL = START
BIND = "33620070855"
PRODUCT_MAIN = "00216560e47a6b8e629ee8b03f63462d02d18c7b"
BEGIN = "<!-- V2380-AUTHORITY:BEGIN -->"
END = "<!-- V2380-AUTHORITY:END -->"
EXISTING = [
    "CHANGELOG.md",
    "README.md",
    "VF_PROJECT.json",
    "docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md",
    "docs/authority/ACCEPTANCE_MATRIX.md",
    "docs/authority/CURRENT.md",
    "docs/authority/RPD.md",
    "docs/authority/SSOT.md",
]
NEW_ADR = "docs/decisions/ADR-20260902-projects-workspace.md"
EXPECTED = sorted(EXISTING + [NEW_ADR])
ROOT = Path("/tmp/p01-v2380-authority")


def run(args: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(args, input=input_text, text=True, capture_output=True)
    if check and cp.returncode != 0:
        print(cp.stdout, file=sys.stderr)
        print(cp.stderr, file=sys.stderr)
        raise SystemExit(cp.returncode or 1)
    return cp


def gh(endpoint: str, *, method: str = "GET", payload: dict | None = None) -> object:
    args = ["gh", "api"]
    if method != "GET":
        args += ["-X", method]
    args.append(endpoint)
    if payload is None:
        cp = run(args)
    else:
        cp = run(args + ["--input", "-"], input_text=json.dumps(payload, ensure_ascii=False))
    return json.loads(cp.stdout)


def gh_exists(endpoint: str) -> bool:
    return run(["gh", "api", endpoint], check=False).returncode == 0


def get_content(path: str, ref: str) -> str:
    obj = gh(f"repos/{REPO}/contents/{path}?ref={ref}")
    assert isinstance(obj, dict)
    return base64.b64decode(obj["content"]).decode("utf-8")


def replace_block(text: str, body: str) -> str:
    text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n*", "", text, flags=re.S)
    block = f"{BEGIN}\n{body.strip()}\n{END}\n\n"
    lines = text.splitlines(True)
    if lines and lines[0].startswith("# "):
        return lines[0] + "\n" + block + "".join(lines[1:]).lstrip("\n")
    return block + text.lstrip("\n")


def common_block() -> str:
    return f"""## V2.38.0 · Projects Workspace Release Candidate

- 状态：`FORMAL RELEASE PREPARATION / NOT PUBLISHED`
- Published Latest：`V{PUBLISHED}`
- Owner Production Observed：`V{OWNER_PROD}`
- R2 Candidate：`{CANDIDATE}` / Candidate Readiness `{READINESS}` = `PASS`
- R2 Formal Source：`{FORMAL}` / Formal Bind `{BIND}` = `PASS`
- 版本围栏：root `VERSION` = runtime `src/VERSION.txt` = `{VERSION}`
- Schema：`{SCHEMA}` / Migration：`NONE`
- `v2.38.0` Tag / GitHub Release / core-updates / Production：`NOT_RUN`

本次把原独立 `kewaro` 项目入口职责并入 P01 的登录后「项目」工作区。「项目」是个人系统/项目入口，不是新的 URL Resource Domain，不增加第二套数据 Authority。P01/P02/P04/P05 保持当前项目入口；P03/P06 只显示 `RETIRED` 历史状态，不恢复旧项目路由。旧 `kewaro` 仓只能在 V2.38.0 上线且 Owner 实际确认导航与页面后，另行获得 destructive approval 才能删除。"""


def build_files() -> dict[str, str]:
    ROOT.mkdir(parents=True, exist_ok=True)
    files = {p: get_content(p, START) for p in EXISTING}
    common = common_block()
    files["README.md"] = replace_block(files["README.md"], common)
    files["docs/authority/CURRENT.md"] = replace_block(
        files["docs/authority/CURRENT.md"],
        common + "\n\n### Current Next Action\n\n构建 deterministic Formal Artifact 与 Strict Fresh。全部 PASS 后停在 Formal Release Owner Gate，不提前创建 Tag/Release。",
    )
    files["docs/authority/RPD.md"] = replace_block(
        files["docs/authority/RPD.md"],
        common + "\n\n### Product Shape Addendum\n\n登录后顶级导航为 `首页 / 导航 / 频道 / 影视 / 专题 / 项目 / 退出`。其中「项目」只聚合个人系统入口与状态；它不写入 `links`、不增加 Resource Domain Profile、不改变导航/频道/影视/专题四个内容域的数据模型。",
    )
    files["docs/authority/SSOT.md"] = replace_block(
        files["docs/authority/SSOT.md"],
        common + "\n\n### SSOT Addendum\n\n`src/projects.php` 是 authenticated presentation/workspace entry。项目清单当前由该页面的受控配置呈现；不新增 SQLite 表、不复制 URL Identity、不改变 `links` / `resource_domain_profiles` / privacy authority。P03/P06 不得成为 active route。",
    )
    files["docs/authority/ACCEPTANCE_MATRIX.md"] = replace_block(
        files["docs/authority/ACCEPTANCE_MATRIX.md"],
        common + f"""

### V2.38.0 Acceptance Addendum

- [x] 登录后导航顺序为 `首页 → 导航 → 频道 → 影视 → 专题 → 项目 → 退出`。
- [x] 匿名访问 `projects.php` 重定向到登录入口。
- [x] P01/P02/P04/P05 为当前入口；P03/P06 仅 RETIRED。
- [x] 390px viewport 无 document horizontal overflow。
- [x] Schema / Migration 不变。
- [x] R2 Candidate Readiness `{READINESS}` PASS。
- [x] R2 Formal Bind `{BIND}` PASS。
- [ ] Formal Artifact。
- [ ] Strict Fresh。
- [ ] Formal Release Owner approval。
- [ ] Owner Production verification。""",
    )
    files["docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md"] = replace_block(
        files["docs/architecture/P01_MULTI_SURFACE_ARCHITECTURE.md"],
        common + "\n\n### Projects Workspace Architecture Addendum\n\n`projects.php` 位于现有 authenticated P01 shell 内，复用相同 Session、安全 Header、Sidebar、Theme 与全局导航。它是 portfolio/workspace presentation，不建立新数据库或第二前端 Authority。外部 P02/P04/P05 入口使用受控外链；P01 回到本地 Home；P03/P06 仅保留退役说明。",
    )

    heading = "## V2.38.0 · Projects Workspace Release Candidate · 2026-09-02"
    if heading not in files["CHANGELOG.md"]:
        entry = f"""{heading}

- 原独立 `kewaro` 项目索引职责并入 P01，新增登录后 `projects.php` 与顶部「项目」入口。
- 顶级导航：`首页 / 导航 / 频道 / 影视 / 专题 / 项目 / 退出`。
- P01/P02/P04/P05 保留为当前项目；P03/P06 仅 RETIRED，不恢复旧路由。
- `项目` 是 portfolio/workspace presentation，不新增 Resource Domain、SQLite 表、URL Identity 或 Privacy Authority。
- root/runtime 双版本围栏均为 `2.38.0`；Schema `{SCHEMA}` 不变，无 Migration。
- Candidate Readiness `{READINESS}` PASS；Formal Bind `{BIND}` PASS；Formal Artifact / Strict Fresh / Formal Release 尚未执行。

"""
        files["CHANGELOG.md"] = entry + files["CHANGELOG.md"]

    files[NEW_ADR] = f"""# ADR · 2026-09-02 · Kewaro Project Index Consolidation into P01

## Status

`ACCEPTED / RELEASE CANDIDATE V2.38.0`

## Decision

把原独立 `kewaro` 静态项目入口职责并入 P01，作为登录后的「项目」工作区。P01/P02/P04/P05 保持当前入口；P03/P06 仅展示 RETIRED 历史状态。

## Architectural Boundary

- 不新增数据库表、URL Identity、Resource Domain 或 Privacy Authority。
- `projects.php` 复用 P01 当前认证、安全 Header、Shell、Theme 与导航。
- `项目` 是 portfolio/workspace presentation，不是第五个内容资源域。
- Kewaro 独立仓在 V2.38.0 Production 实际验证前不得删除；删除仍需单独 destructive approval。

## Evidence

- Product PR `#224` merged to main as `{PRODUCT_MAIN}`.
- R2 Candidate `{CANDIDATE}` / Readiness `{READINESS}` PASS.
- R2 Formal Source `{FORMAL}` / Formal Bind `{BIND}` PASS.
- Schema `{SCHEMA}` / Migration `NONE`.
"""

    data = json.loads(files["VF_PROJECT.json"])
    data.update({
        "status": "V2.37.4 OWNER PRODUCTION OBSERVED / V2.37.5 PUBLISHED / V2.38.0 PROJECTS RELEASE CANDIDATE",
        "production_version": OWNER_PROD,
        "working_version": VERSION,
        "target_release_version": VERSION,
        "current_phase": "V2.38.0 PROJECTS WORKSPACE / FORMAL RELEASE PREPARATION",
        "candidate_version": VERSION,
        "candidate_schema_version": SCHEMA,
        "candidate_state": "V2.38.0 R2 CANDIDATE READINESS + FORMAL BIND PASS / NOT PUBLISHED",
        "formal_release_state": "V2.38.0 PRE-RELEASE GATES IN PROGRESS / NOT PUBLISHED",
        "current_authority": "Owner Production V2.37.4 OBSERVED / Published Latest V2.37.5 / V2.38.0 Projects Candidate",
        "next_action": "Build deterministic V2.38.0 Formal Artifact and Strict Fresh; request explicit Owner Formal Release approval only after PASS.",
    })
    authority = data.get("authority") if isinstance(data.get("authority"), dict) else {}
    data["authority"] = authority
    authority["current_formal_release_evidence"] = "docs/evidence/P01_V2.38.0_FORMAL_BIND_R2_20260902.md"
    data["current_change"] = {
        "change_id": "P01-V2380-PROJECTS-WORKSPACE-20260902",
        "type": "MINOR FEATURE / PROJECTS WORKSPACE + KEWARO CONSOLIDATION",
        "published_base_version": PUBLISHED,
        "product_main_merge": PRODUCT_MAIN,
        "r2_candidate_source": CANDIDATE,
        "r2_candidate_readiness_run": int(READINESS),
        "r2_candidate_readiness": "PASS",
        "r2_formal_source": FORMAL,
        "r2_formal_bind_run": int(BIND),
        "r2_formal_bind": "PASS",
        "schema_change": False,
        "migration": None,
        "version_change": True,
        "release_authorized_by_owner": False,
        "main_write": False,
        "production_write": False,
        "runner_main_write": False,
        "release_completed": False,
    }
    data["v2_38_0_release_candidate"] = {
        "version": VERSION,
        "source_version": PUBLISHED,
        "schema_version": SCHEMA,
        "candidate_source": CANDIDATE,
        "candidate_readiness_run": int(READINESS),
        "candidate_readiness": "PASS",
        "formal_source": FORMAL,
        "formal_bind_run": int(BIND),
        "formal_bind": "PASS",
        "formal_artifact": "NOT_RUN",
        "strict_fresh": "NOT_RUN",
        "tag_state": "NOT_CREATED",
        "release_state": "NOT_PUBLISHED",
        "core_updates_state": "NOT_RUN",
        "production_write": False,
        "kewaro_repository_delete": "NOT_AUTHORIZED",
    }
    files["VF_PROJECT.json"] = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return files


def main() -> int:
    if not os.environ.get("GH_TOKEN"):
        raise SystemExit("GH_TOKEN missing")
    ref = gh(f"repos/{REPO}/git/ref/heads/{BRANCH}")
    assert isinstance(ref, dict) and ref["object"]["sha"] == START, ref
    if gh_exists(f"repos/{REPO}/git/ref/tags/v2.38.0"):
        raise SystemExit("premature v2.38.0 tag exists")

    commit = gh(f"repos/{REPO}/git/commits/{START}")
    assert isinstance(commit, dict)
    base_tree = commit["tree"]["sha"]
    root_tree = gh(f"repos/{REPO}/git/trees/{base_tree}")
    assert isinstance(root_tree, dict)
    base_src = next(x["sha"] for x in root_tree["tree"] if x["path"] == "src")

    files = build_files()
    if sorted(files) != EXPECTED:
        raise SystemExit(f"metadata boundary mismatch: {sorted(files)}")
    json.loads(files["VF_PROJECT.json"])

    entries: list[dict[str, str]] = []
    for path in EXPECTED:
        blob = gh("repos/%s/git/blobs" % REPO, method="POST", payload={"content": files[path], "encoding": "utf-8"})
        assert isinstance(blob, dict)
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    tree = gh(f"repos/{REPO}/git/trees", method="POST", payload={"base_tree": base_tree, "tree": entries})
    assert isinstance(tree, dict)
    new_tree = tree["sha"]
    new_root = gh(f"repos/{REPO}/git/trees/{new_tree}")
    assert isinstance(new_root, dict)
    new_src = next(x["sha"] for x in new_root["tree"] if x["path"] == "src")
    if new_src != base_src:
        raise SystemExit(f"src tree drift: {base_src} -> {new_src}")

    new_commit_obj = gh(
        f"repos/{REPO}/git/commits",
        method="POST",
        payload={"message": "docs(P01): sync V2.38.0 Projects release authority", "tree": new_tree, "parents": [START]},
    )
    assert isinstance(new_commit_obj, dict)
    new_commit = new_commit_obj["sha"]
    gh(f"repos/{REPO}/git/refs/heads/{BRANCH}", method="PATCH", payload={"sha": new_commit, "force": False})

    ref2 = gh(f"repos/{REPO}/git/ref/heads/{BRANCH}")
    assert isinstance(ref2, dict) and ref2["object"]["sha"] == new_commit
    compare = gh(f"repos/{REPO}/compare/{START}...{new_commit}")
    assert isinstance(compare, dict)
    actual = sorted(x["filename"] for x in compare["files"])
    if actual != EXPECTED:
        raise SystemExit(f"compare boundary mismatch: {actual}")
    if get_content("VERSION", new_commit).strip() != VERSION:
        raise SystemExit("root VERSION drift")
    if get_content("src/VERSION.txt", new_commit).strip() != VERSION:
        raise SystemExit("runtime VERSION drift")

    print("P01_V2380_AUTHORITY_SYNC=PASS")
    print(f"P01_V2380_AUTHORITY_SOURCE={new_commit}")
    print(f"P01_V2380_AUTHORITY_TREE={new_tree}")
    print(f"P01_V2380_SRC_TREE_UNCHANGED={new_src}")
    print("P01_V2380_METADATA_FILES=9")
    print("P01_V2380_MAIN_WRITE=0")
    print("P01_V2380_FORMAL_RELEASE_WRITE=0")
    print("P01_V2380_PRODUCTION_WRITE=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
