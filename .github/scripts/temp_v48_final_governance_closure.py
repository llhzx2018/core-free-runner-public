#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

GOV = "llhzx2018/gov-doc"
TAG = "skill-book-v4.8-candidate-20260827"
ASSET = "skill-book_V4.8_CANDIDATE_20260827.zip"
EXPECTED_RELEASE_ID = 378052388
EXPECTED_BYTES = 156008
EXPECTED_SHA = "df933b799e7e56a662f055abfe9825d15a4470c86cf9b41a34e30cbb98bf4c4b"
SOURCE_COMMIT = "d5d809172f23b31212cf6b66551f775b2e07e35f"
RUNNER_RUN = "33105833415"
RUNNER_JOB = "98635300217"


def run(*args: str, cwd: Path | None = None, capture: bool = True) -> str:
    p = subprocess.run(args, cwd=cwd, text=True, check=True, stdout=subprocess.PIPE if capture else None)
    return p.stdout.strip() if capture else ""


def gh_json(path: str) -> dict:
    return json.loads(run("gh", "api", path))


def release_truth() -> tuple[int, int]:
    j = gh_json(f"repos/{GOV}/releases/tags/{TAG}")
    assert j["id"] == EXPECTED_RELEASE_ID
    assert j["prerelease"] is True
    assets = {a["name"]: a for a in j["assets"]}
    z = assets[ASSET]
    s = assets[ASSET + ".sha256"]
    assert z["size"] == EXPECTED_BYTES
    assert z.get("digest") == "sha256:" + EXPECTED_SHA
    print(f"V48_LIVE_RELEASE_ID={j['id']}")
    print(f"V48_LIVE_ZIP_ASSET_ID={z['id']}")
    print(f"V48_LIVE_SHA_ASSET_ID={s['id']}")
    print("V48_LIVE_RELEASE_AUTHORITY=PASS")
    return int(z["id"]), int(s["id"])


def patch_current(root: Path) -> None:
    p = root / "CURRENT.md"
    s = p.read_text(encoding="utf-8")
    old = "| skill-book | V3.5 | V4.6 CANDIDATE（非 Current） |"
    new = "| skill-book | V3.5 | V4.7 CANDIDATE（非 Current） |"
    assert old in s or new in s
    s = s.replace(old, new)
    oldp = "`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6` 为保留的历史 Candidate，`V4.7` 为最新 Candidate；八者均未晋升 Source Current。V4.7 已进入 Candidate Distribution，但未进入 Current Distribution。"
    newp = "`skill-book V4.0/V4.1/V4.2/V4.3/V4.4/V4.5/V4.6/V4.7` 为保留的历史 Candidate，`V4.8` 为最新 Candidate；九者均未晋升 Source Current。V4.8 已进入 Candidate Distribution，但未进入 Current Distribution。"
    if oldp in s:
        s = s.replace(oldp, newp)
    assert "`V4.8` 为最新 Candidate" in s
    p.write_text(s, encoding="utf-8")


