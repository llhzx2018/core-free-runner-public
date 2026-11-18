#!/usr/bin/env bash
# P01 VF Start — exact-source *non-release* owner-trial builder.
# Build on a disposable GitHub-authorized cloud workstation, NOT CloudPanel / Production.
set -Eeuo pipefail
umask 077
export GIT_TERMINAL_PROMPT=0

SOURCE_REPO='llhzx2018/vf-start'
SOURCE_SHA='0e176a4f29e6f6445b6cc14d1db16c7ee05492a0'
OUTPUT_NAME='P01-v2.47.517-NEW-SITE-TRIAL.zip'
OUTPUT_DIR="${P01_TRIAL_OUTPUT_DIR:-$PWD}"
[[ -d "$OUTPUT_DIR" && ! -L "$OUTPUT_DIR" ]] || { echo 'BLOCKED: output directory is not a real directory.' >&2; exit 1; }
OUTPUT_DIR="$(cd -- "$OUTPUT_DIR" && pwd -P)"
[[ -n "$OUTPUT_DIR" && "$OUTPUT_DIR" != '/' ]] || { echo 'BLOCKED: unsafe output directory.' >&2; exit 1; }
[[ ! -e "$OUTPUT_DIR/$OUTPUT_NAME" && ! -L "$OUTPUT_DIR/$OUTPUT_NAME" ]] || { echo 'BLOCKED: trial ZIP already exists; refusing overwrite.' >&2; exit 1; }
[[ ! -e "$OUTPUT_DIR/$OUTPUT_NAME.receipt.json" && ! -L "$OUTPUT_DIR/$OUTPUT_NAME.receipt.json" ]] || { echo 'BLOCKED: receipt already exists; refusing overwrite.' >&2; exit 1; }
for cmd in git python3 php composer node npm sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED: missing build-host tool: $cmd" >&2; exit 1; }
done
# Developer host only. No package-manager installation on the user's CloudPanel site.
php -r 'if(PHP_VERSION_ID<80300) exit(1); foreach(["curl","mbstring","pdo","pdo_sqlite","pdo_mysql","zip","xml","gd","intl"] as $e) if(!extension_loaded($e)) exit(1);' || {
  echo 'BLOCKED: build-host PHP 8.3+ or required extensions missing.' >&2; exit 1;
}
[[ "$(node -p 'Number(process.versions.node.split(".")[0])>=20 ? "YES":"NO"')" == 'YES' ]] || { echo 'BLOCKED: Node 20+ required on build host.' >&2; exit 1; }

WORK="$(mktemp -d -t p01-v517-trial.XXXXXXXX)"
trap 'rm -rf -- "$WORK"' EXIT
SRC="$WORK/src"
mkdir -m 700 "$SRC"
# Use existing GitHub authorization, do not request or print a Personal Access Token.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh repo clone "$SOURCE_REPO" "$SRC" -- --quiet >&2
else
  git clone --quiet "https://github.com/$SOURCE_REPO.git" "$SRC" >&2 || {
    echo 'BLOCKED: no GitHub credentials on this build workstation. Authorize GitHub on the cloud workspace (not CloudPanel).' >&2
    exit 1
  }
fi
if ! git -C "$SRC" cat-file -e "$SOURCE_SHA^{commit}" 2>/dev/null; then
  git -C "$SRC" fetch --no-tags origin "$SOURCE_SHA" >&2
fi
git -C "$SRC" checkout --quiet --detach "$SOURCE_SHA"
[[ "$(git -C "$SRC" rev-parse HEAD)" == "$SOURCE_SHA" ]] || { echo 'BLOCKED: unexpected source checkout.' >&2; exit 1; }
[[ "$(cat "$SRC/VERSION")" == '2.47.517' && "$(cat "$SRC/src/VERSION.txt")" == '2.47.517' ]] || {
  echo 'BLOCKED: version identity changed.' >&2; exit 1
}
[[ -z "$(git -C "$SRC" status --porcelain=v1 --untracked-files=all)" ]] || { echo 'BLOCKED: dirty source.' >&2; exit 1; }

