#!/usr/bin/env bash
# DEV ONLY: real immutable v015 FULL, native 3DB, media+token audit.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
old=369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e
target=e28dcbb0a28ad7e8308746881a81b1c739c86b01
old_zip_sha=538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73
[[ "$(git -C target rev-parse HEAD)" == "$target" ]] || exit 3
root="$RUNNER_TEMP/p08-v016-legacy-issued-$engine"
site="$RUNNER_TEMP/p08-v016-legacy-oldsite-$engine"
full="$RUNNER_TEMP/p08-v016-legacy-full-$engine/full-first.zip"
[[ ! -e "$root" && ! -e "$site" && -s "$full" ]] || exit 3
mkdir -m 700 "$root" "$site"
gh release download v0.1.15 -R llhzx2018/vf-adops \
 -p VF_AdOps_V0.1.15_FULL.zip -D "$root" >/dev/null
archive="$root/VF_AdOps_V0.1.15_FULL.zip"
printf '%s  %s\n' "$old_zip_sha" "$archive" | sha256sum -c --status
unzip -q "$archive" -d "$site"
unzip -p "$archive" FULL_MANIFEST.json > "$root/old-manifest.json"
python3 - "$root/old-manifest.json" "$old" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d['source_sha']==sys.argv[2] and d['target_version']=='0.1.15'
assert d['project_id']=='P08' and d['type']=='CLEAN_FULL_ONLY'
PY
echo "P08_V016_BRIDGE_$engine"_REAL_ORIGINAL_015_ZIP_SHA_SOURCE=PASS
mkdir -p "$site/tests/compatibility"
cp target/tests/test_install_sqlite_e2e.php target/tests/test_install_mysql_e2e.php "$site/tests/"
cp target/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
if [[ "$engine" == sqlite ]]; then
  php "$site/tests/test_install_sqlite_e2e.php"
else
  export P08_TEST_DB_CLEAN=p08_ci_016_old
  export P08_TEST_DB_DIRTY=p08_ci_016_old_dirty
  mariadb -h127.0.0.1 -uroot -p"$P08_TEST_DB_PASSWORD" \
    -e 'CREATE DATABASE p08_ci_016_old; CREATE DATABASE p08_ci_016_old_dirty; CREATE TABLE p08_ci_016_old_dirty.synthetic_dirty(id integer primary key);'
  php "$site/tests/test_install_mysql_e2e.php"
fi
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 42
python3 - "$site" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])/'storage/app/private/adops'
assets=root/'landing-assets'
assets.mkdir(mode=0o700,exist_ok=True)
file=assets/'00000000-0000-4000-8000-000000000001.png'
assert not file.exists()
file.write_bytes(b'\x89PNG\r\n\x1a\nCI-only-synthetic-user-image')
file.chmod(0o600)
token=root/'upgrade/github-read-token'
token.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
if token.is_symlink():raise SystemExit(9)
token.write_text('github_pat_'+'r'*45+'\n')
token.chmod(0o600)
PY
old_manifest_sha="$(sha256sum "$root/old-manifest.json" | cut -d' ' -f1)"
python3 -B target/scripts/build_atomic.py \
 --source target --output "$root/update.zip" \
 --source-version 0.1.15 --source-sha "$old" \
 --source-full-manifest-sha256 "$old_manifest_sha" \
 --previous-full-manifest "$root/old-manifest.json" \
 --target-version 0.1.16 --target-sha "$target" >/dev/null
unzip -tqq "$root/update.zip"
mkdir -m 700 "$root/target-full"
unzip -q "$full" -d "$root/target-full"
php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --audit "$site" "$full" "$root/update.zip"
echo "P08_V016_BRIDGE_$engine"_OLD_ISSUED_MEDIA_TOKEN_AUDIT=PASS
old_pointer="$(readlink "$site/current")"
old_image_hash="$(sha256sum "$site/storage/app/private/adops/landing-assets/00000000-0000-4000-8000-000000000001.png" | cut -d' ' -f1)"
set +e
printf 'wrong-synthetic-password\n' | php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --apply "$site" "$full" "$root/update.zip" CONFIRM_MEDIA_SAFE_V015_TO_V016 \
 > "$root/negative-out" 2> "$root/negative-err"
rc=$?
set -e
[[ "$rc" -eq 2 ]] || { echo 'P08_V016_BRIDGE_NEGATIVE_NONBLOCKING=FAIL'; exit 43; }
grep -Fxq 'P08_V016_BRIDGE_OWNER_AUTH_REFUSED' "$root/negative-err" || {
  grep -E '^P08_V016_BRIDGE_[A-Z_]+$' "$root/negative-err" || true
  echo "P08_V016_BRIDGE_$engine"_OWNER_REFUSAL=FAIL
  exit 44
}
[[ "$(readlink "$site/current")" == "$old_pointer" ]] || exit 45
[[ "$old_image_hash" == "$(sha256sum "$site/storage/app/private/adops/landing-assets/00000000-0000-4000-8000-000000000001.png" | cut -d' ' -f1)" ]] || exit 46
[[ ! -d "$site/storage/app/private/adops/legacy-media-bridge" ]] || exit 47
echo "P08_V016_BRIDGE_$engine"_INVALID_OWNER_NO_MUTATION=PASS