def patch_index(root: Path, zid: int, sid: int) -> None:
    p = root / "distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md"
    s = p.read_text(encoding="utf-8")
    candidate = f'''## Candidate（不改变 Current）

`skill-book V4.8` 是最新 `CANDIDATE / NOT CURRENT`；Source Current仍为V3.5，且V4.8不包含在Current总包中。Installed Runtime Observation为V4.7 Candidate。

- [直接下载 skill-book V4.8 Candidate ZIP](https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{ASSET})
- [下载 SHA-256 文件](https://github.com/llhzx2018/gov-doc/releases/download/{TAG}/{ASSET}.sha256)
- [查看 V4.8 Candidate Release](https://github.com/llhzx2018/gov-doc/releases/tag/{TAG})
- [查看 V4.8 Candidate Source](https://github.com/llhzx2018/gov-doc/tree/main/skills/skill-book/V4.8)
- [查看 V4.8 Candidate Mother Overlay](https://github.com/llhzx2018/gov-doc/blob/main/mother-specs/skill-book/V4.8/SKILL_BOOK_V4.8_CANDIDATE_OVERLAY.md)
- [查看 V4.8 Candidate 分发说明](https://github.com/llhzx2018/gov-doc/blob/main/distribution/skills/candidates/skill-book/V4.8/README.md)

Published Distribution Identity：

- Bytes：`{EXPECTED_BYTES}`
- SHA-256：`{EXPECTED_SHA}`
- Release ID：`{EXPECTED_RELEASE_ID}`
- Remote Asset ID：`{zid}`
- SHA Asset ID：`{sid}`
- Exact Source Commit：`{SOURCE_COMMIT}`
- Runner Run：`{RUNNER_RUN}`
- Runner Job：`{RUNNER_JOB}`
- Unit Tests：`38/38 PASS (modular execution)`
- Python Syntax：`PASS`
- Local / Remote ZIP Identity：`MATCH`
- Remote Download Readback：`PASS`
- ZIP CRC / Unsafe Path / Duplicate Path / pycache：`PASS`
- Backend V4.8 Runtime Test：`NOT_RUN`
- Real Reader Forward Evidence：`NOT_RUN`
- Current Promotion：`NOT_AUTHORIZED`
- Status：`PUBLISHED_REMOTE_VERIFIED`

V4.8 Candidate Publication仅完成分发闭环，不将Source Current从V3.5晋升，也不以机器PASS替代READ / LEARN / TRAIN / DO的真人Reader Outcome。

历史 Candidate：

- [skill-book V4.7](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.7)
- [skill-book V4.6](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.6)
- [skill-book V4.5](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.5)
- [skill-book V4.4](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.4)
- [skill-book V4.3](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.3)
- [skill-book V4.2](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.2)
- [skill-book V4.1](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.1)
- [skill-book V4.0](https://github.com/llhzx2018/gov-doc/tree/main/distribution/skills/candidates/skill-book/V4.0)'''
    ns, n = re.subn(r"## Candidate（不改变 Current）\n.*\Z", candidate, s, flags=re.S)
    assert n == 1
    p.write_text(ns, encoding="utf-8")


def patch_candidate_pages(root: Path, zid: int, sid: int) -> None:
    for rel in (
        "distribution/skills/candidates/skill-book/V4.8/README.md",
        "distribution/skills/candidates/skill-book/V4.8/RUNTIME_ZIP_MIRROR_STATUS.md",
    ):
        p = root / rel
        s = p.read_text(encoding="utf-8")
        s, n1 = re.subn(r"(- Remote Asset ID：`)\d+(`)", rf"\g<1>{zid}\g<2>", s, count=1)
        s, n2 = re.subn(r"(- SHA Asset ID：`)\d+(`)", rf"\g<1>{sid}\g<2>", s, count=1)
        assert n1 == 1 and n2 == 1
        assert "PUBLISHED_REMOTE_VERIFIED" in s
        p.write_text(s, encoding="utf-8")


def verify_files(root: Path, zid: int, sid: int) -> None:
    cur = (root / "CURRENT.md").read_text(encoding="utf-8")
    idx = (root / "distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md").read_text(encoding="utf-8")
    rd = (root / "distribution/skills/candidates/skill-book/V4.8/README.md").read_text(encoding="utf-8")
    mir = (root / "distribution/skills/candidates/skill-book/V4.8/RUNTIME_ZIP_MIRROR_STATUS.md").read_text(encoding="utf-8")
    assert "| skill-book | V3.5 | V4.7 CANDIDATE（非 Current） |" in cur
    assert "`V4.8` 为最新 Candidate" in cur
    assert "`skill-book V4.8` 是最新 `CANDIDATE / NOT CURRENT`" in idx
    for needle in (EXPECTED_SHA, str(zid), str(sid), SOURCE_COMMIT, "Current Promotion：`NOT_AUTHORIZED`"):
        assert needle in idx
    assert str(zid) in rd and str(sid) in rd
    assert str(zid) in mir and str(sid) in mir
    assert "PUBLISHED_REMOTE_VERIFIED" in rd and "PUBLISHED_REMOTE_VERIFIED" in mir


