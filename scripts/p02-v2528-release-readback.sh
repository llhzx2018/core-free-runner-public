#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo ERROR_LINE=$LINENO' ERR

PRODUCT_REF="${PRODUCT_REF:?}"
RELEASE_TOKEN="${RELEASE_TOKEN:?}"
TAG=v2.5.28
UPDATE_NAME="VF_Library_V2.5.28_UPDATE.zip"
EXPECTED_UPDATE_SHA="767a52ae1693d80ff27597f67b3b24dd6a79bd495183bc65a2594885ff1dc3f5"
EXPECTED_ASSETS='["SHA256SUMS.txt","VF_Library_V2.5.28_ATOMIC.zip","VF_Library_V2.5.28_FULL.zip","VF_Library_V2.5.28_RELEASE_MANIFEST.json","VF_Library_V2.5.28_RELEASE_NOTES.md","VF_Library_V2.5.28_SOURCE.zip","VF_Library_V2.5.28_UPDATE.zip","repair-v2.5.28.php"]'

export GH_TOKEN="$RELEASE_TOKEN"

gh release view "$TAG" --repo llhzx2018/vf-library \
  --json databaseId,tagName,isDraft,isPrerelease,publishedAt,targetCommitish,assets \
  >"$RUNNER_TEMP/release2528-readback.json"

jq -e '.tagName=="v2.5.28" and .isDraft==false and .isPrerelease==false' "$RUNNER_TEMP/release2528-readback.json" >/dev/null
jq -e --argjson expected "$EXPECTED_ASSETS" '([.assets[].name] | sort) == ($expected | sort)' "$RUNNER_TEMP/release2528-readback.json" >/dev/null

ASSET_COUNT="$(jq '.assets|length' "$RUNNER_TEMP/release2528-readback.json")"
test "$ASSET_COUNT" = 8

mkdir -p "$RUNNER_TEMP/readback2528"
gh release download "$TAG" --repo llhzx2018/vf-library --pattern "$UPDATE_NAME" --dir "$RUNNER_TEMP/readback2528"
RBYTES="$(stat -c%s "$RUNNER_TEMP/readback2528/$UPDATE_NAME")"
RSHA="$(sha256sum "$RUNNER_TEMP/readback2528/$UPDATE_NAME"|awk '{print $1}')"
test "$RSHA" = "$EXPECTED_UPDATE_SHA"

TAGSHA="$(gh api "repos/llhzx2018/vf-library/git/ref/tags/$TAG" --jq .object.sha)"
test "$TAGSHA" = "$PRODUCT_REF"

RELEASE_ID="$(jq -r .databaseId "$RUNNER_TEMP/release2528-readback.json")"
PUBLISHED_AT="$(jq -r .publishedAt "$RUNNER_TEMP/release2528-readback.json")"
test -n "$RELEASE_ID"
test "$RELEASE_ID" != null
test -n "$PUBLISHED_AT"
test "$PUBLISHED_AT" != null

echo RELEASE_ID="$RELEASE_ID"
echo PUBLISHED_AT="$PUBLISHED_AT"
echo ASSET_COUNT="$ASSET_COUNT"
echo UPDATE_BYTES="$RBYTES"
echo UPDATE_SHA256="$RSHA"
echo FORMAL_TAG_SHA="$TAGSHA"
echo FORMAL_RELEASE_REMOTE_READBACK=PASS
echo CORE_UPDATES_WRITE=NO
echo PRODUCTION_WRITE=NO
