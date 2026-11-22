"""Prepare a reproducible, local-only update from the official P07-M03 ZIP."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import stat
import sys
import zipfile


old_build = "0.1.0-release144"
new_build = "0.1.0-release145"
old_sha = "eeddddad32814542d620e13ec46d9567e377af6ef4639cb17e78d26acc05af5d"
old_manifest = "5dd59de44fa024add3e6317b6dc8617fb92df91f"
old_installer = "3f2ba5ed59015cffc3327418699409bbfb8ab1fe"
paths = {
    "bin/vfops-migrate-ui": "a245fe27b59111a44bf9ac93fe4ed82b7b461831",
    "components/p07-m03-failed-task-ux.sh": "01e93f6cb4a3d16bf7b8e97a374eedf45d6148d9",
    "components/p07-m03-safe-batch-ui.sh": "f00c04f85d6411eb25e461bb73bd3cbb43554fcf",
}
policy = runpy.run_path(str(Path(__file__).with_name("rehearse-release144-identity.py")))
blob = policy["git_blob"]
digest = policy["digest"]
replace = policy["replace_once"]
validate = policy["validate_manifest"]
overlay, manifest, build_marker, installer = (policy[name] for name in
                                               ("OVERLAY", "MANIFEST", "MARKER", "INSTALLER"))


def prepare(official: Path, source: Path, result: Path, wrapper: Path) -> None:
    assert digest(official.read_bytes()) == old_sha, "Official ZIP digest mismatch"
    original = policy["trusted_zip_final"](official)
    names = validate(original)
    assert original[build_marker] == (old_build + "\n").encode()
    assert blob(original[manifest]) == old_manifest
    assert blob(original[installer]) == old_installer
    updated = dict(original)
    for path, expected in paths.items():
        content = (source / path).read_bytes()
        assert blob(content) == expected, path
        updated[overlay + path] = content
    updated[build_marker] = (new_build + "\n").encode()
    updated[manifest] = ("\n".join(
        f"{blob(updated[overlay + path])}  {path}" for path in names) + "\n").encode("ascii")
    next_manifest = blob(updated[manifest])
    embedded = original[installer].decode()
    embedded = replace(embedded, f'EXPECTED_BUILD_ID="{old_build}"', f'EXPECTED_BUILD_ID="{new_build}"')
    embedded = replace(embedded, f'RUNTIME_MANIFEST_BLOB="{old_manifest}"',
                        f'RUNTIME_MANIFEST_BLOB="{next_manifest}"')
    updated[installer] = embedded.encode()
    assert validate(updated) == names
    expected_changes = {manifest, build_marker, installer} | {overlay + path for path in paths}
    assert {path for path in original if original[path] != updated[path]} == expected_changes
    result.mkdir(mode=0o700, exist_ok=True)
    output = result / f"P07-M03-{new_build}.zip"
    with zipfile.ZipFile(output, "x", allowZip64=False) as archive:
        for name, raw in sorted(updated.items()):
            entry = zipfile.ZipInfo(name, (2026, 11, 22, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    assert policy["trusted_zip_final"](output) == updated
    sha = digest(output.read_bytes())
    next_installer = blob(updated[installer])
    reference = wrapper.read_text(encoding="utf-8")
    for old, new in (
        (f"BUILD='{old_build}'", f"BUILD='{new_build}'"),
        ("RELEASE='p07-m03-v0.1.0-release144-20261122'", "RELEASE='p07-m03-v0.1.0-release145-20261122'"),
        (f"ZIP_NAME='P07-M03-{old_build}.zip'", f"ZIP_NAME='{output.name}'"),
        (f"ZIP_SHA256='{old_sha}'", f"ZIP_SHA256='{sha}'"),
        (f"RUNTIME_BLOB='{old_manifest}'", f"RUNTIME_BLOB='{next_manifest}'"),
        (f"INSTALLER_BLOB='{old_installer}'", f"INSTALLER_BLOB='{next_installer}'"),
        (f'!="{old_build}": raise ValueError("build")', f'!="{new_build}": raise ValueError("build")'),
        ("p07-m03-release144.XXXXXXXX", "p07-m03-release145.XXXXXXXX"),
        ("非切换 release144。", "非切换 release145。"),
        (f'    "{old_build}":"{old_manifest}",',
         f'    "{old_build}":"{old_manifest}",\n    "{new_build}":"{next_manifest}",'),
        ("/releases/assets/778474753", "/releases/assets/0"),
    ):
        reference = replace(reference, old, new)
    (result / "candidate-wrapper.sh").write_text(reference, encoding="utf-8", newline="\n")
    receipt = {"sha256": sha, "size": output.stat().st_size,
               "runtime_manifest_blob": next_manifest, "installer_blob": next_installer}
    (result / "package.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    prepare(*(Path(arg) for arg in sys.argv[1:]))
