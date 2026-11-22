"""Build an isolated M05 candidate from the published UX10 bundle."""
import json
from pathlib import Path
import runpy
import stat
import sys
import zipfile


base, source, output, installer = map(Path, sys.argv[1:])
helpers = runpy.run_path(str(installer))
read_archive = helpers["read_verified_archive"]
digest = helpers["digest"]
baseline_sha = "11870e7fa741db637284f3ba3a82d35cee19e94f6675a76e09922ea99a8434f9"
before, original = read_archive(base, baseline_sha)
assert before == "0.1.0-m05-ux10-bootstrap-ux-failstop"
build = "0.1.0-m05-ux11-toolbox-lock"
payload = dict(original)
guards = ("lib/m05_environment_guard.py", "lib/m05_toolbox_backup_guard.py")
manifest_name = helpers["MANIFEST"]
for guard in guards:
    payload[guard] = (source / guard).read_bytes()
    assert payload[guard] != original[guard]
for name in ("BUILD_ID", "MODULE_BUILD_ID"):
    payload[name] = (build + "\n").encode()
manifest = json.loads(original[manifest_name])
manifest["module_build_id"] = build
manifest["files"] = {name: digest(raw) for name, raw in sorted(payload.items())
                     if name != manifest_name}
payload[manifest_name] = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
                          + "\n").encode()
assert {name for name in payload if payload[name] != original[name]} == {
    *guards, manifest_name, "BUILD_ID", "MODULE_BUILD_ID",
}
with zipfile.ZipFile(output, "x", allowZip64=False) as archive:
    for name, raw in sorted(payload.items()):
        entry = zipfile.ZipInfo("p07-m05/" + name, (2026, 1, 1, 0, 0, 0))
        entry.create_system = 3
        entry.external_attr = (stat.S_IFREG | (0o755 if name in helpers["BINS"] else 0o644)) << 16
        archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
output_sha = digest(output.read_bytes())
assert read_archive(output, output_sha) == (build, payload)
print(output_sha)
