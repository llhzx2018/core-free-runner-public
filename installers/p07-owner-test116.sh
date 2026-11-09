#!/usr/bin/env bash
# P07 release116 OWNER test: fetch exact PRIVATE product using EXISTING
# GitHub credentials and build a separate, non-production install on CP2.
# Public bootstrap contains NO private product files, tokens or secrets.
set -Eeuo pipefail
umask 077

PRODUCT_SHA='e3c21c05b544c251f9474bd6b0b59c2ff8207ccd'
PRODUCT_BRANCH='fix/p07-versioned-laravel-external-20261108'
BASE_SHA='7c3f685465b0da9a4414a13b629ea599006019ae'
EXPECTED_BUILD='0.1.0-release116'
CARE_BUILD='0.1.0-rc83'
TARGET='/opt/vf-server-ops-rc293'
PREVIOUS='/opt/vf-server-ops-rc293.previous'
NEW_TREE='/opt/vf-server-ops-rc293.new'
BIN='/usr/local/bin/vfops-rc293'

note() { printf 'P07_TEST116_%s\n' "$1"; }
die() { note "$1" >&2; exit 13; }
command -v git >/dev/null || die 'GIT_MISSING_NO_CHANGES'
command -v python3 >/dev/null || die 'PYTHON_MISSING_NO_CHANGES'
command -v curl >/dev/null || die 'CURL_MISSING_NO_CHANGES'
command -v tar >/dev/null || die 'TAR_MISSING_NO_CHANGES'
command -v sha256sum >/dev/null || die 'SHA256SUM_MISSING_NO_CHANGES'
[[ "$(id -u)" == 0 ]] || die 'ROOT_REQUIRED_NO_CHANGES'

# This is an isolated Owner test slot, not the live release115 installation.
# Never remove or overwrite a previous test tree or its rollback slot.
for existing in "$TARGET" "$PREVIOUS" "$NEW_TREE" "$BIN"; do
  [[ ! -e "$existing" && ! -L "$existing" ]] ||
    die 'TEST_SLOT_ALREADY_EXISTS_NO_CHANGES'
done
[[ -f /opt/vf-server-ops/BUILD_ID ]] ||
  die 'LIVE_INSTALL_NOT_FOUND_NO_CHANGES'
live_before="$(cat /opt/vf-server-ops/BUILD_ID)"
[[ "$live_before" == '0.1.0-release115' ]] ||
  die 'LIVE_BUILD_UNEXPECTED_NO_CHANGES'

work="$(mktemp -d /tmp/p07-owner-test116.XXXXXXXX)" ||
  die 'TEMP_DIR_UNAVAILABLE_NO_CHANGES'
trap 'rm -rf -- "$work"' EXIT

# No GitHub login, copy-pasted token, Git credential installation,
# or password prompts. Reuse only read permission already on this VPS.
# Do not expose auth errors, usernames or remote content in public output.
export GIT_TERMINAL_PROMPT=0
if git clone --quiet --depth 1 --single-branch --branch "$PRODUCT_BRANCH" \
    'https://github.com/llhzx2018/vf-server-ops.git' "$work/product" \
    >/dev/null 2>&1; then
  note 'PRIVATE_REPO_HTTPS_READ=PASS'
else
  rm -rf -- "$work/product"
  if GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10' \
      git clone --quiet --depth 1 --single-branch --branch "$PRODUCT_BRANCH" \
      'git@github.com:llhzx2018/vf-server-ops.git' "$work/product" \
      >/dev/null 2>&1; then
    note 'PRIVATE_REPO_SSH_READ=PASS'
  else
    die 'PRIVATE_SOURCE_AUTH_REQUIRED_NO_CHANGES'
  fi
fi

actual="$(git -C "$work/product" rev-parse HEAD)" ||
  die 'PRODUCT_SHA_UNAVAILABLE_NO_CHANGES'
[[ "$actual" == "$PRODUCT_SHA" ]] ||
  die 'PRODUCT_SOURCE_MOVED_REFUSE_UNPINNED_CODE'
