#!/usr/bin/env python3
"""P07 public Toolbox terminal UX V3 adoption and PR negative gate.

No private P07 source or token is needed. The canonical design authority
stays in the private product repository. This checks PUBLIC owned code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DOC = "docs/authority/P07_TERMINAL_UX_ADOPTION.md"
WORKFLOW = ".github/workflows/p07-public-terminal-ux-v3.yml"
SCENARIOS = {
    "main_menu", "readonly", "write_confirmation", "cancel_eof_invalid",
    "success", "failure_block", "no_color_non_tty",
}
REFERENCES = {"ubuntu-subiquity", "redhat-nmtui", "github-gh", "heroku-cli"}
PUBLIC_ROUTES = {
    "installers/p07-toolbox.sh": "P07-TOOLBOX",
    "installers/vf-node.sh": "P07-M01",
    "installers/p07-vpscheck.sh": "P07-M02",
    "installers/p07.sh": "P07-M03",
    "installers/p07-system-care.sh": "P07-M04",
}
USER_COPY = re.compile(
    r"\b(?:printf|echo|say|read|ui_[a-z]+|menu_[a-z]+)\b"
    r"|菜单|选择|确认|返回|检查|安装|完成|失败|重试|按 Enter|\bprompt\b",
    re.I,
)


class PublicUXError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise PublicUXError(message)


def load_and_check(root: Path = ROOT) -> None:
    doc = root / DOC
    wf = root / WORKFLOW
    agents = root / "AGENTS.md"
    for p in (doc, wf, agents):
        require(p.is_file() and not p.is_symlink(),
                f"P07 Public UX Gate 缺少 {p.relative_to(root)}")
    text = doc.read_text(encoding="utf-8")
    for token in ("P07_TERMINAL_UX_STANDARD_V3.md",
                  "P07_TERMINAL_UX_MODULES_V1.json",
                  "P07-M01", "P07-M02", "P07-M03", "P07-M04", "P07-M05",
                  "P07-M03-D04", "NO_COLOR", "Terminal"):
        require(token in text, f"P07 public UX 标准与覆盖丢失：{token}")
    require("P07_TERMINAL_UX_ADOPTION.md" in agents.read_text(encoding="utf-8"),
            "Public AGENTS 未接线到 P07 UX V3")
    content = wf.read_text(encoding="utf-8")
    for token in ("pull_request:", "check_p07_public_terminal_ux.py",
                  "--base-ref", "BASE_SHA",
                  "test_p07_public_terminal_ux.py"):
        require(token in content, f"P07 Public UX CI 接线缺失：{token}")
    for route in PUBLIC_ROUTES:
        require((root / route).is_file(), f"公共 P07 用户入口不存在：{route}")
    # M02 pinned v21 is an immutable external historical version, NOT a
    # file in current public main. Never pretend it is a current-main path.
    require("experiments/p07-vps-audit-v21.sh" in text,
            "必须解释 M02 固定历史源码与当前 main 的区别")


def source_owner(path: str) -> str | None:
    if path in PUBLIC_ROUTES:
        return PUBLIC_ROUTES[path]
    if re.fullmatch(r"experiments/p07-vps-audit-[\w.-]+\.sh", path):
        return "P07-M02"
    if re.fullmatch(r"installers/p07-[\w.-]*(?:menu|ui)[\w.-]*\.sh", path):
        raise PublicUXError(f"P07 新公共菜单源 {path} 未登记 UI 模块归属")
    return None


def git_changed(root: Path, base_ref: str) -> tuple[list[str], dict[str, str]]:
    require(bool(base_ref) and not base_ref.startswith("-"), "公共 PR base 不明确")
    try:
        merge_base = subprocess.run(
            ["git", "-C", str(root), "merge-base", base_ref, "HEAD"],
            check=True, text=True, capture_output=True, timeout=10
        ).stdout.strip()
        names_raw = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "-z", merge_base, "HEAD"],
            check=True, capture_output=True, timeout=10
        ).stdout
        paths = [v.decode("utf-8") for v in names_raw.split(b"\0") if v]
        delta = {}
        for path in paths:
            if source_owner(path) is None:
                continue
            content = subprocess.run(
                ["git", "-C", str(root), "diff", "--unified=0",
                 merge_base, "HEAD", "--", path],
                check=True, text=True, capture_output=True, timeout=10
            ).stdout
            changed = "\n".join(line[1:] for line in content.splitlines()
                                if (line.startswith("+") or line.startswith("-"))
                                and not line.startswith(("+++", "---")))
            delta[path] = changed
        return paths, delta
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublicUXError("公共 PR Git diff 不可验证") from exc


def validate_pr(
    changed_paths: list[str], changed_lines: dict[str, str],
    root: Path = ROOT,
) -> str:
    impacted: dict[str, set[str]] = {}
    for path in changed_paths:
        require(bool(path) and not path.startswith("/") and
                ".." not in Path(path).parts, "P07 public UX 路径无效")
        owner = source_owner(path)
        if owner and USER_COPY.search(changed_lines.get(path, "")):
            impacted.setdefault(owner, set()).add(path)
    if not impacted:
        return "P07_PUBLIC_UI_CHANGE=N_A"
    reviews = [x for x in changed_paths if x.startswith("docs/ux-reviews/")
               and x.endswith(".json")]
    require(bool(reviews), "公共 P07 终端用户提示已改动，但缺少 UX PR 证据")
    covered: dict[str, set[str]] = {}
    for rel in reviews:
        file = root / rel
        require(file.is_file() and not file.is_symlink(), "公共 UX review 文件不存在")
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise PublicUXError("公共 UX review JSON 不可读") from exc
        module = data.get("module_id")
        require(data.get("schema") == "vf.p07.public-ux-review.v1" and
                module in impacted, "公共 UX review 模块与当前 PR 不一致")
        require(data.get("reference") in REFERENCES and
                data.get("production_run") is False,
                "公共 UX review 无企业参考或冒充 Production")
        files = data.get("changed_surfaces")
        require(isinstance(files, list) and files and
                set(files) <= impacted[module],
                "公共 UX review 记录了其它模块/其它 PR 文件")
        tests = data.get("scenario_tests")
        require(isinstance(tests, dict) and set(tests) == SCENARIOS,
                "公共 UX review 七场景正反用例不全")
        for scenario, proof in tests.items():
            require(isinstance(proof, dict), "公共 UX 测试记录缺少具体方法")
            file_path, name = proof.get("file"), proof.get("test")
            require(isinstance(file_path, str) and
                    file_path.startswith("tests/") and file_path.endswith(".py")
                    and ".." not in Path(file_path).parts and
                    isinstance(name, str) and re.fullmatch(r"test_[\w]+", name),
                    f"公共 UX {scenario} 测试标识非法")
            path = root / file_path
            require(path.is_file() and not path.is_symlink(), "公共 UX 测试文件不存在")
            code = path.read_text(encoding="utf-8")
            require(f"def {name}(" in code and "assert" in code,
                    f"公共 UX {scenario} 测试函数缺失")
        covered.setdefault(module, set()).update(files)
    require(covered == impacted, "公共 P07 终端 UI PR 有模块/源文件未接受 UX 验收")
    return "P07_PUBLIC_UI_REVIEW=STRUCTURAL_PASS (需独立实际交互测试)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-ref", help="PR base commit for real Git delta")
    args = ap.parse_args(argv)
    try:
        load_and_check()
        print("P07_PUBLIC_TERMINAL_UX_V3_ROUTE=PASS 五模块公共触点 + 工作流")
        if args.base_ref:
            changed, lines = git_changed(ROOT, args.base_ref)
            print(validate_pr(changed, lines))
        return 0
    except (PublicUXError, TypeError, KeyError, OSError) as exc:
        print(f"P07_PUBLIC_TERMINAL_UX_GATE=BLOCKED {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
