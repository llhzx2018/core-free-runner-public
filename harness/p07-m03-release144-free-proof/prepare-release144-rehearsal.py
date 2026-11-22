"""Prepare and verify the next M03 identity for a local release rehearsal."""
from __future__ import annotations

import hashlib
import runpy
from pathlib import Path
import re
import sys


stage = Path(sys.argv[2]).resolve()
work = Path(sys.argv[1]).resolve()
assert work.is_dir() and work.parent == Path("/tmp") and work.name.startswith("p07-release-rehearsal.")
promoter = runpy.run_path(str(stage / "rehearse-release144-identity.py"))
promote = promoter["promote"]
candidate = stage / "rc4-bootstrap-final-proof.zip"
next_zip = work / "P07-M03-0.1.0-release144-rehearsal.zip"
receipt = promote(candidate, next_zip)
second = promote(candidate, work / "second.zip")
assert receipt == second and next_zip.read_bytes() == (work / "second.zip").read_bytes()
reference = promoter["trusted_zip"](candidate)
rehearsal = promoter["trusted_zip_final"](next_zip)
assert reference.keys() == rehearsal.keys()
assert {name for name in reference if reference[name] != rehearsal[name]} == promoter["ALLOW_CHANGE"]
bad_candidate = work / "candidate-altered.zip"
bad_candidate.write_bytes(candidate.read_bytes() + b"incorrect archive")
try:
    promote(bad_candidate, work / "must-not-exist.zip")
except promoter["FormalBuildBlocked"] as exc:
    assert str(exc) == "RC_SOURCE_SHA_MISMATCH"
    assert not (work / "must-not-exist.zip").exists()
else:
    raise AssertionError("Candidate alteration was accepted")

published_wrapper = stage / "public-release142-wrapper-reference.sh"
wrapper = published_wrapper.read_text(encoding="utf-8")
old_manifest = "cc3d90839bf71ea9139f5fc0d1c6cb12403b58e0"
next_manifest = receipt["runtime_manifest_blob"]
for key, old, new in (
    ("BUILD", "0.1.0-release142", "0.1.0-release144"),
    ("RELEASE", "p07-m03-v0.1.0-release142-20261120", "p07-m03-v0.1.0-release144-rehearsal"),
    ("ZIP_NAME", "P07-M03-0.1.0-release142.zip", next_zip.name),
    ("ZIP_SHA256", "dc6978463e8e73a224e7cccb2bdffe9710bc3bb478076b670703bbb164bda87e", receipt["sha256"]),
    ("RUNTIME_BLOB", old_manifest, next_manifest),
    ("INSTALLER_BLOB", "faadb1c6945b967ff5a06a730f2503f1ccd0de88", receipt["installer_blob"]),
):
    wrapper = promoter["replace_once"](wrapper, f"{key}='{old}'", f"{key}='{new}'")
for old, new in (
    ('!="0.1.0-release142": raise ValueError("build")', '!="0.1.0-release144": raise ValueError("build")'),
    ("p07-m03-release142.XXXXXXXX", "p07-m03-release144-rehearsal.XXXXXXXX"),
    ('/releases/assets/769843045"', '/releases/assets/0"'),
    ("非切换 release142。", "非切换 release144 本地演练。"),
    (f'    "0.1.0-release142":"{old_manifest}",',
     f'    "0.1.0-release142":"{old_manifest}",\n    "0.1.0-release144":"{next_manifest}",'),
):
    wrapper = promoter["replace_once"](wrapper, old, new)
assert all(mark in wrapper for mark in (
    'verified_m03_build "$m03_previous"',
    'mv -nT -- "$m03_previous" "$m03_archive"',
    'flock -x "$m03_lock_fd"',
    'P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh"',
))
assert not re.search(r'rm -rf -- "\$m03_previous"', wrapper)
(work / "wrapper-rehearsal.sh").write_text(wrapper, encoding="utf-8")
print("P07_RELEASE144_REHEARSAL_REPRODUCIBLE_IDENTITY_ONLY=PASS")
print("P07_RELEASE144_REHEARSAL_ALTERED_CANDIDATE_REJECTED=PASS")
print("P07_RELEASE144_REHEARSAL_ZIP_SHA256=" + hashlib.sha256(next_zip.read_bytes()).hexdigest())
