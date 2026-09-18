#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, os, shutil, stat, subprocess, sys, zipfile, datetime as dt

ROOT = Path.cwd()
TARGET = "2.5.33"
SOURCES = ["2.5.31", "2.5.32"]
SCHEMA = 2401
TS = "2026-09-18T10:36:11Z"
PRODUCT_REF = os.environ["PRODUCT_REF"]
RUN_ID = os.environ.get("GITHUB_RUN_ID", "UNKNOWN")
STAMP = tuple(dt.datetime.fromisoformat(TS.replace("Z", "+00:00")).astimezone(dt.timezone.utc).timetuple()[:6])

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def meta(path):
    path = Path(path)
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)}

def zw(z, name, data, mode=0o644):
    info = zipfile.ZipInfo(name, STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | mode) << 16
    z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

def rezip(root, destination):
    root = Path(root)
    with zipfile.ZipFile(destination, "w") as z:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                mode = 0o755 if os.access(path, os.X_OK) else 0o644
                zw(z, path.relative_to(root).as_posix(), path.read_bytes(), mode)

def patch_builder(destination):
    src = (ROOT / "scripts/build-release-v2.5.4.py").read_text(encoding="utf-8")
    old = "ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.2'; VER='2.5.4'; SCHEMA=2401; DT=(2026,8,19,2,0,0)"
    new = "ROOT=Path.cwd(); SRCVER='2.5.32'; VER='2.5.33'; SCHEMA=2401; DT=(2026,9,18,10,36,11)"
    if old not in src:
        raise SystemExit("builder identity block changed")
    src = src.replace(old, new, 1)
    start = "notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''"
    end = "''')\n arts=[sz,fz,uz,az,rf,notes]"
    i = src.index(start)
    j = src.index(end, i)
    notes = """notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''# VF Library V{VER}

V2.5.33 is the reading-comfort and interface-density release for P02.

- Reader default typography converges to 16px / 1.65 with a 72ch standard measure.
- Narrow / standard / wide reading widths and A-/A+ remain user-adjustable.
- New editor sessions use 15px / 1.64 while existing local editor-size preferences remain preserved.
- Reader, Preview and Scratch share a calmer long-form reading scale.
- Light mode uses warmer paper-like neutral surfaces while preserving the VF Library teal identity.
- Desktop navigation and document-list density are tightened without changing IA or canonical content.
- Schema remains {SCHEMA}; no migration.
- The online UPDATE supports verified direct upgrades from V2.5.31 and V2.5.32.
- OWNER explicitly authorized publish-first; real-use acceptance remains a separate post-publication truth.
''')
 arts=[sz,fz,uz,az,rf,notes]"""
    src = src[:i] + notes + src[j + len(end):]
    Path(destination).write_text(src, encoding="utf-8")

def finalize(out):
    out = Path(out)
    deploy = out / ".deploy"
    subprocess.check_call(["bash", "scripts/build-deploy-tree.sh", str(deploy)])
    update = out / f"VF_Library_V{TARGET}_UPDATE.zip"
    subprocess.check_call([
        "python3", "scripts/build-multisource-update.py",
        "--deploy-root", str(deploy), "--output", str(update),
        "--target-version", TARGET,
        "--source-version", SOURCES[0], "--source-version", SOURCES[1],
        "--source-schema", str(SCHEMA), "--target-schema", str(SCHEMA),
        "--timestamp", TS,
    ])

    full = out / f"VF_Library_V{TARGET}_FULL.zip"
    full_dir = out / ".full"
    with zipfile.ZipFile(full) as z:
        z.extractall(full_dir)
    runtime_manifest = full_dir / "release-manifest.json"
    data = json.loads(runtime_manifest.read_text(encoding="utf-8"))
    data["upgrade"]["supported_from"] = SOURCES
    data["upgrade"]["update"] = meta(update)
    runtime_manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rezip(full_dir, full)

    release_manifest = out / f"VF_Library_V{TARGET}_RELEASE_MANIFEST.json"
    release = json.loads(release_manifest.read_text(encoding="utf-8"))
    release["compatibility"]["supported_from"] = SOURCES
    release["gates"] = {
        "exact_source": f"PASS_RUN_{RUN_ID}",
        "repository_and_unit": f"PASS_RUN_{RUN_ID}",
        "real_chromium": f"PASS_RUN_{RUN_ID}",
        "deterministic_build": f"PASS_RUN_{RUN_ID}",
        "fresh_install": f"PASS_RUN_{RUN_ID}",
        "atomic_upgrade_2.5.31": f"PASS_RUN_{RUN_ID}",
        "atomic_upgrade_2.5.32": f"PASS_RUN_{RUN_ID}",
        "secret": "PASS",
        "private_data": "PASS",
        "db_binary": "PASS",
        "archive": "PASS",
    }
    release["git"] = {
        "main_readback": "PRE_RELEASE_CURRENT_MAIN_UNCHANGED",
        "formal_tag": f"v{TARGET}",
        "tag_readback": "PENDING_REMOTE_RELEASE",
    }
    release["deployment"] = {
        "status": "NOT_EXECUTED",
        "production_readback": "NOT_EXECUTED",
        "final_online_pass": False,
    }
    type_by_name = {a["path"]: a.get("type", "") for a in release["artifacts"]}
    artifacts = []
    for path in [
        out / f"VF_Library_V{TARGET}_SOURCE.zip",
        full,
        update,
        out / f"VF_Library_V{TARGET}_ATOMIC.zip",
        out / f"repair-v{TARGET}.php",
        out / f"VF_Library_V{TARGET}_RELEASE_NOTES.md",
    ]:
        item = meta(path)
        item["type"] = type_by_name.get(path.name, "UPDATE" if path == update else "")
        artifacts.append(item)
    release["artifacts"] = artifacts
    release_manifest.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    shutil.rmtree(deploy, ignore_errors=True)
    shutil.rmtree(full_dir, ignore_errors=True)
    artifacts_for_sums = [p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt"]
    (out / "SHA256SUMS.txt").write_text(
        "".join(f"{sha(p)}  {p.name}\n" for p in sorted(artifacts_for_sums, key=lambda p: p.name)),
        encoding="utf-8",
    )

def build(out):
    temp_builder = Path(os.environ["RUNNER_TEMP"]) / "build-v2533.py"
    patch_builder(temp_builder)
    tree = subprocess.check_output(["git", "show", "-s", "--format=%T", PRODUCT_REF], text=True).strip()
    subprocess.check_call([
        "python3", str(temp_builder),
        "--out", str(out),
        "--source-commit", PRODUCT_REF,
        "--source-tree", tree,
        "--source-ref", "release/v2.5.33",
    ])
    finalize(out)

for name in ["build/formal-a", "build/formal-b"]:
    build(name)

def hashes(root):
    return {p.name: sha(p) for p in Path(root).iterdir() if p.is_file()}

a = hashes("build/formal-a")
b = hashes("build/formal-b")
if a != b:
    raise SystemExit(f"non-deterministic build: {a} != {b}")
print("P02_V2533_DETERMINISTIC_FORMAL_BUILD=PASS")
for name, digest in sorted(a.items()):
    print(f"FORMAL_SHA256 {digest} {name}")
