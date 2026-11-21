#!/usr/bin/env bash
# DEV ONLY: original issued v015 + candidate v016 real SIGKILL and DB/media restore
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_R131_DISPOSABLE" == YES && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
old=369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e
target=fe99c4bcdbe8075824072ebf092c66d2ea55247c
old_zip_sha=538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73
[[ "$(git -C target rev-parse HEAD)" == "$target" ]] || exit 3
root="$RUNNER_TEMP/p08-v016-r131-$engine"
site="$RUNNER_TEMP/p08-r129-real-issued-r131-v016-$engine"
[[ ! -e "$root" && ! -e "$site" ]] || exit 3
mkdir -m 700 "$root" "$site"
gh release download v0.1.15 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.15_FULL.zip -D "$root" >/dev/null
oldZip="$root/VF_AdOps_V0.1.15_FULL.zip"
printf '%s  %s\n' "$old_zip_sha" "$oldZip" | sha256sum -c --status
unzip -q "$oldZip" -d "$site"
unzip -p "$oldZip" FULL_MANIFEST.json > "$root/old-manifest.json"
test "$(php -r '$v=json_decode(file_get_contents($argv[1]),true);echo $v["source_sha"]??"";' "$root/old-manifest.json")" = "$old"
mkdir -p "$site/tests/compatibility"
cp target/tests/test_install_sqlite_e2e.php target/tests/test_install_mysql_e2e.php "$site/tests/"
cp target/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
if [[ "$engine" == sqlite ]]; then
  php "$site/tests/test_install_sqlite_e2e.php"
else
  export P08_TEST_DB_CLEAN=p08_ci_016_fault
  export P08_TEST_DB_DIRTY=p08_ci_016_fault_dirty
  mariadb -h127.0.0.1 -uroot -p"$P08_TEST_DB_PASSWORD" -e \
    'CREATE DATABASE p08_ci_016_fault; CREATE DATABASE p08_ci_016_fault_dirty; CREATE DATABASE p08_ci_016_fault_restore; CREATE TABLE p08_ci_016_fault_dirty.synthetic_dirty(id integer primary key);'
  php "$site/tests/test_install_mysql_e2e.php"
fi
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 41
python3 - "$site" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])/'storage/app/private/adops'
assets=root/'landing-assets'; assets.mkdir(mode=0o700,exist_ok=True)
media=assets/'00000000-0000-4000-8000-000000000001.png'
media.write_bytes(b'\x89PNG\r\n\x1a\nCI-only-synthetic-r131-media')
media.chmod(0o600)
token=root/'upgrade/github-read-token';token.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
token.write_text('github_pat_'+'r'*45+'\n')
token.chmod(0o600)
PY
image="$(sha256sum "$site/storage/app/private/adops/landing-assets/00000000-0000-4000-8000-000000000001.png" | cut -d' ' -f1)"
token="$(sha256sum "$site/storage/app/private/adops/upgrade/github-read-token" | cut -d' ' -f1)"
npm ci --prefix target --ignore-scripts --no-fund --no-audit >/dev/null
npm run build --prefix target >/dev/null
composer --working-dir=target install --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader >/dev/null
python3 -B target/scripts/build_full.py --source "$GITHUB_WORKSPACE/target" --output "$root/target-full.zip" --version 0.1.16 --source-sha "$target" --governance-root "$GITHUB_WORKSPACE/gov" >/dev/null
mkdir -m 700 "$root/full"
unzip -q "$root/target-full.zip" -d "$root/full"
oldManifestSha="$(sha256sum "$root/old-manifest.json" | cut -d' ' -f1)"
python3 -B target/scripts/build_atomic.py --source target --output "$root/update.zip" --source-version 0.1.15 --source-sha "$old" --source-full-manifest-sha256 "$oldManifestSha" --previous-full-manifest "$root/old-manifest.json" --target-version 0.1.16 --target-sha "$target" >/dev/null
unzip -tqq "$root/update.zip"
php -l scripts/p08_v016_legacy_r131.php
set +e
php scripts/p08_v016_legacy_r131.php kill "$site" "$root/full" "$root/update.zip" "$target" > "$root/kill.log" 2> "$root/kill.err"
rc="$?"
set -e
if [[ "$rc" != 137 ]]; then
  cat "$root/kill.err" >&2
  echo "P08_V016_R131_$engine"_REAL_SIGKILL_EXIT_137=FAIL
  exit 42
fi
echo "P08_V016_R131_$engine"_REAL_SIGKILL_EXIT_137=PASS
[[ "$(readlink "$site/current")" == "releases/$target" ]] || exit 43
test -s "$site/storage/app/private/adops/maintenance/maintenance.json"
php scripts/p08_v016_legacy_r131.php recover "$site" "$root/full" "$root/update.zip" "$target"
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 44
test ! -e "$site/storage/app/private/adops/maintenance/maintenance.json"
[[ "$(sha256sum "$site/storage/app/private/adops/landing-assets/00000000-0000-4000-8000-000000000001.png" | cut -d' ' -f1)" == "$image" ]] || exit 45
[[ "$(sha256sum "$site/storage/app/private/adops/upgrade/github-read-token" | cut -d' ' -f1)" == "$token" ]] || exit 46
echo "P08_V016_R131_$engine"_ORIGINAL_015_MEDIA_SAFE_RECOVERY=PASS