echo 'Building exact-source Composer/Vue/Vite full package on disposable cloud workstation…'
(cd "$SRC" && python3 -B scripts/build_p01_next_clean_full.py build \
  --source-sha "$SOURCE_SHA" --composer composer --output "$WORK/full.zip") >"$WORK/build.log" 2>&1 || {
    echo 'BLOCKED: clean FULL compilation failed. No trial ZIP was delivered.' >&2; tail -n 12 "$WORK/build.log" >&2; exit 1
  }
python3 -B "$SRC/scripts/build_p01_next_clean_full.py" verify --zip "$WORK/full.zip" >"$WORK/verified-clean.json"
python3 -B "$SRC/scripts/build_p01_next_cloudpanel_full.py" build \
  --source-zip "$WORK/full.zip" --output "$WORK/cloudpanel.zip" >"$WORK/cloudpanel.json"
python3 -B "$SRC/scripts/build_p01_next_cloudpanel_full.py" verify --zip "$WORK/cloudpanel.zip" >"$WORK/verified-cloudpanel.json"
PARENT_SHA="$(sha256sum "$WORK/cloudpanel.zip" | awk '{print $1}')"
python3 -B "$SRC/scripts/build_p01_next_owner_trial.py" build \
  --developer-zip "$WORK/cloudpanel.zip" --source-sha "$SOURCE_SHA" \
  --developer-sha256 "$PARENT_SHA" --output "$WORK/trial.zip" >"$WORK/trial.json"
python3 -B "$SRC/scripts/build_p01_next_owner_trial.py" verify \
  --zip "$WORK/trial.zip" --source-sha "$SOURCE_SHA" \
  --developer-sha256 "$PARENT_SHA" >"$WORK/verified-trial.json"

P01_TRIAL_SOURCE_SHA="$SOURCE_SHA" P01_TRIAL_PARENT_SHA="$PARENT_SHA" \
P01_TRIAL_TEMP_ZIP="$WORK/trial.zip" P01_TRIAL_OUTPUT_ZIP="$OUTPUT_DIR/$OUTPUT_NAME" \
python3 - <<'PY'
import hashlib, json, os, pathlib, shutil, zipfile
source=os.environ['P01_TRIAL_SOURCE_SHA']; parent=os.environ['P01_TRIAL_PARENT_SHA']
origin=pathlib.Path(os.environ['P01_TRIAL_TEMP_ZIP'])
target=pathlib.Path(os.environ['P01_TRIAL_OUTPUT_ZIP'])
receipt=target.with_name(target.name+'.receipt.json')
with zipfile.ZipFile(origin) as z:
    doc=json.loads(z.read('BUILD-MANIFEST.json'))
    assert doc['source_sha']==source
    assert doc['version']=='2.47.517'
    assert doc['readiness']=='OWNER_TRIAL_CANDIDATE'
    assert doc['developer_cloudpanel_sha256']==parent
    assert doc['trial_scope']=={
       'new_empty_site_only':True,
       'legacy_data_import_authorized':False,
       'old_site_cutover_authorized':False,
       'automatic_update_authorized':False,
       'formal_release_authorized':False,
    }
    assert len(z.namelist())>5900
    assert not any(x.startswith('private/') or x.startswith('.env') for x in z.namelist())
digest=hashlib.sha256(origin.read_bytes()).hexdigest()
data={
    'status':'OWNER_TRIAL_CANDIDATE_BUILT_AND_VERIFIED',
    'version':'2.47.517','source_sha':source,
    'sha256':digest,'bytes':origin.stat().st_size,
    'scope':doc['trial_scope'],
    'formal_release':False,
    'production_modified':False,
    'previous_real_machine_evidence':'https://github.com/llhzx2018/core-free-runner-public/actions/runs/44224946618',
}
# Exclusive-create: no accidental replacement of a prior trial or receipt.
try:
    with target.open('xb') as dest, origin.open('rb') as src:
        shutil.copyfileobj(src,dest,1024*1024)
    target.chmod(0o600)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    with receipt.open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n')
    receipt.chmod(0o600)
except BaseException:
    if target.exists(): target.unlink()
    raise
print('P01_TRIAL_HANDED_OFF=YES')
print('SOURCE_SHA='+source)
print('OUTPUT_ZIP='+str(target))
print('RECEIPT='+str(receipt))
print('ZIP_SHA256='+digest)
print('FORMAL_RELEASE=NO')
print('PRODUCTION_CHANGED=NO')
PY
