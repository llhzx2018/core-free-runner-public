#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_module("p01_base_v3", HERE / "p01-build-release.py")
v2 = load_module("p01_v2_atomic", HERE / "p01-build-release-v2.py")

VERSION = "2.21.16"
SOURCE_VERSION = "2.21.14"
SCHEMA = "2026080902"

GATE_ONLY_FILES = {
    ".gitignore",
    "CHANGELOG.md",
    "DEPLOY-HERE.txt",
    "FULL-PACKAGE-NOTES.txt",
    "README.md",
    "UPGRADE-V2.txt",
    "robots.txt",
}
LEGACY_EXTENSION_ZIP = "VF-Start-Browser-Extension.zip"
LEGACY_EXTENSION_ADDITIONS = {
    "browser-extension/popup.css",
    "browser-extension/popup.html",
    "browser-extension/popup.js",
}

AUTHORITY: dict = {}
SOURCE_GATE_KEYS: set[str] = set()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pop_option(argv: list[str], name: str) -> str:
    try:
        i = argv.index(name)
    except ValueError:
        raise SystemExit(f"missing required option: {name}")
    if i + 1 >= len(argv):
        raise SystemExit(f"missing value for option: {name}")
    value = argv[i + 1]
    del argv[i : i + 2]
    return value


def peek_option(argv: list[str], name: str) -> str:
    try:
        i = argv.index(name)
    except ValueError:
        raise SystemExit(f"missing required option: {name}")
    if i + 1 >= len(argv):
        raise SystemExit(f"missing value for option: {name}")
    return argv[i + 1]


def load_source_authority(authority_path: Path, production_root: Path, production_commit: str) -> set[str]:
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    if authority.get("schema") != "p01-app-runtime-authority/1.0":
        raise SystemExit("runtime authority schema mismatch")
    if authority.get("project_id") != "P01" or authority.get("component_id") != "APP":
        raise SystemExit("runtime authority project/component mismatch")
    if authority.get("source_version") != SOURCE_VERSION:
        raise SystemExit("runtime authority source version mismatch")
    if authority.get("production_commit") != production_commit:
        raise SystemExit("runtime authority production commit mismatch")
    frozen = authority.get("frozen_runtime_target") or {}
    if int(frozen.get("count", 0)) != 124 or frozen.get("exact_reconciliation") != "124/124 PASS":
        raise SystemExit("frozen 2.21.14 runtime authority is not sealed 124/124")

    legacy_manifest_path = production_root / "release-manifest.json"
    legacy = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
    runtime_files = legacy.get("runtime_files") or {}
    if legacy.get("version") != SOURCE_VERSION or int(legacy.get("runtime_hashed_file_count", 0)) != 121:
        raise SystemExit("historical 2.21.14 release-manifest baseline mismatch")
    if len(runtime_files) != 121 or LEGACY_EXTENSION_ZIP not in runtime_files:
        raise SystemExit("historical runtime path authority mismatch")

    derivation = authority.get("app_runtime_derivation") or {}
    if set(derivation.get("remove") or []) != {LEGACY_EXTENSION_ZIP}:
        raise SystemExit("legacy component handoff removal rule mismatch")
    if set(derivation.get("add") or []) != LEGACY_EXTENSION_ADDITIONS:
        raise SystemExit("legacy popup handoff additions mismatch")
    if set(derivation.get("gate_only_files_forbidden") or []) != GATE_ONLY_FILES:
        raise SystemExit("gate-only exclusion authority mismatch")

    keys = set(runtime_files)
    keys.remove(LEGACY_EXTENSION_ZIP)
    keys.update(LEGACY_EXTENSION_ADDITIONS)
    if len(keys) != int(derivation.get("expected_app_source_gate_count", 0)) or len(keys) != 123:
        raise SystemExit(f"APP source runtime gate count mismatch: {len(keys)}")
    if keys & GATE_ONLY_FILES:
        raise SystemExit("non-runtime delivery/repository file leaked into APP source gate")

    missing = sorted(k for k in keys if not (production_root / k).is_file())
    if missing:
        raise SystemExit(f"production commit misses prior runtime authority paths: {missing}")

    ext = json.loads((production_root / "browser-extension/manifest.json").read_text(encoding="utf-8"))
    if str(ext.get("version")) != "1.6.4":
        raise SystemExit("Browser Extension legacy handoff must remain 1.6.4")

    global AUTHORITY
    AUTHORITY = authority
    return keys


