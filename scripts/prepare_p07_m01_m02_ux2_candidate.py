#!/usr/bin/env python3
"""P07-M01 网络代理节点 / P07-M02 服务器性能检测 UX2
Pre-release-only exact upgrade plan. DOES NOT publish or change official Toolbox.
Writes a candidate shell script only at the caller's selected isolated path.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parents[1] / "installers/p07-toolbox.sh"
M01_INSTALLER_BLOB = "0919751da9038b6db51a88c7052195becc152e32"
M01_MANIFEST = "1f66f642769848e5be0c9a25ccb58a60e97e40fe2eb58a088233a5c129f1cb90"
M02_SHA = "18a7a7dc401772fda7344845b952bc307a46f05443d086ec5e38a1954308587d"
OLD_M02_SHA = "7b083e4cf105d40b04b4cbe898fb6b9e1bb7f1ef3385bc1d20829796f6852013"
OLD_M01_MANIFEST = "56c93541c7fa8386b12769573bd69413a51e3da9f5f4e277a4649e61bbc6cd3d"
PIN = "c83059495c59244f3b8328e33c10df1bb775a4e1"


def exact_one(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"Candidate source drift: {old[:100]}")
    return source.replace(old, new)


def generate(upgrade_installer_ref: str, source: str | None = None) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", upgrade_installer_ref):
        raise ValueError("Expected immutable 40-char Git commit ref")
    text = SOURCE.read_text(encoding="utf-8") if source is None else source
    changes = [
        ('VF_NODE_EXPECTED="0.1.0-ux1"', 'VF_NODE_EXPECTED="0.1.0-ux2"'),
        ('M01_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-vf-node-independent-ux1.sh"',
         f'M01_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/{upgrade_installer_ref}/installers/p07-vf-node-independent-ux2-candidate.sh"'),
        ('M01_INSTALLER_BLOB="4f9139d001f1d5e2415c3fe883adc1a54ef3bec3"', f'M01_INSTALLER_BLOB="{M01_INSTALLER_BLOB}"'),
        (f'M01_MANIFEST_SHA256="{OLD_M01_MANIFEST}"', f'M01_MANIFEST_SHA256="{M01_MANIFEST}"'),
        ('M01_TARGET_MANIFEST_SHA256="$M01_MANIFEST_SHA256"',
         'M01_PREVIOUS_BUILD="0.1.0-ux1"\n'
         f'M01_PREVIOUS_MANIFEST_SHA256="{OLD_M01_MANIFEST}"\n'
         'M01_TARGET_MANIFEST_SHA256="$M01_MANIFEST_SHA256"'),
        ('"$M01_BOOTSTRAP_BUILD") expected_manifest="$M01_BOOTSTRAP_MANIFEST_SHA256" ;;',
         '"$M01_BOOTSTRAP_BUILD") expected_manifest="$M01_BOOTSTRAP_MANIFEST_SHA256" ;;\n'
         '    "$M01_PREVIOUS_BUILD") expected_manifest="$M01_PREVIOUS_MANIFEST_SHA256" ;;'),
        ('VPS_AUDIT_BUILD_EXPECTED="2.1.1-ux1"', 'VPS_AUDIT_BUILD_EXPECTED="2.1.1-ux2"'),
        ('VPS_AUDIT_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/3cacb9e9ccbe60f76e4b4ac90920bc9d06ead877/experiments/p07-vps-audit-v21-ux1.sh"',
         f'VPS_AUDIT_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/{PIN}/experiments/p07-vps-audit-v21-ux2.sh"'),
        (f'VPS_AUDIT_SHA256="{OLD_M02_SHA}"',
         f'VPS_AUDIT_SHA256="{M02_SHA}"\n'
         'VPS_AUDIT_PREVIOUS_BUILD="2.1.1-ux1"\n'
         f'VPS_AUDIT_PREVIOUS_SHA256="{OLD_M02_SHA}"'),
        ('"$VPS_AUDIT_BOOTSTRAP_BUILD") required_sha="$VPS_AUDIT_BOOTSTRAP_SHA256" ;;',
         '"$VPS_AUDIT_BOOTSTRAP_BUILD") required_sha="$VPS_AUDIT_BOOTSTRAP_SHA256" ;;\n'
         '    "$VPS_AUDIT_PREVIOUS_BUILD") required_sha="$VPS_AUDIT_PREVIOUS_SHA256" ;;'),
    ]
    for old, new in changes:
        text = exact_one(text, old, new)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", required=True, help="exact commit containing UX2 installer candidate")
    parser.add_argument("--output", type=Path, required=True, help="non-official temporary path")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == SOURCE.resolve() or output.is_symlink() or output.exists() or "/installers/" in str(output):
        raise SystemExit("Refusing to overwrite official/current Toolbox or an existing file")
    result = generate(args.ref)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")
    print("M01/M02 UX2 isolated candidate created; OFFICIAL_TOOLBOX_UNCHANGED=YES")
    print("FORMAL_RELEASE=NO DISTRIBUTION=NO PRODUCTION=NO")


if __name__ == "__main__":
    main()
