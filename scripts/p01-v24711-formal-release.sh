#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_RELEASE_WRITE_TOKEN:?missing release credential}"
: "${P01_EXACT_SHA:=252ca51215e7e4411741e2f53d0bcc68f37614f2}"
: "${P01_EXACT_TREE:=1e6fe31f03ed871e68b3153b7e5c1e81099d1cf7}"
: "${P01_SOURCE_SHA:=972541fd06c66044105ec1b19cf7738c340c90c1}"
: "${P01_VERSION:=2.47.11}"
: "${P01_SOURCE_VERSION:=2.47.10}"
: "${RUNNER_ROOT:=$PWD/runner}"
: "${P01_ROOT:=$PWD/vf-start}"
: "${BASELINE_ROOT:=$PWD/baseline}"

REPO="llhzx2018/vf-start"
API="https://api.github.com/repos/${REPO}"
TAG="v${P01_VERSION}"
OUT="/tmp/p01-v24711-formal-release"
EXPECTED_FULL_BYTES=869376
EXPECTED_FULL_SHA="e2f6f41eaaea2c2fdc0788741f309d5d467d9a764a99c064ef7ba8a1d60c444a"
EXPECTED_UPDATE_BYTES=1882483
EXPECTED_UPDATE_SHA="c743c1d2434f448839c356cf138e9a4dece464ec6d15caa7027c6e3b41614fa6"
EXPECTED_BRIDGE_BYTES=35644
EXPECTED_BRIDGE_SHA="e7036b2f442655793834c2973532334f2ba20b43862a8d3d68b3ffc3c0ce076b"
FULL="VF-Start-V${P01_VERSION}-FULL.zip"
UPDATE="VF_Start_V${P01_VERSION}_UPDATE.zip"
BRIDGE="P01_V24710_AUTH_BRIDGE.php"

api() {
  local method="$1" url="$2"; shift 2
  curl --fail-with-body -sS -L -X "$method" \
    -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}" \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    "$@" "$url"
}

sha() { sha256sum "$1" | awk '{print $1}'; }
bytes() { stat -c '%s' "$1"; }

rm -rf "$OUT"
mkdir -p "$OUT"

test "$(git -C "$P01_ROOT" rev-parse HEAD)" = "$P01_EXACT_SHA"
test "$(git -C "$P01_ROOT" rev-parse HEAD^{tree})" = "$P01_EXACT_TREE"
test "$(git -C "$BASELINE_ROOT" rev-parse HEAD)" = "$P01_SOURCE_SHA"

python "$RUNNER_ROOT/scripts/p01-v24711-release-gate.py" \
  --candidate "$P01_ROOT/src" \
  --source "$BASELINE_ROOT/src" \
  --out "$OUT" \
  --candidate-commit "$P01_EXACT_SHA" \
  --candidate-tree "$P01_EXACT_TREE" \
  --source-commit "$P01_SOURCE_SHA" >/tmp/p01-v24711-formal-build.json

test "$(bytes "$OUT/$FULL")" = "$EXPECTED_FULL_BYTES"
test "$(sha "$OUT/$FULL")" = "$EXPECTED_FULL_SHA"
test "$(bytes "$OUT/$UPDATE")" = "$EXPECTED_UPDATE_BYTES"
test "$(sha "$OUT/$UPDATE")" = "$EXPECTED_UPDATE_SHA"
test "$(bytes "$OUT/$BRIDGE")" = "$EXPECTED_BRIDGE_BYTES"
test "$(sha "$OUT/$BRIDGE")" = "$EXPECTED_BRIDGE_SHA"
printf '%s  %s\n' "$EXPECTED_FULL_SHA" "$FULL" >"$OUT/$FULL.sha256"
printf '%s  %s\n' "$EXPECTED_UPDATE_SHA" "$UPDATE" >"$OUT/$UPDATE.sha256"
printf '%s  %s\n' "$EXPECTED_BRIDGE_SHA" "$BRIDGE" >"$OUT/$BRIDGE.sha256"

# Fail closed if main moved after the exact machine gate.
main_json="$(api GET "$API/branches/main")"
remote_main="$(python -c 'import json,sys; print(json.load(sys.stdin)["commit"]["sha"])' <<<"$main_json")"
test "$remote_main" = "$P01_EXACT_SHA"

# Ensure the release tag is either absent or already bound to the exact gated source.
set +e
tag_json="$(api GET "$API/git/ref/tags/$TAG" 2>/tmp/p01-tag.err)"
tag_rc=$?
set -e
if [[ $tag_rc -ne 0 ]]; then
  payload="$(python - <<PY
import json
print(json.dumps({'ref':'refs/tags/$TAG','sha':'$P01_EXACT_SHA'}))
PY
)"
  tag_json="$(api POST "$API/git/refs" -H 'Content-Type: application/json' -d "$payload")"
fi
tag_sha="$(python -c 'import json,sys; print(json.load(sys.stdin)["object"]["sha"])' <<<"$tag_json")"
test "$tag_sha" = "$P01_EXACT_SHA"

set +e
release_json="$(api GET "$API/releases/tags/$TAG" 2>/tmp/p01-release.err)"
release_rc=$?
set -e
if [[ $release_rc -ne 0 ]]; then
  body="$(cat <<EOF
VF Start V${P01_VERSION} formal release.

Exact source: ${P01_EXACT_SHA}
Exact source tree: ${P01_EXACT_TREE}
Validated direct upgrade: V${P01_SOURCE_VERSION} → V${P01_VERSION}
Schema: 2026090401 → 2026090401
Migration: NONE

