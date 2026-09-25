#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT="$PWD/product"
REPO="llhzx2018/vf-library"
SOURCE_SHA="46d0fd07bc977e02bcec626fa97491bd85e42331"
TARGET_BRANCH="chore/p02-v25121-source-manifest-20260925"

: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN is required}"

cd "$PRODUCT"
test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
test "$(cat VERSION)" = "2.5.121"

python3 scripts/generate-source-manifest.py
python3 scripts/verify-source-manifest.py

mapfile -t CHANGED < <(git diff --name-only)
printf 'CHANGED=%s\n' "${CHANGED[*]}"
test "${#CHANGED[@]}" -eq 2
printf '%s\n' "${CHANGED[@]}" | sort | diff -u <(printf '%s\n' SOURCE_MANIFEST.json SOURCE_MANIFEST.txt | sort) -

git config user.name "VictorForge"
git config user.email "llhzx2018@gmail.com"
git checkout -b "$TARGET_BRANCH"
git add SOURCE_MANIFEST.json SOURCE_MANIFEST.txt
git commit -m "chore(P02): refresh V2.5.121 source manifest"

git remote set-url origin "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/${REPO}.git"
git push origin "$TARGET_BRANCH"

echo P02_V25121_SOURCE_MANIFEST_SYNC=PASS
echo TARGET_BRANCH="$TARGET_BRANCH"
