#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"
: "${RUNNER_TOKEN:?missing runner token}"

REPO="llhzx2018/vf-start"
RUNNER_REPO="llhzx2018/core-free-runner-public"
TAG="v2.47.13"
EXACT_SHA="e714cfe540ad39202c2cb558e5c0a370ef6d6502"
EXACT_TREE="400768a3b11edba4e0b54264a08b08ec6af9155e"
PROOF_RUN="35342204523"
PROOF_NAME="p01-v24713-runtime-boundary-35342204523"

FULL="VF-Start-V2.47.13-FULL.zip"
UPDATE="VF_Start_V2.47.13_UPDATE.zip"
BRIDGE="P01_V24710_AUTH_BRIDGE.php"
FULL_BYTES="869136"
FULL_SHA="1eadccb499869912e225f89b1a6cb0fe832e5c7d47ee635ddde4990bdec68509"
UPDATE_BYTES="1852330"
UPDATE_SHA="e8094c52f5ef2c3973a08cfcd845ec6d99096ee46d03e02a3fa8fa11211fd3b4"

ROOT="/tmp/p01-v24713-formal-release"
ART="$ROOT/artifact"
rm -rf "$ROOT"
mkdir -p "$ART" evidence/runner

sha(){ sha256sum "$1" | awk '{print $1}'; }
bytes(){ stat -c '%s' "$1"; }
api(){ GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh api "$@"; }

test "$(api "repos/${REPO}/branches/main" --jq '.commit.sha')" = "$EXACT_SHA"
test "$(api "repos/${REPO}/git/commits/${EXACT_SHA}" --jq '.tree.sha')" = "$EXACT_TREE"

GH_TOKEN="$RUNNER_TOKEN" gh run download "$PROOF_RUN" --repo "$RUNNER_REPO" --name "$PROOF_NAME" --dir "$ART"

grep -Fx "P01_EXACT_SOURCE_SHA=$EXACT_SHA" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "P01_V24713_RUNTIME_BOUNDARY_GATE=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "GATE_ONLY_DRIFT_ACCEPTED=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "RUNTIME_TAMPER_REJECTED=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "BRIDGED_PRODUCTION_SHAPE_UPGRADE=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "DATA_PRESERVATION=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "INJECTED_FAILURE_ROLLBACK=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "INTERRUPTION_RECOVERY=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null
grep -Fx "GLOBAL_BARRIER=PASS" "$ART/R1_GATE_RECEIPT.txt" >/dev/null

test "$(bytes "$ART/$FULL")" = "$FULL_BYTES"
test "$(sha "$ART/$FULL")" = "$FULL_SHA"
test "$(bytes "$ART/$UPDATE")" = "$UPDATE_BYTES"
test "$(sha "$ART/$UPDATE")" = "$UPDATE_SHA"
test -s "$ART/$BRIDGE"
BRIDGE_BYTES="$(bytes "$ART/$BRIDGE")"
BRIDGE_SHA="$(sha "$ART/$BRIDGE")"
printf '%s  %s\n' "$BRIDGE_SHA" "$BRIDGE" >"$ART/$BRIDGE.sha256"
(
  cd "$ART"
  sha256sum "$FULL" "$FULL.sha256" "$UPDATE" "$UPDATE.sha256" "$BRIDGE" "$BRIDGE.sha256" >SHA256SUMS.txt
)

if api "repos/${REPO}/releases/tags/${TAG}" >/dev/null 2>&1; then
  echo "release already exists" >&2
  exit 1
fi

TAG_CREATED=0
RELEASE_CREATED=0
RELEASE_ID=""
cleanup(){
  rc=$?
  trap - ERR
  set +e
  if [[ "$RELEASE_CREATED" == 1 && -n "$RELEASE_ID" ]]; then
    api --method DELETE "repos/${REPO}/releases/${RELEASE_ID}" >/dev/null
  fi
  if [[ "$TAG_CREATED" == 1 ]]; then
    api --method DELETE "repos/${REPO}/git/refs/tags/${TAG}" >/dev/null
  fi
  exit "$rc"
}
trap cleanup ERR

api --method POST "repos/${REPO}/git/refs" -f ref="refs/tags/${TAG}" -f sha="$EXACT_SHA" >/dev/null
TAG_CREATED=1
test "$(api "repos/${REPO}/git/ref/tags/${TAG}" --jq '.object.sha')" = "$EXACT_SHA"

BODY=$(cat <<EOF
VF Start V2.47.13 runtime-boundary recovery release.

Exact source: $EXACT_SHA
Exact source tree: $EXACT_TREE
Validated direct upgrade: V2.47.10 → V2.47.13
Schema: 2026090401 → 2026090401
Migration: NONE

Owner Production journal proved V2.47.12 Atomic source verification was hashing gate-only deployment/documentation files that the proven V2.47.10 formal builder had explicitly excluded from the runtime boundary. V2.47.13 restores that proven boundary without weakening runtime integrity.

Gate-only files excluded from Atomic source verification remain distributable in FULL:
- .gitignore
- CHANGELOG.md
- DEPLOY-HERE.txt
- FULL-PACKAGE-NOTES.txt
- README.md
- UPGRADE-V2.txt
- robots.txt
- VF-Start-Browser-Extension.zip

Runtime PHP/assets remain strictly SHA-enforced. The machine gate intentionally mutated gate-only files and required upgrade PASS, then tampered app/bootstrap.php and required source verification FAIL.

Machine proof: Public Runner $PROOF_RUN PASS.
- Fresh Install PASS
- V2.47.10 + authorization bridge + gate-only Production drift upgrade PASS
- Runtime tamper rejection PASS
- Data preservation PASS
- Injected failure rollback PASS
- Hard interruption recovery PASS
- Global maintenance barrier PASS
- Deterministic FULL / UPDATE package identity PASS

Production is not changed by publishing this release.
EOF
)

