"""P07-M05 generic-init: isolated nonpublic candidate from official UX12 ZIP."""
from pathlib import Path
import json
import runpy
import stat
import sys
import zipfile

base, source, output, atomic = map(Path, sys.argv[1:])
helpers = runpy.run_path(str(atomic))
official_sha = "424ff9b90d9ce1c5d2b8de9773fb3350d959d8a5f030580e568918a7bc66d279"
before, original = helpers["read_verified_archive"](base, official_sha)
assert before == "0.1.0-m05-ux12-apt-failstop", before

build = "0.1.0-m05-ux13-provider-neutral"
patches = (
    "bin/vfops-init-ui",
    "lib/m05_environment_guard.py",
    "lib/m05_owner_trial_guard.py",
    "lib/m05_passive_image_helpers.py",
)
payload = dict(original)
for item in patches:
    path = source / item
    assert path.is_file() and not path.is_symlink()
    new_bytes = path.read_bytes()
    assert new_bytes and new_bytes != original.get(item), item
    payload[item] = new_bytes
for item in ("BUILD_ID", "MODULE_BUILD_ID"):
    payload[item] = (build + "\n").encode("ascii")

name = helpers["MANIFEST"]
record = json.loads(original[name])
record["module_build_id"] = build
record["files"] = {
    item: helpers["digest"](raw)
    for item, raw in sorted(payload.items()) if item != name
}
payload[name] = (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)
                 + "\n").encode("utf-8")
expected_changes = set(patches) | {"BUILD_ID", "MODULE_BUILD_ID", name}
assert {item for item, data in payload.items() if data != original.get(item)} == expected_changes

with zipfile.ZipFile(output, mode="x", allowZip64=False) as packed:
    for item, raw in sorted(payload.items()):
        zi = zipfile.ZipInfo("p07-m05/" + item, (2026, 1, 1, 0, 0, 0))
        zi.create_system = 3
        zi.external_attr = (
            stat.S_IFREG | (0o755 if item in helpers["BINS"] else 0o644)
        ) << 16
        packed.writestr(zi, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
candidate_sha = helpers["digest"](output.read_bytes())
verified_build, verified_payload = helpers["read_verified_archive"](output, candidate_sha)
assert verified_build == build and verified_payload == payload
print("M05_OFFICIAL_UX12_TO_CANDIDATE_PACKAGE=PASS")
print("M05_DEV_CANDIDATE_SHA256=" + candidate_sha)
