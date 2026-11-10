#!/usr/bin/env bash
# P07 release142 Owner trial bootstrap. PUBLIC-SAFE: no private source/secret.
# Requires an authorized HTTPS prebuilt candidate package and its SHA256.
# No git, apt, GitHub login, automatic migration, DNS or source-site writes.
set -Eeuo pipefail
umask 077
fail() { printf 'P07_OWNER142_BLOCKED=%s\n' "$1" >&2; exit 13; }
need() { command -v "$1" >/dev/null 2>&1 || fail "MISSING_$1_NO_CHANGES"; }
# The public nonformal Owner trial is pinned by immutable GitHub asset ID
# and digest, so a single no-Git SSH command can install without hand-entered
# environment variables. Explicit overrides remain available for test runners.
# This nonformal trial's immutable asset ID and SHA-256 are verified.
# No Git, manual download or owner-provided hash is needed on CP2.
url="${P07_TRIAL_URL:-}"
sha="${P07_TRIAL_SHA256:-}"
[[ -n "$url" && -n "$sha" ]] || fail "DISTRIBUTION_NOT_READY_NO_CHANGES"
[[ "$url" =~ ^https://[^[:space:]]+$ ]] || fail "HTTPS_PACKAGE_URL_REQUIRED_NO_CHANGES"
[[ ! "$url" =~ ^https://[^/]+@ ]] || fail "EMBEDDED_CREDENTIAL_REFUSED"
[[ "$sha" =~ ^[0-9a-f]{64}$ ]] || fail "SHA256_REQUIRED_NO_CHANGES"
[[ "$(id -u)" == 0 ]] || fail "ROOT_REQUIRED_NO_CHANGES"
for command_name in curl sha256sum python3 bash; do need "$command_name"; done
target=/opt/vf-server-ops-rc142
previous=/opt/vf-server-ops-rc142.previous
binary=/usr/local/bin/vfops-rc142
[[ -f /opt/vf-server-ops/BUILD_ID ]] || fail "RELEASE115_NOT_INSTALLED_NO_CHANGES"
old="$(cat /opt/vf-server-ops/BUILD_ID)"
[[ "$old" == "0.1.0-release115" ]] || fail "STABLE_BUILD_UNEXPECTED_NO_CHANGES"
# A successful first installation creates a dedicated slot. Re-running the
# same trusted bootstrap is a NO-CHANGE success, not a failed installation.
# A partial, altered, interrupted, or mismatched slot still fails closed.
if [[ -d "$target" && ! -L "$target" && -f "$target/BUILD_ID" &&
      ! -L "$target/BUILD_ID" && -x "$target/bin/vfops-user" &&
      -L "$binary" &&
      "$(readlink -- "$binary" 2>/dev/null || true)" == "$target/bin/vfops-user" &&
      "$(cat "$target/BUILD_ID")" == "0.1.0-release142" &&
      "$(NO_COLOR=1 "$binary" --build-id 2>/dev/null || true)" == "0.1.0-release142" &&
      ! -e "$previous" && ! -L "$previous" &&
      ! -e /opt/vf-server-ops-rc142.new &&
      ! -L /opt/vf-server-ops-rc142.new ]]; then
  printf '%s\n' \
    'P07_OWNER142_ALREADY_INSTALLED=YES' \
    "P07_OWNER142_RUN_COMMAND=$binary" \
    'P07_OWNER142_STABLE_VFOPS_UNCHANGED=YES' \
    'P07_OWNER142_MIGRATION_AUTORUN=NO' \
    'P07_OWNER142_DNS_CHANGED=NO'
  exit 0
fi
for slot in "$target" "$previous" /opt/vf-server-ops-rc142.new "$binary"; do
  [[ ! -e "$slot" && ! -L "$slot" ]] || fail "TEST_SLOT_ALREADY_OCCUPIED_NO_CHANGES"
done
work="$(mktemp -d -t p07-owner142.XXXXXXXX)" || fail "TEMP_DIR_UNAVAILABLE_NO_CHANGES"
trap 'rm -rf -- "$work"' EXIT
curl_headers=()
case "$url" in
  https://api.github.com/*) curl_headers=(-H 'Accept: application/octet-stream') ;;
esac
curl -fsSL --proto '=https' --proto-redir '=https' --connect-timeout 15 \
  --max-time 300 --retry 2 "${curl_headers[@]}" "$url" -o "$work/bundle.tar.gz" ||
  fail "PACKAGE_DOWNLOAD_FAILED_NO_CHANGES"
printf '%s  %s\n' "$sha" "$work/bundle.tar.gz" |
  sha256sum --check --status || fail "SHA256_MISMATCH_NO_CHANGES"
python3 -B - "$work" <<'PY' || fail "CANDIDATE_ARCHIVE_INVALID_NO_CHANGES"
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

work = Path(sys.argv[1])
root = work / "candidate"
def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

with tarfile.open(work / "bundle.tar.gz", "r:gz") as archive:
    entries = archive.getmembers()
    if not entries or len(entries) > 20000:
        raise SystemExit(13)
    seen = set()
    total = 0
    for entry in entries:
        path = entry.name
        parts = PurePosixPath(path).parts
        if (not parts or parts[0] != "candidate" or path.startswith("/")
                or "\\" in path or any(p in (".", "..") for p in parts)
                or not (entry.isdir() or entry.isfile()) or path in seen):
            raise SystemExit(13)
        seen.add(path)
        if entry.isfile():
            total += entry.size
            if entry.size > 256 * 1024 * 1024 or total > 512 * 1024 * 1024:
                raise SystemExit(13)
    for entry in entries:
        dst = work / entry.name
        if entry.isdir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(entry) as src, dst.open("xb") as out:
                while True:
                    chunk = src.read(1048576)
                    if not chunk:
                        break
                    out.write(chunk)

att = json.loads((root / "candidate_attestation.json").read_text("utf-8"))
if (att.get("status") != "FORMAL_STAGING_NOT_PUBLISHED" or
        att.get("product_build") != "0.1.0-release142" or
        not re.fullmatch(r"[0-9a-f]{40}", att.get("product_source_sha", ""))):
    raise SystemExit(13)
runtime = (root / "dist/p07/0.1.0/overlay/RUNTIME.gitblob").read_bytes()
if git_blob(runtime) != att.get("runtime_manifest_blob"):
    raise SystemExit(13)
wrapper = (root / "installers/p07.sh").read_text("utf-8")
final = (root / "installers/p07-final.sh").read_bytes()
pins = re.findall(r'^EXPECTED_BLOB="([0-9a-f]{40})"$', wrapper, re.M)
if len(pins) != 1 or pins[0] != git_blob(final):
    raise SystemExit(13)
if b'EXPECTED_BUILD_ID="0.1.0-release142"' not in final:
    raise SystemExit(13)
PY
P07_INSTALL_DIR="$target" \
P07_PREVIOUS_DIR="$previous" \
P07_BIN_LINK="$binary" \
P07_NO_EXEC=1 \
P07_PUBLIC_ROOT="file://$work/candidate" \
  bash "$work/candidate/installers/p07.sh" ||
  fail "CANDIDATE_INSTALL_FAILED_CHECK_TEST_SLOT"
[[ -x "$binary" || -L "$binary" ]] || fail "CANDIDATE_BINARY_MISSING"
[[ "$("$binary" --build-id)" == "0.1.0-release142" ]] || fail "BUILD_READBACK_MISMATCH"
[[ "$(cat /opt/vf-server-ops/BUILD_ID)" == "$old" ]] || fail "STABLE_BUILD_CHANGED_STOP"
printf '%s\n' \
  'P07_OWNER142_TEST_INSTALL=PASS' \
  "P07_OWNER142_RUN_COMMAND=$binary" \
  'P07_OWNER142_STABLE_VFOPS_UNCHANGED=YES' \
  'P07_OWNER142_MIGRATION_AUTORUN=NO' \
  'P07_OWNER142_DNS_CHANGED=NO'