def main() -> None:
    token = os.environ.get("VF_RELEASE_WRITE_TOKEN") or os.environ.get("RELEASE_TOKEN") or os.environ.get("GH_TOKEN")
    assert token, "VF_RELEASE_WRITE_TOKEN missing"
    os.environ["GH_TOKEN"] = token
    zid, sid = release_truth()

    root = Path("gov-v48-final")
    if root.exists():
        subprocess.run(("rm", "-rf", str(root)), check=True)
    url = f"https://x-access-token:{token}@github.com/{GOV}.git"
    run("git", "clone", "-q", url, str(root), capture=False)
    run("git", "config", "user.name", "VF Candidate Reconcile", cwd=root)
    run("git", "config", "user.email", "release@kewaro.com", cwd=root)
    live = run("git", "rev-parse", "origin/main", cwd=root)
    remote_live = run("git", "ls-remote", "origin", "refs/heads/main", cwd=root).split()[0]
    assert live == remote_live
    print(f"GOV_MAIN_BEFORE_V48_FINAL={live}")
    run("git", "checkout", "-q", "-B", "v48-final", "origin/main", cwd=root, capture=False)
    subprocess.run(("git", "merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD"), cwd=root, check=True)

    patch_current(root)
    patch_index(root, zid, sid)
    patch_candidate_pages(root, zid, sid)
    verify_files(root, zid, sid)
    subprocess.run(("git", "diff", "--check"), cwd=root, check=True)
    subprocess.run(("git", "add", "CURRENT.md", "distribution/skills/CURRENT_SKILL_DOWNLOAD_INDEX.md", "distribution/skills/candidates/skill-book/V4.8/README.md", "distribution/skills/candidates/skill-book/V4.8/RUNTIME_ZIP_MIRROR_STATUS.md"), cwd=root, check=True)
    subprocess.run(("git", "diff", "--cached", "--check"), cwd=root, check=True)
    changed = subprocess.run(("git", "diff", "--cached", "--quiet"), cwd=root).returncode != 0
    if changed:
        run("git", "commit", "-q", "-m", "skill-book: finalize V4.8 published candidate pointers", cwd=root, capture=False)
        commit = run("git", "rev-parse", "HEAD", cwd=root)
        before_push = run("git", "ls-remote", "origin", "refs/heads/main", cwd=root).split()[0]
        assert before_push == live, f"main moved: {live} -> {before_push}"
        run("git", "push", "-q", "origin", "HEAD:main", cwd=root, capture=False)
        print(f"V48_FINAL_GOV_COMMIT={commit}")
        print("V48_FINAL_GOV_WRITE=PASS")
    else:
        print("V48_GOVERNANCE_ALREADY_FINAL=PASS")

    run("git", "fetch", "-q", "origin", "main", cwd=root, capture=False)
    run("git", "reset", "-q", "--hard", "origin/main", cwd=root, capture=False)
    verify_files(root, zid, sid)
    zid2, sid2 = release_truth()
    assert (zid2, sid2) == (zid, sid)
    final = run("git", "rev-parse", "HEAD", cwd=root)
    print(f"V48_FINAL_GOV_MAIN={final}")
    print("LATEST_CANDIDATE=V4.8")
    print("SOURCE_CURRENT=V3.5")
    print("INSTALLED_RUNTIME_OBSERVATION=V4.7")
    print("CURRENT_PROMOTION=NOT_AUTHORIZED")
    print("V48_MIRROR=PUBLISHED_REMOTE_VERIFIED")
    print("V48_FINAL_REMOTE_READBACK=PASS")


if __name__ == "__main__":
    main()
