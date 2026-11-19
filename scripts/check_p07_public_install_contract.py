#!/usr/bin/env python3
"""P07 sole public anonymous SSH entry contract — source-level gate, not a Release proof."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ("bash <(curl -fsSL "
           "https://raw.githubusercontent.com/llhzx2018/core-free-runner-public"
           "/main/installers/p07-toolbox.sh)")
DOCUMENTS = (
    "AGENTS.md",
    "README.md",
    "docs/authority/P07_PUBLIC_INSTALL_CONTRACT.md",
    "docs/authority/P07_TERMINAL_UX_ADOPTION.md",
)
TOOLBOX = "installers/p07-toolbox.sh"


class PublicInstallContractError(ValueError):
    pass


def check(ok: bool, reason: str) -> None:
    if not ok:
        raise PublicInstallContractError(reason)


def get(root: Path, path: str) -> str:
    target = root / path
    check(target.is_file() and not target.is_symlink(), f"缺少正式公共分发文件：{path}")
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PublicInstallContractError(f"公共分发文件不可读：{path}") from exc


def validate(root: Path = ROOT) -> str:
    for path in DOCUMENTS:
        doc = get(root, path)
        check(doc.count(COMMAND) == 1, f"{path} 未保持唯一正确的公共 SSH 指令")
        check(doc.count("bash <(curl") == 1, f"{path} 提供了另一条不一致的安装指令")
    installer = get(root, TOOLBOX)
    check(installer.startswith("#!/usr/bin/env bash"), "公共 Toolbox 不是 Shell 安装器")
    for pattern in (r"\bgh\s+(?:auth|api|repo|release|login)\b",
                    r"\bgit\s+clone\b",
                    r"core-free-runner-private",
                    r"(?:GH_TOKEN|GITHUB_TOKEN|GITHUB_PAT|GIT_TOKEN)"):
        check(not re.search(pattern, installer),
              "公共 Toolbox 不能依赖 GitHub 用户认证或私有仓")
    check('https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/'
          in installer, "公共 Toolbox 未锁定公共源码托管")
    check("VF_NODE_EXPECTED=" in installer and "VPS_AUDIT_BUILD_EXPECTED=" in installer
          and "M04_BUILD_EXPECTED=" in installer and "M05_BUILD_EXPECTED=" in installer,
          "公共五模块路由元数据不完整")
    build = re.search(r'^VF_SERVER_OPS_BUILD_EXPECTED="0[.]1[.]0-release([0-9]+)"$',
                      installer, re.M)
    url = re.search(
        r'^VF_SERVER_OPS_INSTALLER="https://raw[.]githubusercontent[.]com/'
        r'llhzx2018/core-free-runner-public/'
        r'\$\{VF_SERVER_OPS_INSTALLER_REF\}/installers/p07-m03-release'
        r'([0-9]+)-atomic[.]sh"$', installer, re.M)
    check(build is not None and url is not None, "M03 公开正式版本 pin 不存在或非匿名 HTTPS")
    check(build.group(1) == url.group(1), "M03 Toolbox 目标构建与实际安装器版本不一致")
    check(re.search(r'^VF_SERVER_OPS_MANIFEST_BLOB="[a-f0-9]{40}"$',
                    installer, re.M) is not None, "M03 公开运行时 manifest 身份缺失")
    m03 = get(root, f"installers/p07-m03-release{build.group(1)}-atomic.sh")
    check(f"BUILD='0.1.0-release{build.group(1)}'" in m03,
          "M03 模块安装器不是公共 Toolbox 所声称的版本")
    check(re.search(r"(?m)^ZIP_SHA256='[a-f0-9]{64}'$", m03) is not None,
          "M03 官方 ZIP SHA256 锁定缺失")
    check("https://github.com/llhzx2018/core-free-runner-public/releases/download/"
          in m03 and "sha256sum -c" in m03,
          "M03 不再是可匿名下载、可校验的公共正式制品")
    check(not re.search(r"\bgh\s+(?:auth|api|login)\b|core-free-runner-private", m03),
          "M03 正式安装器不得要求 GitHub 授权或私有仓")
    return "P07_PUBLIC_ANONYMOUS_SINGLE_ENTRY=STRUCTURAL_PASS"


def main() -> int:
    try:
        print(validate())
        return 0
    except (PublicInstallContractError, ValueError, OSError) as exc:
        print(f"P07_PUBLIC_ANONYMOUS_SINGLE_ENTRY=BLOCKED {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
