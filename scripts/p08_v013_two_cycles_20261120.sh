#!/usr/bin/env bash
# ONE-OFF public-safe machine proof. No Owner, Production or remote source mutation.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES ]] || exit 3
[[ "$(id -u)" != 0 && -d "$RUNNER_TEMP" ]] || exit 3
[[ "$(realpath "$RUNNER_TEMP")" == "$RUNNER_TEMP" ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
main_sha=98f219f386eb2a29b6ba75a2cf2994cc4057af85
official_sha=8b385fecd132a02ac79f5b67e670783e98997c3e
official_zip_sha=f8075f065d1413c984f80ef7531242cfc894bf272e90f6d89282074f6617c1ec
[[ "$(git -C p08 rev-parse HEAD)" == "$main_sha" ]] || exit 3
[[ "$(cat p08/VERSION)" == "0.1.13" ]] || exit 3
work="$RUNNER_TEMP/p08-v013-2cycle-$engine"
site="$RUNNER_TEMP/p08-r129-real-issued-r131-r155-$engine-two-cycle"
[[ ! -e "$work" && ! -e "$site" ]] || exit 3
umask 077
mkdir -m 700 "$work"
log="$work/private.log"
phase() {
  local name="$1"; shift
  if "$@" >> "$log" 2>&1; then
    printf 'P08_V013_TWO_CYCLE_%s_%s=PASS\n' "$engine" "$name"
  else
    printf 'P08_V013_TWO_CYCLE_%s_%s=FAIL\n' "$engine" "$name"
    exit 40
  fi
}
phase OFFICIAL_DOWNLOAD gh release download v0.1.13 -R llhzx2018/vf-adops \
  -p VF_AdOps_V0.1.13_FULL.zip -D "$work"
archive="$work/VF_AdOps_V0.1.13_FULL.zip"
echo "$official_zip_sha  $archive" | sha256sum --check --status || exit 41
unzip -p "$archive" FULL_MANIFEST.json > "$work/013-manifest.json"
python3 - "$work/013-manifest.json" "$official_sha" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
assert m["type"]=="CLEAN_FULL_ONLY"
assert m["repository"]=="llhzx2018/vf-adops"
assert m["source_sha"]==sys.argv[2] and m["target_version"]=="0.1.13"
assert m["data_included"] is False
PY
echo "P08_V013_TWO_CYCLE_$engine"_PUBLISHED_SOURCE_IDENTITY=PASS
base_digest="$(sha256sum "$work/013-manifest.json" | cut -d' ' -f1)"
phase COMPOSER_INSTALL composer install --working-dir=p08 --no-dev --no-scripts \
  --prefer-dist --no-interaction --no-progress --optimize-autoloader
phase NPM_CI npm ci --prefix p08 --ignore-scripts --no-audit --no-fund
phase VITE npm run build --prefix p08
git -C p08 config user.name "P08 Ephemeral Machine Fixture"
git -C p08 config user.email "p08-fixture@invalid.example"
new_fixture_commit() {
  local old="$1" newer="$2"
  python3 - "$old" "$newer" <<'PY'
from pathlib import Path
import sys
old,new=sys.argv[1:]
version=Path('p08/VERSION')
note=Path('p08/public/p08-install-build.txt')
assert version.read_text().strip()==old
body=note.read_text()
assert old in body,("installer note lacks expected version",old)
version.write_text(new+'\n')
note.write_text(body.replace(old,new).replace("DEVELOPMENT_CANDIDATE_NOT_ISSUED","ISOLATED_NOT_RELEASED"))
PY
  phase COMMIT_STAGE git -C p08 add VERSION public/p08-install-build.txt
  phase COMMIT_SAVE git -C p08 commit -m "test-only version $newer (never pushed)"
}
new_fixture_commit 0.1.13 0.1.14
sha014="$(git -C p08 rev-parse HEAD)"
phase FULL_014 python3 -B p08/scripts/build_full.py \
  --source p08 --output "$work/014-full.zip" --version 0.1.14 \
  --source-sha "$sha014" --governance-root gov
unzip -p "$work/014-full.zip" FULL_MANIFEST.json > "$work/014-manifest.json"
phase UPDATE_013_TO_014 python3 -B p08/scripts/build_atomic.py \
  --source p08 --output "$work/014-update.zip" \
  --source-version 0.1.13 --source-sha "$official_sha" \
  --source-full-manifest-sha256 "$base_digest" \
  --previous-full-manifest "$work/013-manifest.json" \
  --target-version 0.1.14 --target-sha "$sha014"
digest014="$(sha256sum "$work/014-manifest.json" | cut -d' ' -f1)"
new_fixture_commit 0.1.14 0.1.15
sha015="$(git -C p08 rev-parse HEAD)"
phase FULL_015 python3 -B p08/scripts/build_full.py \
  --source p08 --output "$work/015-full.zip" --version 0.1.15 \
  --source-sha "$sha015" --governance-root gov
phase UPDATE_014_TO_015 python3 -B p08/scripts/build_atomic.py \
  --source p08 --output "$work/015-update.zip" \
  --source-version 0.1.14 --source-sha "$sha014" \
  --source-full-manifest-sha256 "$digest014" \
  --previous-full-manifest "$work/014-manifest.json" \
  --target-version 0.1.15 --target-sha "$sha015"
echo "P08_V013_TWO_CYCLE_$engine"_NO_RELEASE_OR_DISTRIBUTION_WRITE=CONFIRMED
mkdir -m 700 "$site"
phase FULL_EXTRACT unzip -q "$archive" -d "$site"
mkdir -p "$site/tests/compatibility" "$site/tests/fixtures"
cp p08/tests/test_install_sqlite_e2e.php p08/tests/test_install_mysql_e2e.php "$site/tests/"
cp p08/tests/fixtures/create_ci_databases.php "$site/tests/fixtures/"
cp p08/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
if [[ "$engine" == sqlite ]]; then
  phase REAL_FIRST_INSTALL php "$site/tests/test_install_sqlite_e2e.php"
else
  phase NATIVE_DB_CREATE php "$site/tests/fixtures/create_ci_databases.php"
  phase REAL_FIRST_INSTALL php "$site/tests/test_install_mysql_e2e.php"
fi
[[ "$(readlink "$site/current")" == "releases/$official_sha" ]] || exit 42
token="$site/storage/app/private/adops/upgrade/github-read-token"
media="$site/storage/app/private/adops/r202-media-proof.bin"
mkdir -p "$(dirname "$token")"
printf 'github_pat_%050d\n' 0 > "$token"
printf 'P08_ISOLATED_MEDIA_%s\n' "$engine" > "$media"
chmod 0600 "$token" "$media"
token_sha="$(sha256sum "$token" | cut -d' ' -f1)"
media_sha="$(sha256sum "$media" | cut -d' ' -f1)"
phase FIRST_NATIVE_ATOMIC env P08_R205_CHAINED=YES php \
  p08/tests/compatibility/r205_chained_atomic_apply.php \
  "$site" "$official_sha" "$base_digest" "$work/014-update.zip" "$sha014" 0.1.14
[[ "$(readlink "$site/current")" == "releases/$sha014" ]] || exit 43
phase SECOND_NATIVE_ATOMIC env P08_R205_CHAINED=YES php \
  p08/tests/compatibility/r205_chained_atomic_apply.php \
  "$site" "$sha014" "$digest014" "$work/015-update.zip" "$sha015" 0.1.15
[[ "$(readlink "$site/current")" == "releases/$sha015" ]] || exit 44
[[ "$(cat "$site/current/VERSION")" == 0.1.15 ]] || exit 44
[[ "$(sha256sum "$token" | cut -d' ' -f1)" == "$token_sha" ]] || exit 45
[[ "$(sha256sum "$media" | cut -d' ' -f1)" == "$media_sha" ]] || exit 45
echo "P08_V013_TWO_CYCLE_$engine"_SAME_SITE_TWO_REAL_NATIVE_ATOMICS=PASS
echo "P08_V013_TWO_CYCLE_$engine"_PRIVATE_TOKEN_MEDIA_PRESERVED=PASS
echo "P08_V013_TWO_CYCLE_$engine"_AUTHENTICATED_HTTPS_BROWSER=NOT_RUN
echo "P08_V013_TWO_CYCLE_$engine"_NATIVE_FAILURE_ROLLBACK=NOT_RUN
echo "P08_V013_TWO_CYCLE_$engine"_FORMAL_RELEASE_READY=NO