REL=$(api --method POST "repos/${REPO}/releases"   -f tag_name="$TAG"   -f target_commitish="$EXACT_SHA"   -f name="VF Start V2.47.13"   -f body="$BODY"   -F draft=true   -F prerelease=false)
RELEASE_ID=$(jq -r '.id' <<<"$REL")
test "$RELEASE_ID" != "null"
RELEASE_CREATED=1

upload(){
  local file="$1" ctype="$2" name
  name=$(basename "$file")
  curl --fail-with-body -sS -L -X POST     -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}"     -H "Content-Type: ${ctype}"     -H 'X-GitHub-Api-Version: 2022-11-28'     --data-binary "@$file"     "https://uploads.github.com/repos/${REPO}/releases/${RELEASE_ID}/assets?name=${name}" >/dev/null
}
upload "$ART/$FULL" application/zip
upload "$ART/$FULL.sha256" text/plain
upload "$ART/$UPDATE" application/zip
upload "$ART/$UPDATE.sha256" text/plain
upload "$ART/$BRIDGE" application/octet-stream
upload "$ART/$BRIDGE.sha256" text/plain
upload "$ART/SHA256SUMS.txt" text/plain

REL2=$(api "repos/${REPO}/releases/${RELEASE_ID}")
test "$(jq -r '.draft' <<<"$REL2")" = "true"
test "$(jq -r '.target_commitish' <<<"$REL2")" = "$EXACT_SHA"

verify_remote(){
  local name="$1" expected_bytes="$2" expected_sha="$3" id digest tmp
  id=$(jq -r --arg n "$name" '[.assets[]|select(.name==$n)|.id] | if length==1 then .[0] else empty end' <<<"$REL2")
  test -n "$id"
  digest=$(jq -r --arg n "$name" '[.assets[]|select(.name==$n)|.digest] | if length==1 then .[0] else empty end' <<<"$REL2")
  if [[ -n "$digest" && "$digest" != "null" ]]; then test "$digest" = "sha256:$expected_sha"; fi
  tmp="$ROOT/remote-$name"
  curl --fail-with-body -sS -L     -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}"     -H 'Accept: application/octet-stream'     -H 'X-GitHub-Api-Version: 2022-11-28'     "https://api.github.com/repos/${REPO}/releases/assets/${id}" -o "$tmp"
  test "$(bytes "$tmp")" = "$expected_bytes"
  test "$(sha "$tmp")" = "$expected_sha"
}

verify_remote "$FULL" "$FULL_BYTES" "$FULL_SHA"
verify_remote "$UPDATE" "$UPDATE_BYTES" "$UPDATE_SHA"
verify_remote "$BRIDGE" "$BRIDGE_BYTES" "$BRIDGE_SHA"
verify_remote "$FULL.sha256" "$(bytes "$ART/$FULL.sha256")" "$(sha "$ART/$FULL.sha256")"
verify_remote "$UPDATE.sha256" "$(bytes "$ART/$UPDATE.sha256")" "$(sha "$ART/$UPDATE.sha256")"
verify_remote "$BRIDGE.sha256" "$(bytes "$ART/$BRIDGE.sha256")" "$(sha "$ART/$BRIDGE.sha256")"
verify_remote "SHA256SUMS.txt" "$(bytes "$ART/SHA256SUMS.txt")" "$(sha "$ART/SHA256SUMS.txt")"

api --method PATCH "repos/${REPO}/releases/${RELEASE_ID}" -F draft=false -F prerelease=false -f body="$BODY" >/dev/null
FINAL=$(api "repos/${REPO}/releases/tags/${TAG}")
test "$(jq -r '.draft' <<<"$FINAL")" = "false"
test "$(jq -r '.prerelease' <<<"$FINAL")" = "false"
test "$(jq -r '.target_commitish' <<<"$FINAL")" = "$EXACT_SHA"
test "$(jq -r '.assets|length' <<<"$FINAL")" = "7"

RELEASE_CREATED=0
TAG_CREATED=0
trap - ERR

PUBLISHED_AT=$(jq -r '.published_at' <<<"$FINAL")
cat >evidence/runner/P01_V24713_FORMAL_RELEASE_RECEIPT.txt <<EOF
P01_EXACT_SOURCE_SHA=$EXACT_SHA
P01_EXACT_SOURCE_TREE=$EXACT_TREE
TAG=$TAG
RELEASE_ID=$RELEASE_ID
PUBLISHED_AT=$PUBLISHED_AT
PROOF_RUN=$PROOF_RUN
SOURCE_VERSION=2.47.10
TARGET_VERSION=2.47.13
SCHEMA=2026090401
MIGRATION=NONE
FULL_BYTES=$FULL_BYTES
FULL_SHA256=$FULL_SHA
UPDATE_BYTES=$UPDATE_BYTES
UPDATE_SHA256=$UPDATE_SHA
BRIDGE_BYTES=$BRIDGE_BYTES
BRIDGE_SHA256=$BRIDGE_SHA
GATE_ONLY_DRIFT_ACCEPTED=PASS
RUNTIME_TAMPER_REJECTED=PASS
REMOTE_READBACK=PASS
FORMAL_RELEASE=PASS
PRODUCTION=NOT_TESTED
P01_V24713_FORMAL_RELEASE_GATE=PASS
EOF
cat evidence/runner/P01_V24713_FORMAL_RELEASE_RECEIPT.txt