def corrected_build_repair(source: dict[str, bytes], target: dict[str, bytes], bridge_update_hash: str) -> str:
    missing = sorted(SOURCE_GATE_KEYS - set(source))
    if missing:
        raise SystemExit(f"source runtime authority missing from production checkout: {missing}")
    source_gate = {k: source[k] for k in sorted(SOURCE_GATE_KEYS)}
    if set(source_gate) & GATE_ONLY_FILES:
        raise SystemExit("gate-only files leaked into corrected source manifest")
    if len(source_gate) != 123:
        raise SystemExit(f"corrected source gate must contain 123 APP runtime files, got {len(source_gate)}")

    if "release-manifest.json" not in target:
        raise SystemExit("generated target release-manifest missing")
    target_runtime = {
        k: v for k, v in target.items()
        if k != "release-manifest.json" and k not in GATE_ONLY_FILES
    }
    if set(target_runtime) & GATE_ONLY_FILES:
        raise SystemExit("gate-only files leaked into target runtime identity")

    release_manifest = json.loads(target["release-manifest.json"].decode("utf-8"))
    release_manifest["runtime_hashed_file_count"] = len(target_runtime)
    release_manifest["runtime_files"] = {k: sha256_bytes(v) for k, v in sorted(target_runtime.items())}
    release_manifest["atomic_runtime_boundary"] = {
        "source_authority": "P01 V2.21.14 Frozen Runtime Target / 124-file exact reconciliation",
        "source_app_gate_count": len(source_gate),
        "target_app_gate_count": len(target_runtime),
        "gate_only_files_excluded": sorted(GATE_ONLY_FILES),
        "package_payload_is_not_runtime_authority": True,
    }
    release_manifest["browser_extension"]["legacy_transition"] = {
        "source_version": "1.6.4",
        "target_version": "1.6.4",
        "legacy_distribution_artifact": LEGACY_EXTENSION_ZIP,
        "historical_frozen_target_member": True,
        "app_gate_policy": "EXCLUDED_AND_PRESERVED",
        "app_atomic_owns_legacy_zip": False,
    }
    target["release-manifest.json"] = (
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    atomic_target = dict(target_runtime)
    atomic_target["release-manifest.json"] = target["release-manifest.json"]
    repair = v2.build_repair(source_gate, atomic_target, bridge_update_hash)
    old = "public const TARGET_VERSION='2.21.15';"
    new = f"public const TARGET_VERSION='{VERSION}';"
    if repair.count(old) != 1:
        raise SystemExit("cannot safely retarget V2 Atomic template")
    repair = repair.replace(old, new, 1)
    return repair


def postprocess(out: Path) -> None:
    notes = f"""# VF Start V{VERSION}\n\n本版本是 V2.21.15 已确认 Atomic Old Source Gate 缺陷的维护修正版，不增加产品功能。\n\n- 修正生成器：Old Production Source Gate 从 prior Formal Production Runtime Identity Authority 生成，不再从 FULL / Git repository 文件全集生成。\n- V2.21.14 APP Frozen Runtime Authority：124-file exact reconciliation；Legacy Browser Extension ZIP 通过组件 Handoff 从 APP Gate 排除并保留。\n- 7 个非 Runtime 文件不再参与 APP Runtime SHA Gate：.gitignore、CHANGELOG.md、DEPLOY-HERE.txt、FULL-PACKAGE-NOTES.txt、README.md、UPGRADE-V2.txt、robots.txt。\n- Browser Extension：1.6.4，独立组件，本轮不升版；APP Atomic 不删除、不覆盖历史 VF-Start-Browser-Extension.zip。\n- Schema：{SCHEMA} → {SCHEMA}，无 Migration / 业务数据变化。\n- Production 在正式授权升级前仍为 V{SOURCE_VERSION}。\n"""
    (out / f"VF_Start_V{VERSION}_RELEASE_NOTES.md").write_text(notes, encoding="utf-8")

    formal_path = out / f"VF_Start_V{VERSION}_RELEASE_MANIFEST.json"
    formal = json.loads(formal_path.read_text(encoding="utf-8"))
    formal["corrective_release"] = {
        "supersedes": "2.21.15",
        "known_defect": "V2.21.15_ATOMIC_OLD_SOURCE_GATE_BOUNDARY_DEFECT",
        "scope": "ATOMIC_SOURCE_GATE_BOUNDARY_CORRECTION",
    }
    formal["atomic_runtime_gate"] = {
        "source_version": SOURCE_VERSION,
        "source_app_gate_count": 123,
        "gate_only_files_excluded": sorted(GATE_ONLY_FILES),
        "authority": "docs/evidence/P01_V2.21.14_APP_RUNTIME_AUTHORITY.json",
        "generator_rule": "PRIOR_FORMAL_PRODUCTION_RUNTIME_IDENTITY",
    }
    formal["browser_extension"] = {
        "version": "1.6.4",
        "independent": True,
        "released_this_round": False,
        "legacy_distribution_artifact": LEGACY_EXTENSION_ZIP,
        "legacy_handoff": "EXCLUDED_FROM_APP_GATE_AND_PRESERVED",
    }
    formal["gates"].update({
        "original_2_21_15_failure_replay": "PENDING",
        "corrected_fixture_upgrade": "PENDING",
        "true_runtime_tamper_negative": "PENDING",
        "gate_only_file_negative": "PENDING",
    })
    formal_path.write_text(json.dumps(formal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sums = out / "SHA256SUMS.txt"
    artifacts = [p for p in sorted(out.iterdir()) if p.is_file() and p.name != "SHA256SUMS.txt"]
    sums.write_text("".join(f"{base.sha256_file(p)}  {p.name}\n" for p in artifacts), encoding="utf-8")


def main() -> None:
    authority_value = pop_option(sys.argv, "--source-runtime-authority")
    production_root = Path(peek_option(sys.argv, "--production")).resolve()
    production_commit = peek_option(sys.argv, "--production-commit")
    out = Path(peek_option(sys.argv, "--out")).resolve()

    global SOURCE_GATE_KEYS
    SOURCE_GATE_KEYS = load_source_authority(Path(authority_value).resolve(), production_root, production_commit)

    base.VERSION = VERSION
    base.SOURCE_VERSION = SOURCE_VERSION
    base.SCHEMA = SCHEMA
    base.build_repair = corrected_build_repair
    base.main()
    postprocess(out)

    print(json.dumps({
        "generator": "p01-build-release-v3",
        "version": VERSION,
        "source_version": SOURCE_VERSION,
        "source_app_runtime_gate_files": len(SOURCE_GATE_KEYS),
        "gate_only_files_excluded": sorted(GATE_ONLY_FILES),
        "legacy_extension_handoff": LEGACY_EXTENSION_ZIP,
        "status": "PASS",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
