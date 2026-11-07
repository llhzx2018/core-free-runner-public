#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import base64
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PUBLIC_CONST = r"public const {name}='([^']*)';"
PRIVATE_CONST = r"private const {name}='([^']*)';"
UPDATER_PATHS = (
    "app/UpdateManager.php",
    "app/CoreUpdates/UpdateCore.php",
    "app/CoreUpdates/GitHubClient.php",
)


def die(message: str) -> "NoReturn":
    raise SystemExit(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_rel(rel: str) -> str:
    q = PurePosixPath(rel)
    if rel.startswith("/") or "\\" in rel or ".." in q.parts or str(q) != rel or rel in ("", "."):
        die(f"unsafe path: {rel}")
    return rel


def collect(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    forbidden_parts = {"private", "private_data", "PRIVATE_DATA", "backups", "backup", "sessions", "tokens", "staging"}
    forbidden_suffixes = (".sqlite", ".sqlite3", ".db", ".log", ".env")
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(root).as_posix()
        safe_rel(rel)
        parts = PurePosixPath(rel).parts
        low = rel.lower()
        if any(part in forbidden_parts or part.startswith(".vfnav-data-") for part in parts):
            continue
        if low.endswith(forbidden_suffixes):
            continue
        out[rel] = p.read_bytes()
    return out


def parse_public(text: str, name: str) -> str:
    m = re.search(PUBLIC_CONST.format(name=re.escape(name)), text)
    if not m:
        die(f"missing public constant: {name}")
    return m.group(1)


def decode_private(text: str, name: str):
    m = re.search(PRIVATE_CONST.format(name=re.escape(name)), text)
    if not m:
        die(f"missing private constant: {name}")
    try:
        return json.loads(base64.b64decode(m.group(1)).decode())
    except Exception as exc:
        die(f"invalid private constant {name}: {exc}")


def replace_public(text: str, name: str, value: str) -> str:
    pattern = r"(public const " + re.escape(name) + r"=)'[^']*';"
    out, count = re.subn(pattern, lambda m: m.group(1) + "'" + value + "';", text, count=1)
    if count != 1:
        die(f"cannot replace public constant: {name}")
    return out


def replace_private(text: str, name: str, obj) -> str:
    encoded = base64.b64encode(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).decode()
    pattern = r"(private const " + re.escape(name) + r"=)'[^']*';"
    out, count = re.subn(pattern, lambda m: m.group(1) + "'" + encoded + "';", text, count=1)
    if count != 1:
        die(f"cannot replace private constant: {name}")
    return out


def zip_deterministic(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(files):
            safe_rel(rel)
            info = zipfile.ZipInfo(rel, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.create_system = 3
            z.writestr(info, files[rel])


def subset(files: dict[str, bytes], prefix: str) -> dict[str, str]:
    return {k: sha(v) for k, v in files.items() if k.startswith(prefix)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build one exact-source Owner-approved v2.47.500 Formal Atomic updater fix from signed v2.47.499 bytes.")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--baseline-full", required=True)
    ap.add_argument("--baseline-repair", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--source-version", required=True)
    ap.add_argument("--target-sha", required=True)
    ap.add_argument("--target-tree", required=True)
    args = ap.parse_args()

    if not SEMVER.fullmatch(args.version) or not SEMVER.fullmatch(args.source_version):
        die("version must be x.y.z")
    if not re.fullmatch(r"[0-9a-f]{40}", args.target_sha):
        die("target sha must be 40 lowercase hex")
    if not re.fullmatch(r"[0-9a-f]{40}", args.target_tree):
        die("target tree must be 40 lowercase hex")

    if args.version != "2.47.500" or args.source_version != "2.47.499":
        die("one-case P01 v2.47.500: only formal 2.47.499 source is permitted")
    if args.target_sha != "e8b13aeb13f5fbc9c3f2808acccab69fd05e542a":
        die("one-case formal source drift: target SHA not Owner approved")
    if args.target_tree != "b16fa3d9e9c83649ef988f494ef49f1982c7495e":
        die("one-case formal source drift: target tree not Owner approved")

    candidate = Path(args.candidate).resolve()
    baseline = Path(args.baseline_full).resolve()
    baseline_repair = Path(args.baseline_repair).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    candidate_all = collect(candidate)
    baseline_all = collect(baseline)

    if candidate_all.get("VERSION.txt", b"").strip() != args.version.encode():
        die("candidate VERSION.txt mismatch")
    if baseline_all.get("VERSION.txt", b"").strip() != args.source_version.encode():
        die("baseline FULL VERSION.txt mismatch")
    if "release-manifest.json" not in baseline_all:
        die("baseline FULL release-manifest.json missing")
    if not baseline_repair.is_file():
        die("baseline repair script missing")

    old = baseline_repair.read_text(encoding="utf-8")
    old_target_version = parse_public(old, "TARGET_VERSION")
    old_schema = parse_public(old, "TARGET_SCHEMA")
    if old_target_version != args.source_version:
        die(f"baseline repair target {old_target_version} != source version {args.source_version}")

    old_target = decode_private(old, "TARGET_MANIFEST")
    if not isinstance(old_target, dict) or not old_target:
        die("baseline TARGET_MANIFEST invalid")

    missing = sorted(k for k in old_target if k not in baseline_all)
    if missing:
        die("baseline FULL misses prior Atomic target files: " + ",".join(missing[:10]))
    for rel, expected in old_target.items():
        if sha(baseline_all[rel]) != expected:
            die("baseline FULL bytes do not match prior Atomic target: " + rel)

    source_files = {k: baseline_all[k] for k in sorted(old_target)}
    package_only = set(baseline_all) - set(old_target)
    target_files = {k: v for k, v in candidate_all.items() if k not in package_only}

    # One-case formally Owner-authorized updater safety fix. Cannot be used for other versions.
    # Preserve the existing independent UpdateCore/GitHubClient contracts;
    # do not disable the migration or backup/recovery safety guards.
    if subset(source_files, "migrations/") != subset(target_files, "migrations/"):
        die("updater safety-fix candidate cannot change migrations")
    for rel in ("app/CoreUpdates/UpdateCore.php", "app/CoreUpdates/GitHubClient.php"):
        if source_files.get(rel) != target_files.get(rel):
            die("CoreUpdates compatibility change requires separate authority: " + rel)
    if source_files.get("app/UpdateManager.php") == target_files.get("app/UpdateManager.php"):
        die("updater safety-fix candidate must actually change UpdateManager")
    if b"provedSupersededInstall" not in target_files["app/UpdateManager.php"] or b"unresolvedInstallJournal" not in target_files["app/UpdateManager.php"]:
        die("missing exact interrupted-journal safety fix")
    if b"GLOBAL_LOCK_WAIT_MS=1500" not in target_files["app/Platform/Barrier.php"]:
        die("bounded global lock correction missing")
    for name in ("VERSION.txt", "app/bootstrap.php", "app/UpdateManager.php", "app/Platform/Barrier.php"):
        if name not in source_files or name not in target_files:
            die("missing required source/target: " + name)

    baseline_manifest = json.loads(baseline_all["release-manifest.json"].decode("utf-8"))
    if str(baseline_manifest.get("version", "")) != args.source_version:
        die("baseline release manifest version mismatch")
    baseline_schema = str(baseline_manifest.get("schema_version", ""))
    if baseline_schema and baseline_schema != old_schema:
        die("baseline release manifest schema mismatch")

    runtime_identity = dict(target_files)
    runtime_identity.pop("release-manifest.json", None)

    formal = dict(baseline_manifest)
    formal.update({
        "project": "VF Start",
        "project_id": "P01",
        "project_slug": "vf-start",
        "version": args.version,
        "source_version": args.source_version,
        "release_type": "formal-updater-safety-fix",
        "stage": "FORMAL_RELEASE_ARTIFACT",
        "deployable": True,
        "source_commit": args.target_sha,
        "source_tree": args.target_tree,
        "schema_version": old_schema,
        "schema_change": False,
        "schema_migrations": [],
        "runtime_data_included": False,
        "seed_user_business_data_included": False,
        "runtime_hashed_file_count": len(runtime_identity),
        "runtime_files": {k: sha(v) for k, v in sorted(runtime_identity.items())},
        "updater_safety_fix": {
            "schema_unchanged": True,
            "migrations_unchanged": True,
            "updater_change": "bounded_global_lock_and_interrupted_journal_guard",
            "atomic_interruption_recovery": True,
            "builder": "core-free-runner-public/scripts/p01-v247500-formal-updater-release.py",
            "source_only": True,
            "owner_specific_release_authorized": True,
            "mode_h_gate": "P01_VF_START_2_47_500_ATOMIC524",
            "production_auto_apply": False,
        },
    })
    formal["update"] = {
        "project_id": "P01", "component_id": "APP", "channel": "stable",
        "source_version": args.source_version, "target_version": args.version,
        "from_versions": [args.source_version],
        "asset_name": f"VF_Start_V{args.version}_UPDATE.zip",
        "update_type": "ATOMIC", "backup_required": True,
        "rollback_supported": True,
    }
    release_manifest_bytes = (json.dumps(formal, ensure_ascii=False, indent=2) + "\n").encode()
    target_files["release-manifest.json"] = release_manifest_bytes

    source_manifest = {k: sha(v) for k, v in sorted(source_files.items())}
    target_manifest = {k: sha(v) for k, v in sorted(target_files.items())}
    payload = {k: base64.b64encode(v).decode() for k, v in sorted(target_files.items())}
    removed = sorted(set(source_manifest) - set(target_manifest))

    # The published 2.47.491 repair is the source-file authority, but it is
    # not a safe executable template for the next candidate: it lacks the
    # interruption journal/recovery implementation. Build from the existing
    # public journal-capable Atomic engine, never silently downgrade to old.
    engine = Path(__file__).with_name("p01-build-release-v2.py")
    spec = importlib.util.spec_from_file_location("p01_journal_atomic", engine)
    if spec is None or spec.loader is None:
        die("journal-capable Atomic engine unavailable")
    atomic_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(atomic_module)
    repair = atomic_module.build_repair(source_files, target_files, "")
    repair = replace_public(repair, "SOURCE_VERSION", args.source_version)
    repair = replace_public(repair, "TARGET_VERSION", args.version)
    repair = replace_public(repair, "TARGET_SCHEMA", old_schema)
    for name, obj in (
        ("SOURCE_MANIFEST", source_manifest),
        ("TARGET_MANIFEST", target_manifest),
        ("PAYLOAD", payload),
        ("REMOVED", removed),
        ("SOURCE_ALTERNATES", {}),
    ):
        repair = replace_private(repair, name, obj)
    for guard in ("recoverInterrupted", "journalPath", "VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY", "maintenanceLease", "Atomic 维护锁等待超时"):
        if guard not in repair:
            die("Atomic interruption recovery engine missing: " + guard)

    repair_name = f"repair-v{args.version}.php"
    repair_bytes = repair.encode("utf-8")

    full_files = dict(candidate_all)
    full_files["release-manifest.json"] = release_manifest_bytes
    full_files["FULL-PACKAGE-NOTES.txt"] = (
        f"VF Start V{args.version} FORMAL FULL\n\n"
        "FULL = clean first-install package.\n"
        "No live SQLite, private data, backup, log, session, token, secret, repair or staging data is included.\n"
        f"Existing V{args.source_version} installations must use the formal Atomic UPDATE instead of overwriting with FULL.\n"
    ).encode("utf-8")

    full_name = f"VF-Start-V{args.version}-FULL.zip"
    update_name = f"VF_Start_V{args.version}_UPDATE.zip"
    zip_deterministic(out / full_name, full_files)
    zip_deterministic(out / update_name, {repair_name: repair_bytes})

    receipt = {
        "project_id": "P01",
        "mode": "formal-updater-safety-fix",
        "version": args.version,
        "source_version": args.source_version,
        "target_sha": args.target_sha,
        "target_tree": args.target_tree,
        "schema": old_schema,
        "baseline_atomic_target_files": len(old_target),
        "target_atomic_files": len(target_manifest),
        "removed_files": removed,
        "full_name": full_name,
        "full_bytes": (out / full_name).stat().st_size,
        "full_sha256": sha((out / full_name).read_bytes()),
        "update_name": update_name,
        "update_bytes": (out / update_name).stat().st_size,
        "update_sha256": sha((out / update_name).read_bytes()),
    }
    (out / "P01_V247500_FORMAL_ARTIFACT_RECEIPT.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
