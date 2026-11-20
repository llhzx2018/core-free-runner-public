#!/usr/bin/env bash
# P08 v014 development source-bound builder smoke; no official Release write.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
source_sha=deee2750aed1a8944d07c05a6efb03d6bf5e7eee
issued_sha=8b385fecd132a02ac79f5b67e670783e98997c3e
official_sha=f8075f065d1413c984f80ef7531242cfc894bf272e90f6d89282074f6617c1ec
[[ "$(git -C p08 rev-parse HEAD)" == "$source_sha" ]] || exit 3
[[ "$(cat p08/VERSION)" == 0.1.14 ]] || exit 3
work="$RUNNER_TEMP/p08-86-exact-source"
[[ ! -e "$work" ]] || exit 3
umask 077
mkdir -m 700 "$work"
log="$work/private.log"
phase(){
  local label="$1"; shift
  if "$@" >>"$log" 2>&1; then
    echo "P08_86_$label=PASS"
  else
    echo "P08_86_$label=FAIL"
    exit 41
  fi
}
phase DEV_CHECK bash p08/scripts/dev_check.sh
phase COMPOSER_LOCKED composer install --working-dir=p08 --no-dev --no-scripts \
  --prefer-dist --no-interaction --no-progress --optimize-autoloader
phase NPM_LOCKED npm ci --prefix p08 --ignore-scripts --no-audit --no-fund
phase VITE npm run build --prefix p08
phase OFFICIAL_013_FULL_DOWNLOAD gh release download v0.1.13 -R llhzx2018/vf-adops \
  -p VF_AdOps_V0.1.13_FULL.zip -D "$work"
archive="$work/VF_AdOps_V0.1.13_FULL.zip"
printf '%s  %s\n' "$official_sha" "$archive" | sha256sum -c --status || exit 42
unzip -p "$archive" FULL_MANIFEST.json > "$work/013-manifest.json"
python3 - "$work/013-manifest.json" "$issued_sha" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
assert m['project_id']=='P08' and m['repository']=='llhzx2018/vf-adops'
assert m['source_sha']==sys.argv[2] and m['target_version']=='0.1.13'
assert m['type']=='CLEAN_FULL_ONLY' and m['data_included'] is False
PY
previous="$(sha256sum "$work/013-manifest.json" | cut -d' ' -f1)"
echo "P08_86_ISSUED_013_SOURCE_VERIFIED=PASS"
phase FULL_DEV_BUILD python3 -B p08/scripts/build_full.py --source p08 \
 --output "$work/014-full.zip" --version 0.1.14 \
 --source-sha "$source_sha" --governance-root gov
phase ATOMIC_DEV_BUILD python3 -B p08/scripts/build_atomic.py --source p08 \
 --output "$work/014-update.zip" --source-version 0.1.13 \
 --source-sha "$issued_sha" --source-full-manifest-sha256 "$previous" \
 --previous-full-manifest "$work/013-manifest.json" \
 --target-version 0.1.14 --target-sha "$source_sha"
phase FINAL_ARCHIVE_READBACK python3 - "$work/014-full.zip" "$work/014-update.zip" "$source_sha" "$issued_sha" "$previous" <<'PY'
import json,sys,zipfile
full,atomic,target,source,manifest=sys.argv[1:]
with zipfile.ZipFile(full) as z:
    m=json.loads(z.read('FULL_MANIFEST.json'))
    files=z.namelist()
    assert m['type']=='CLEAN_FULL_ONLY'
    assert m['target_version']=='0.1.14' and m['source_sha']==target
    assert m['data_included'] is False
    assert 'VERSION' in files and z.read('VERSION')==b'0.1.14\n'
    assert all(not n.startswith(('storage/','tests/','scripts/'))
               for n in files)
    assert '.env' not in files
    assert 'public/p08-owner-first-forward.php' not in files
with zipfile.ZipFile(atomic) as z:
    m=json.loads(z.read('ATOMIC_MANIFEST.json'))
    files=z.namelist()
    assert m['type']=='P08_ATOMIC_CODE_ONLY_V1'
    assert m['source_version']=='0.1.13' and m['source_sha']==source
    assert m['source_full_manifest_sha256']==manifest
    assert m['target_version']=='0.1.14' and m['target_sha']==target
    assert m['schema_changes'] is False
    assert all(not n.startswith(('storage/','tests/','scripts/'))
               for n in files)
    assert '.env' not in files
    assert 'public/p08-owner-first-forward.php' not in files
PY
echo "P08_86_DEV_CANDIDATE_SOURCE_SHA=$source_sha"
echo "P08_86_OFFICIAL_RELEASE=NOT_AUTHORIZED"
echo "P08_86_FORMAL_13_DOMAIN_GATE=NOT_RUN"
echo "P08_86_PRODUCTION=UNCHANGED"