This release restores the read-only update authorization recovery path, classifies HTTP 401/403 authorization failures, prevents stale-latest cache from masquerading as current update truth, and ships a bounded one-time V2.47.10 authorization bridge. The bridge contains no token, does no network access, and retires after successful V2.47.11 installation.
EOF
)"
  payload="$(BODY="$body" python - <<'PY'
import json,os
print(json.dumps({
  'tag_name':'v2.47.11',
  'target_commitish':'252ca51215e7e4411741e2f53d0bcc68f37614f2',
  'name':'VF Start V2.47.11',
  'body':os.environ['BODY'],
  'draft':False,
  'prerelease':False,
}))
PY
)"
  release_json="$(api POST "$API/releases" -H 'Content-Type: application/json' -d "$payload")"
fi

release_id="$(python -c 'import json,sys; d=json.load(sys.stdin); assert d["tag_name"]=="v2.47.11" and not d["draft"] and not d["prerelease"]; print(d["id"])' <<<"$release_json")"
release_target="$(python -c 'import json,sys; print(json.load(sys.stdin).get("target_commitish",""))' <<<"$release_json")"
test "$release_target" = "$P01_EXACT_SHA" || test "$tag_sha" = "$P01_EXACT_SHA"

upload_one() {
  local path="$1" ctype="$2"
  local name; name="$(basename "$path")"
  local current; current="$(api GET "$API/releases/$release_id/assets")"
  local existing_id existing_size
  existing_id="$(NAME="$name" python -c 'import json,os,sys; a=[x for x in json.load(sys.stdin) if x.get("name")==os.environ["NAME"]]; print(a[0]["id"] if a else "")' <<<"$current")"
  existing_size="$(NAME="$name" python -c 'import json,os,sys; a=[x for x in json.load(sys.stdin) if x.get("name")==os.environ["NAME"]]; print(a[0]["size"] if a else "")' <<<"$current")"
  if [[ -z "$existing_id" ]]; then
    curl --fail-with-body -sS -L -X POST \
      -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}" \
      -H "Content-Type: $ctype" \
      -H 'X-GitHub-Api-Version: 2022-11-28' \
      --data-binary "@$path" \
      "https://uploads.github.com/repos/${REPO}/releases/${release_id}/assets?name=${name}" >/tmp/p01-upload.json
  else
    test "$existing_size" = "$(bytes "$path")"
  fi
}

upload_one "$OUT/$FULL" application/zip
upload_one "$OUT/$FULL.sha256" text/plain
upload_one "$OUT/$UPDATE" application/zip
upload_one "$OUT/$UPDATE.sha256" text/plain
upload_one "$OUT/$BRIDGE" application/octet-stream
upload_one "$OUT/$BRIDGE.sha256" text/plain
upload_one "$OUT/SHA256SUMS.txt" text/plain

assets="$(api GET "$API/releases/$release_id/assets")"
verify_remote() {
  local name="$1" expected_bytes="$2" expected_sha="$3"
  local meta id remote_size
  meta="$(NAME="$name" python -c 'import json,os,sys; a=[x for x in json.load(sys.stdin) if x.get("name")==os.environ["NAME"]]; assert len(a)==1; print(json.dumps(a[0]))' <<<"$assets")"
  id="$(python -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$meta")"
  remote_size="$(python -c 'import json,sys; print(json.load(sys.stdin)["size"])' <<<"$meta")"
  test "$remote_size" = "$expected_bytes"
  curl --fail-with-body -sS -L \
    -H "Authorization: Bearer ${VF_RELEASE_WRITE_TOKEN}" \
    -H 'Accept: application/octet-stream' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    "$API/releases/assets/$id" -o "/tmp/remote-$name"
  test "$(bytes "/tmp/remote-$name")" = "$expected_bytes"
  test "$(sha "/tmp/remote-$name")" = "$expected_sha"
}
verify_remote "$FULL" "$EXPECTED_FULL_BYTES" "$EXPECTED_FULL_SHA"
verify_remote "$UPDATE" "$EXPECTED_UPDATE_BYTES" "$EXPECTED_UPDATE_SHA"
verify_remote "$BRIDGE" "$EXPECTED_BRIDGE_BYTES" "$EXPECTED_BRIDGE_SHA"

mkdir -p "$RUNNER_ROOT/evidence/runner"
cat >"$RUNNER_ROOT/evidence/runner/P01_V24711_FORMAL_RELEASE.txt" <<EOF
P01_EXACT_SOURCE_SHA=$P01_EXACT_SHA
P01_EXACT_SOURCE_TREE=$P01_EXACT_TREE
VERSION=$P01_VERSION
FROM_VERSION=$P01_SOURCE_VERSION
SCHEMA=2026090401
MIGRATION=NONE
TAG=$TAG
RELEASE_ID=$release_id
FULL_NAME=$FULL
FULL_BYTES=$EXPECTED_FULL_BYTES
FULL_SHA256=$EXPECTED_FULL_SHA
UPDATE_NAME=$UPDATE
UPDATE_BYTES=$EXPECTED_UPDATE_BYTES
UPDATE_SHA256=$EXPECTED_UPDATE_SHA
BRIDGE_NAME=$BRIDGE
BRIDGE_BYTES=$EXPECTED_BRIDGE_BYTES
BRIDGE_SHA256=$EXPECTED_BRIDGE_SHA
TAG_EXACT_SOURCE=PASS
RELEASE_DRAFT_FALSE=PASS
RELEASE_PRERELEASE_FALSE=PASS
REMOTE_FULL_READBACK=PASS
REMOTE_UPDATE_READBACK=PASS
REMOTE_BRIDGE_READBACK=PASS
FORMAL_RELEASE=PASS
PRODUCTION=NOT_TESTED
EOF
cat "$RUNNER_ROOT/evidence/runner/P01_V24711_FORMAL_RELEASE.txt"
