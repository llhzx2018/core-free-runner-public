#!/usr/bin/env bash
set -Eeuo pipefail

: "${GH_TOKEN:?GH_TOKEN required}"
RELEASE_SOURCE='a9300382d3a862fb599b8b928961ead38dee8f31'
VERIFIED_RUN='33184343643'
ARTIFACT_NAME='P06-V0.1.15-FORMAL-ATOMIC-RELEASE-SET'
FULL_SHA='03702b4c0401f5777cfbe52702821f84a11a83e1ea2a06680b0ead3808820cd7'
FULL_BYTES='271733'
UPDATE_SHA='152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe'
UPDATE_BYTES='278578'
ROOT="$RUNNER_TEMP/p06-v0115-publication"
rm -rf "$ROOT"
mkdir -p "$ROOT/release-set"

# Fence the live release source before publication.
MAIN="$(gh api repos/llhzx2018/vf-press/git/ref/heads/main --jq .object.sha)"
test "$MAIN" = "$RELEASE_SOURCE"
if gh api repos/llhzx2018/vf-press/releases/tags/v0.1.15 >/dev/null 2>&1; then
  echo 'P06_V0115_RELEASE_ALREADY_EXISTS=YES'
else
  gh run download "$VERIFIED_RUN" -R llhzx2018/core-free-runner-public -n "$ARTIFACT_NAME" -D "$ROOT/release-set"
  test "$(tr -d '\r\n' < "$ROOT/release-set/RELEASE_SOURCE.txt")" = "$RELEASE_SOURCE"
  test "$(tr -d '\r\n' < "$ROOT/release-set/FULL_BYTES.txt")" = "$FULL_BYTES"
  test "$(tr -d '\r\n' < "$ROOT/release-set/FULL_SHA256.txt")" = "$FULL_SHA"
  test "$(tr -d '\r\n' < "$ROOT/release-set/UPDATE_BYTES.txt")" = "$UPDATE_BYTES"
  test "$(tr -d '\r\n' < "$ROOT/release-set/UPDATE_SHA256.txt")" = "$UPDATE_SHA"
  test "$(stat -c %s "$ROOT/release-set/VF_Press_V0.1.15_FULL.zip")" = "$FULL_BYTES"
  test "$(sha256sum "$ROOT/release-set/VF_Press_V0.1.15_FULL.zip" | awk '{print $1}')" = "$FULL_SHA"
  test "$(stat -c %s "$ROOT/release-set/VF_Press_V0.1.15_UPDATE.zip")" = "$UPDATE_BYTES"
  test "$(sha256sum "$ROOT/release-set/VF_Press_V0.1.15_UPDATE.zip" | awk '{print $1}')" = "$UPDATE_SHA"
  echo P06_V0115_ARTIFACT_IDENTITY=PASS

  gh release create v0.1.15 \
    -R llhzx2018/vf-press \
    --target "$RELEASE_SOURCE" \
    --title 'VF Press V0.1.15 · Human-readable System Baseline UI' \
    --notes 'V0.1.15 makes System Info / System Baseline / Runtime Health administrator-first while preserving Common Product Baseline V2 machine truth and the two explicit TIME/API exceptions. Schema remains 3. Product Exact Source 561e59a82f035e2622c4567710bec06a1c50dab3 passed the Human UI Formal Gate. Release Source a9300382d3a862fb599b8b928961ead38dee8f31 is the merged release source. Real V0.1.14 -> V0.1.15 Atomic Gate Run 33184343643 passed with recovery point, user-data preservation, Schema 3, post-update HTTP and rollback contract. Production is not modified by this release.' \
    "$ROOT/release-set/VF_Press_V0.1.15_FULL.zip" \
    "$ROOT/release-set/VF_Press_V0.1.15_UPDATE.zip" \
    "$ROOT/release-set/SHA256SUMS.txt" \
    "$ROOT/release-set/RELEASE_INFO.json"
fi

TAG_SHA="$(gh api repos/llhzx2018/vf-press/git/ref/tags/v0.1.15 --jq .object.sha)"
test "$TAG_SHA" = "$RELEASE_SOURCE"
gh api repos/llhzx2018/vf-press/releases/tags/v0.1.15 > "$ROOT/release.json"
python3 - "$ROOT/release.json" "$FULL_BYTES" "$FULL_SHA" "$UPDATE_BYTES" "$UPDATE_SHA" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
full_bytes=int(sys.argv[2]); full_sha=sys.argv[3]
update_bytes=int(sys.argv[4]); update_sha=sys.argv[5]
assert r['tag_name']=='v0.1.15'
assert not r['draft'] and not r['prerelease']
assets={a['name']:a for a in r['assets']}
for name,size,sha in [
  ('VF_Press_V0.1.15_FULL.zip',full_bytes,full_sha),
  ('VF_Press_V0.1.15_UPDATE.zip',update_bytes,update_sha),
]:
  a=assets[name]
  assert a['size']==size,(name,a['size'],size)
  assert a.get('digest')==f'sha256:{sha}',(name,a.get('digest'),sha)
print('P06_V0115_RELEASE_ID='+str(r['id']))
print('P06_V0115_PUBLISHED_AT='+str(r['published_at']))
print('P06_V0115_FULL_ASSET_ID='+str(assets['VF_Press_V0.1.15_FULL.zip']['id']))
print('P06_V0115_UPDATE_ASSET_ID='+str(assets['VF_Press_V0.1.15_UPDATE.zip']['id']))
print('P06_V0115_PUBLICATION=PASS')
PY
