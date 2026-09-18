#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"
: "${RUNNER_TOKEN:?missing runner read credential}"

P01_REPO="llhzx2018/vf-start"
RUNNER_REPO="llhzx2018/core-free-runner-public"
TAG="v2.47.11"
RELEASE_ID="390634431"
EXACT_SHA="252ca51215e7e4411741e2f53d0bcc68f37614f2"
PROOF_RUN="35218603875"
PROOF_ARTIFACT="p01-v24711-atomic-hotfix-r1-35218603875"

FULL="VF-Start-V2.47.11-FULL.zip"
UPDATE="VF_Start_V2.47.11_UPDATE.zip"
BRIDGE="P01_V24710_AUTH_BRIDGE.php"
SUMS="SHA256SUMS.txt"

FULL_BYTES="869376"
FULL_SHA="e2f6f41eaaea2c2fdc0788741f309d5d467d9a764a99c064ef7ba8a1d60c444a"
BRIDGE_BYTES="35644"
BRIDGE_SHA="e7036b2f442655793834c2973532334f2ba20b43862a8d3d68b3ffc3c0ce076b"
OLD_UPDATE_BYTES="1882483"
OLD_UPDATE_SHA="c743c1d2434f448839c356cf138e9a4dece464ec6d15caa7027c6e3b41614fa6"
NEW_UPDATE_BYTES="1883052"
NEW_UPDATE_SHA="5b6d843a734280de22d22a447b105b1ecd07144bffee46ad36c50f1e7988ae95"

ROOT="/tmp/p01-v24711-hotfix-publish"
OLD="$ROOT/old"
NEW="$ROOT/new"
rm -rf "$ROOT"
mkdir -p "$OLD" "$NEW" evidence/runner

sha(){ sha256sum "$1" | awk '{print $1}'; }
bytes(){ stat -c '%s' "$1"; }
api(){ GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh api "$@"; }

REL="$(api "repos/${P01_REPO}/releases/tags/${TAG}")"
test "$(jq -r '.id' <<<"$REL")" = "$RELEASE_ID"
test "$(jq -r '.target_commitish' <<<"$REL")" = "$EXACT_SHA"
test "$(jq -r '.draft' <<<"$REL")" = "false"
test "$(jq -r '.prerelease' <<<"$REL")" = "false"
test "$(jq -r '.immutable // false' <<<"$REL")" = "false"
test "$(api "repos/${P01_REPO}/git/ref/tags/${TAG}" --jq '.object.sha')" = "$EXACT_SHA"

GH_TOKEN="$RUNNER_TOKEN" gh run download "$PROOF_RUN"   --repo "$RUNNER_REPO"   --name "$PROOF_ARTIFACT"   --dir "$NEW"

test "$(bytes "$NEW/$FULL")" = "$FULL_BYTES"
test "$(sha "$NEW/$FULL")" = "$FULL_SHA"
test "$(bytes "$NEW/$UPDATE")" = "$NEW_UPDATE_BYTES"
test "$(sha "$NEW/$UPDATE")" = "$NEW_UPDATE_SHA"
grep -Fx "P01_V24711_ATOMIC_HOTFIX_R1_GATE=PASS" "$NEW/R1_GATE_RECEIPT.txt" >/dev/null

asset_id(){
  local name="$1"
  jq -r --arg n "$name" '[.assets[]|select(.name==$n)|.id] | if length==1 then .[0] else empty end' <<<"$REL"
}
download_release_asset(){
  local name="$1" dest="$2" id
  id="$(asset_id "$name")"
  test -n "$id"
  curl --fail-with-body -sS -L     -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}"     -H 'Accept: application/octet-stream'     -H 'X-GitHub-Api-Version: 2022-11-28'     "https://api.github.com/repos/${P01_REPO}/releases/assets/${id}" -o "$dest"
}

for name in "$FULL" "$FULL.sha256" "$UPDATE" "$UPDATE.sha256" "$BRIDGE" "$BRIDGE.sha256" "$SUMS"; do
  download_release_asset "$name" "$OLD/$name"
done

test "$(bytes "$OLD/$FULL")" = "$FULL_BYTES"
test "$(sha "$OLD/$FULL")" = "$FULL_SHA"
test "$(bytes "$OLD/$BRIDGE")" = "$BRIDGE_BYTES"
test "$(sha "$OLD/$BRIDGE")" = "$BRIDGE_SHA"
test "$(bytes "$OLD/$UPDATE")" = "$OLD_UPDATE_BYTES"
test "$(sha "$OLD/$UPDATE")" = "$OLD_UPDATE_SHA"
grep -Fq "$OLD_UPDATE_SHA  $UPDATE" "$OLD/$UPDATE.sha256"

cp "$OLD/$FULL" "$OLD/$FULL.sha256" "$OLD/$BRIDGE" "$OLD/$BRIDGE.sha256" "$NEW/"
printf '%s  %s\n' "$NEW_UPDATE_SHA" "$UPDATE" >"$NEW/$UPDATE.sha256"
(cd "$NEW" && sha256sum "$FULL" "$FULL.sha256" "$UPDATE" "$UPDATE.sha256" "$BRIDGE" "$BRIDGE.sha256" >"$SUMS")