[[ "$(cat "$work/product/BUILD_ID")" == "$EXPECTED_BUILD" ]] ||
  die 'PRODUCT_BUILD_ID_MISMATCH'

# Public immutable release115 base provides pre-existing installer,
# original runtime and System Care. This does NOT install release115 again.
git clone --quiet --depth 1 --filter=blob:none --no-checkout \
  'https://github.com/llhzx2018/core-free-runner-public.git' \
  "$work/public" >/dev/null 2>&1 ||
  die 'PUBLIC_BASE_CLONE_FAILED'
git -C "$work/public" fetch --quiet --depth 1 origin "$BASE_SHA" \
  >/dev/null 2>&1 || die 'PUBLIC_BASE_EXACT_PIN_UNAVAILABLE'
git -C "$work/public" checkout --quiet --detach FETCH_HEAD \
  >/dev/null 2>&1 || die 'PUBLIC_BASE_CHECKOUT_FAILED'
[[ "$(git -C "$work/public" rev-parse HEAD)" == "$BASE_SHA" ]] ||
  die 'PUBLIC_BASE_PIN_MISMATCH'

python3 -B "$work/product/scripts/p07_candidate_bundle.py" \
  --product-root "$work/product" \
  --public-root "$work/public" \
  --output "$work/candidate" \
  --product-sha "$PRODUCT_SHA" \
  --build "$EXPECTED_BUILD" \
  --care "$CARE_BUILD" >/dev/null ||
  die 'CANDIDATE_BUILD_FAILED_NO_LIVE_CHANGES'

python3 -B - "$work/candidate" "$PRODUCT_SHA" <<'PY' ||
  die 'CANDIDATE_IDENTITY_INVALID_NO_LIVE_CHANGES'
import json,sys
from pathlib import Path
tree=Path(sys.argv[1]); want=sys.argv[2]
a=json.loads((tree/'candidate_attestation.json').read_text())
assert a['product_source_sha']==want
assert a['product_build']=='0.1.0-release116'
assert a['status']=='FORMAL_STAGING_NOT_PUBLISHED'
for key in ('installers/p07.sh','installers/p07-final.sh',
            'dist/p07/0.1.0/overlay/RUNTIME.gitblob'):
    assert (tree/key).is_file(), key
PY
note 'CANDIDATE_SOURCE_PIN=PASS'
note 'CANDIDATE_MANIFEST=PASS'

# Run only the identity-pinned local candidate installer, never any public
# main release115 installer. The original vfops and its data are untouched.
P07_INSTALL_DIR="$TARGET" \
P07_PREVIOUS_DIR="$PREVIOUS" \
P07_BIN_LINK="$BIN" \
P07_NO_EXEC=1 \
P07_PUBLIC_ROOT="file://$work/candidate" \
  bash "$work/candidate/installers/p07.sh" >/dev/null ||
  die 'ISOLATED_TEST_INSTALL_FAILED_CHECK_TEST_SLOT'

[[ -x "$BIN" || -L "$BIN" ]] ||
  die 'TEST_BINARY_MISSING'
[[ "$("$BIN" --build-id)" == "$EXPECTED_BUILD" ]] ||
  die 'TEST_BUILD_READBACK_FAILED'
[[ "$(cat /opt/vf-server-ops/BUILD_ID)" == "$live_before" ]] ||
  die 'LIVE_BUILD_CHANGED_STOP'
[[ ! -e "$NEW_TREE" && ! -L "$NEW_TREE" ]] ||
  die 'CANDIDATE_STAGING_RESIDUE_STOP'

printf '%s\n' \
  'P07_TEST116_INSTALL=PASS' \
  "P07_TEST116_PRODUCT_SHA=$PRODUCT_SHA" \
  "P07_TEST116_BUILD=$EXPECTED_BUILD" \
  "P07_TEST116_RUN_COMMAND=$BIN" \
  "P07_TEST116_OLD_VFOPS_BUILD=$live_before" \
  'P07_TEST116_MIGRATION_AUTORUN=NO' \
  'P07_TEST116_DNS_CHANGED=NO'
