#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"
: "${RUNNER_TOKEN:?missing runner token}"

REPO="llhzx2018/vf-start"
RUNNER_REPO="llhzx2018/core-free-runner-public"
TAG="v2.47.14"
EXACT_SHA="421e7b5df1e48db768b39470fc99580330a07c0f"
EXACT_TREE="598eaae633ef485dd2eef1330a9370cb46f90506"
PROOF_RUN="35356150139"
PROOF_NAME="p01-v24714-navigation-row-35356150139"

FULL="VF-Start-V2.47.14-FULL.zip"
UPDATE="VF_Start_V2.47.14_UPDATE.zip"
FULL_BYTES="869410"
FULL_SHA="c18bbcda3231ba542ceb7752fd6f722a8699682e62d3375e5e619ab0105e90aa"
UPDATE_BYTES="1852914"
UPDATE_SHA="65d7822f3814f3c5d7341394cd581032b111c741217813fdff35c282eaecf903"

ROOT="/tmp/p01-v24714-formal-release"
ART="$ROOT/artifact"
rm -rf "$ROOT"
mkdir -p "$ART" evidence/runner

sha(){ sha256sum "$1" | awk '{print $1}'; }
bytes(){ stat -c '%s' "$1"; }
api(){ GH_TOKEN="$VF_RELEASE_WRITE_TOKEN" gh api "$@"; }

test "$(api "repos/${REPO}/branches/main" --jq '.commit.sha')" = "$EXACT_SHA"
test "$(api "repos/${REPO}/git/commits/${EXACT_SHA}" --jq '.tree.sha')" = "$EXACT_TREE"

GH_TOKEN="$RUNNER_TOKEN" gh run download "$PROOF_RUN" --repo "$RUNNER_REPO" --name "$PROOF_NAME" --dir "$ART"

grep -Fx "P01_EXACT_SOURCE_SHA=$EXACT_SHA" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "P01_EXACT_SOURCE_TREE=$EXACT_TREE" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "P01_V24714_NAVIGATION_ROW_RELEASE_GATE=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "PUBLIC_NAVIGATION_ROW_RENDER=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "UI_PUBLIC_ROW_LAYOUT_CONTRACT=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "V24713_TO_V24714_ATOMIC_UPGRADE=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "DATA_PRESERVATION=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "MANAGED_UPDATE_CREDENTIAL_PRESERVATION=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "INJECTED_FAILURE_ROLLBACK=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "INTERRUPTION_RECOVERY=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null
grep -Fx "GLOBAL_BARRIER=PASS" "$ART/R14_GATE_RECEIPT.txt" >/dev/null

test "$(bytes "$ART/$FULL")" = "$FULL_BYTES"
test "$(sha "$ART/$FULL")" = "$FULL_SHA"
test "$(bytes "$ART/$UPDATE")" = "$UPDATE_BYTES"
test "$(sha "$ART/$UPDATE")" = "$UPDATE_SHA"

printf '%s  %s\n' "$FULL_SHA" "$FULL" >"$ART/$FULL.sha256"
printf '%s  %s\n' "$UPDATE_SHA" "$UPDATE" >"$ART/$UPDATE.sha256"
(
  cd "$ART"
  sha256sum "$FULL" "$FULL.sha256" "$UPDATE" "$UPDATE.sha256" >SHA256SUMS.txt
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
VF Start V2.47.14 Navigation public-row layout fix.

Exact source: $EXACT_SHA
Exact source tree: $EXACT_TREE
Validated direct upgrade: V2.47.13 → V2.47.14
Schema: 2026090401 → 2026090401
Migration: NONE

Fix:
- Logged-out Navigation rows no longer collapse title / URL text into the icon-width column.
- Public rows without the admin selection checkbox use the correct three-column layout: icon + flexible copy + metadata.
- Signed-in/admin row behavior is unchanged.

Machine proof: Public Runner $PROOF_RUN PASS.
- Clean FULL install / admin login / setup lock PASS
- Public Navigation real render + row-layout contract PASS
- V2.47.13 → V2.47.14 Atomic update PASS
- Persistent business data preserved
- Managed private read credential preserved with 0600 mode
- Gate-only source drift accepted; real runtime tamper rejected
- Injected rollback PASS
- Hard interruption recovery PASS
- Global maintenance barrier PASS
- Deterministic FULL / UPDATE identity PASS

Publishing this release does not update Production automatically.
EOF
)

REL=$(api --method POST "repos/${REPO}/releases"   -f tag_name="$TAG"   -f target_commitish="$EXACT_SHA"   -f name="VF Start V2.47.14"   -f body="$BODY"   -F draft=true   -F prerelease=false)
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
upload "$ART/SHA256SUMS.txt" text/plain

REL2=$(api "repos/${REPO}/releases/${RELEASE_ID}")
test "$(jq -r '.draft' <<<"$REL2")" = "true"
test "$(jq -r '.target_commitish' <<<"$REL2")" = "$EXACT_SHA"
test "$(jq -r '.assets|length' <<<"$REL2")" = "5"

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
verify_remote "$FULL.sha256" "$(bytes "$ART/$FULL.sha256")" "$(sha "$ART/$FULL.sha256")"
verify_remote "$UPDATE.sha256" "$(bytes "$ART/$UPDATE.sha256")" "$(sha "$ART/$UPDATE.sha256")"
verify_remote "SHA256SUMS.txt" "$(bytes "$ART/SHA256SUMS.txt")" "$(sha "$ART/SHA256SUMS.txt")"

api --method PATCH "repos/${REPO}/releases/${RELEASE_ID}" -F draft=false -F prerelease=false -f body="$BODY" >/dev/null
FINAL=$(api "repos/${REPO}/releases/tags/${TAG}")
test "$(jq -r '.draft' <<<"$FINAL")" = "false"
test "$(jq -r '.prerelease' <<<"$FINAL")" = "false"
test "$(jq -r '.target_commitish' <<<"$FINAL")" = "$EXACT_SHA"
test "$(jq -r '.assets|length' <<<"$FINAL")" = "5"

RELEASE_CREATED=0
TAG_CREATED=0
trap - ERR

PUBLISHED_AT=$(jq -r '.published_at' <<<"$FINAL")
cat >evidence/runner/P01_V24714_FORMAL_RELEASE_RECEIPT.txt <<EOF
P01_EXACT_SOURCE_SHA=$EXACT_SHA
P01_EXACT_SOURCE_TREE=$EXACT_TREE
TAG=$TAG
RELEASE_ID=$RELEASE_ID
PUBLISHED_AT=$PUBLISHED_AT
PROOF_RUN=$PROOF_RUN
SOURCE_VERSION=2.47.13
TARGET_VERSION=2.47.14
SCHEMA=2026090401
MIGRATION=NONE
FULL_BYTES=$FULL_BYTES
FULL_SHA256=$FULL_SHA
UPDATE_BYTES=$UPDATE_BYTES
UPDATE_SHA256=$UPDATE_SHA
PUBLIC_NAVIGATION_ROW_RENDER=PASS
UI_PUBLIC_ROW_LAYOUT_CONTRACT=PASS
V24713_TO_V24714_ATOMIC_UPGRADE=PASS
DATA_PRESERVATION=PASS
MANAGED_UPDATE_CREDENTIAL_PRESERVATION=PASS
REMOTE_READBACK=PASS
FORMAL_RELEASE=PASS
PRODUCTION=NOT_WRITTEN
P01_V24714_FORMAL_RELEASE_GATE=PASS
EOF
cat evidence/runner/P01_V24714_FORMAL_RELEASE_RECEIPT.txt