upload_one(){
  local path="$1" ctype="$2" name
  name="$(basename "$path")"
  curl --fail-with-body -sS -L -X POST     -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}"     -H "Content-Type: ${ctype}"     -H 'X-GitHub-Api-Version: 2022-11-28'     --data-binary "@$path"     "https://uploads.github.com/repos/${P01_REPO}/releases/${RELEASE_ID}/assets?name=${name}" >/dev/null
}
delete_name(){
  local name="$1" rel id
  rel="$(api "repos/${P01_REPO}/releases/tags/${TAG}")"
  id="$(jq -r --arg n "$name" '[.assets[]|select(.name==$n)|.id] | if length==1 then .[0] else empty end' <<<"$rel")"
  if [[ -n "$id" ]]; then api --method DELETE "repos/${P01_REPO}/releases/assets/${id}" >/dev/null; fi
}
restore_old(){
  trap - ERR
  set +e
  for name in "$UPDATE" "$UPDATE.sha256" "$SUMS"; do delete_name "$name"; done
  upload_one "$OLD/$UPDATE" application/zip
  upload_one "$OLD/$UPDATE.sha256" text/plain
  upload_one "$OLD/$SUMS" text/plain
}
MUTATED=0
trap 'rc=$?; if [[ "$MUTATED" == 1 ]]; then restore_old; fi; exit $rc' ERR

for name in "$UPDATE" "$UPDATE.sha256" "$SUMS"; do delete_name "$name"; done
MUTATED=1
upload_one "$NEW/$UPDATE" application/zip
upload_one "$NEW/$UPDATE.sha256" text/plain
upload_one "$NEW/$SUMS" text/plain

REL2="$(api "repos/${P01_REPO}/releases/tags/${TAG}")"
verify_remote(){
  local name="$1" expected_bytes="$2" expected_sha="$3" id tmp
  id="$(jq -r --arg n "$name" '[.assets[]|select(.name==$n)|.id] | if length==1 then .[0] else empty end' <<<"$REL2")"
  test -n "$id"
  tmp="$ROOT/remote-$name"
  curl --fail-with-body -sS -L     -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}"     -H 'Accept: application/octet-stream'     -H 'X-GitHub-Api-Version: 2022-11-28'     "https://api.github.com/repos/${P01_REPO}/releases/assets/${id}" -o "$tmp"
  test "$(bytes "$tmp")" = "$expected_bytes"
  test "$(sha "$tmp")" = "$expected_sha"
}
verify_remote "$UPDATE" "$NEW_UPDATE_BYTES" "$NEW_UPDATE_SHA"
verify_remote "$FULL" "$FULL_BYTES" "$FULL_SHA"
verify_remote "$BRIDGE" "$BRIDGE_BYTES" "$BRIDGE_SHA"

UPDATE_SHA_FILE_SHA="$(sha "$NEW/$UPDATE.sha256")"
SUMS_SHA="$(sha "$NEW/$SUMS")"
verify_remote "$UPDATE.sha256" "$(bytes "$NEW/$UPDATE.sha256")" "$UPDATE_SHA_FILE_SHA"
verify_remote "$SUMS" "$(bytes "$NEW/$SUMS")" "$SUMS_SHA"

BODY="$(jq -r '.body // ""' <<<"$REL2")"
MARKER="Atomic Asset Hotfix R1"
if ! grep -Fq "$MARKER" <<<"$BODY"; then
  BODY="$BODY

Atomic Asset Hotfix R1
- Corrected UPDATE asset only; product source/tag unchanged at `$EXACT_SHA`.
- Machine proof: Public Runner `$PROOF_RUN` PASS.
- Corrected UPDATE: `$UPDATE` / $NEW_UPDATE_BYTES bytes / SHA-256 `$NEW_UPDATE_SHA`.
- FULL and authorization bridge bytes unchanged.
- Production remains separate and is not changed by this publication repair."
  api --method PATCH "repos/${P01_REPO}/releases/${RELEASE_ID}" -f body="$BODY" >/dev/null
fi

MUTATED=0
trap - ERR

cat >evidence/runner/P01_V24711_ATOMIC_HOTFIX_R1_PUBLISH.txt <<EOF
P01_EXACT_SOURCE_SHA=$EXACT_SHA
TAG=$TAG
RELEASE_ID=$RELEASE_ID
PROOF_RUN=$PROOF_RUN
OLD_UPDATE_BYTES=$OLD_UPDATE_BYTES
OLD_UPDATE_SHA256=$OLD_UPDATE_SHA
NEW_UPDATE_BYTES=$NEW_UPDATE_BYTES
NEW_UPDATE_SHA256=$NEW_UPDATE_SHA
FULL_BYTES=$FULL_BYTES
FULL_SHA256=$FULL_SHA
BRIDGE_BYTES=$BRIDGE_BYTES
BRIDGE_SHA256=$BRIDGE_SHA
RELEASE_ASSET_REPLACEMENT=PASS
REMOTE_UPDATE_READBACK=PASS
REMOTE_FULL_UNCHANGED=PASS
REMOTE_BRIDGE_UNCHANGED=PASS
CORE_UPDATES=NOT_YET_UPDATED
PRODUCTION=NOT_TESTED
EOF
cat evidence/runner/P01_V24711_ATOMIC_HOTFIX_R1_PUBLISH.txt
