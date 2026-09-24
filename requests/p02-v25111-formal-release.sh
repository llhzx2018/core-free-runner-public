#!/usr/bin/env bash
set -Eeuo pipefail

REPO="llhzx2018/vf-library"
TAG="v2.5.111"
VERSION="2.5.111"
SOURCE_SHA="a4d55bd24824e7ca61e2fb79cd0d0e20e708279c"
SOURCE_TREE="d877754100828d130fa01c953a7c9a3e108ab6d4"
PRODUCT="$PWD/product"
OUT="$PRODUCT/build/formal-release"
REMOTE="$RUNNER_TEMP/p02-v25111-remote-release"

: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN is required}"
export GH_TOKEN="$VF_RELEASE_WRITE_TOKEN"

cd "$PRODUCT"
test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
test "$(git show -s --format=%T HEAD)" = "$SOURCE_TREE"
test "$(cat VERSION)" = "$VERSION"
python3 scripts/generate-source-manifest.py
git diff --exit-code -- SOURCE_MANIFEST.json SOURCE_MANIFEST.txt
python3 scripts/verify-source-manifest.py

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "Formal release already exists: $TAG" >&2
  exit 1
fi
if gh api "repos/$REPO/git/ref/tags/$TAG" >/dev/null 2>&1; then
  echo "Tag already exists without expected release: $TAG" >&2
  exit 1
fi

rm -rf "$OUT" "$REMOTE"
python3 scripts/build-release.py   --out build/formal-release   --source-version 2.5.81   --source-version 2.5.82   --source-version 2.5.102   --source-version 2.5.103   --source-version 2.5.104   --source-version 2.5.105   --source-commit "$SOURCE_SHA"   --source-tree "$SOURCE_TREE"   --source-ref main   --release-summary "Settings refinement batch: Basic, Content & Categories, Display & Sort, Search & Use, Import & Export, plus system-diagnostics navigation continuity."

cd "$OUT"
sha256sum -c SHA256SUMS.txt
for z in *.zip; do unzip -t "$z" >/dev/null; done

mapfile -t ASSETS < <(find . -maxdepth 1 -type f -printf '%f\n' | sort)
test "${#ASSETS[@]}" -eq 8

gh release create "$TAG"   --repo "$REPO"   --target "$SOURCE_SHA"   --title "P02 · VF Library V2.5.111"   --notes-file "VF_Library_V2.5.111_RELEASE_NOTES.md"   "${ASSETS[@]}"

TAG_SHA="$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq '.object.sha')"
test "$TAG_SHA" = "$SOURCE_SHA"

RELEASE_JSON="$RUNNER_TEMP/p02-v25111-release.json"
gh api "repos/$REPO/releases/tags/$TAG" > "$RELEASE_JSON"
python3 - "$RELEASE_JSON" "$SOURCE_SHA" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["tag_name"]=="v2.5.111"
assert x["draft"] is False
assert x["prerelease"] is False
assert x["target_commitish"]==sys.argv[2]
names=sorted(a["name"] for a in x["assets"])
expected=sorted([
 "VF_Library_V2.5.111_ATOMIC.zip",
 "VF_Library_V2.5.111_FULL.zip",
 "VF_Library_V2.5.111_RELEASE_MANIFEST.json",
 "VF_Library_V2.5.111_RELEASE_NOTES.md",
 "VF_Library_V2.5.111_SOURCE.zip",
 "VF_Library_V2.5.111_UPDATE.zip",
 "repair-v2.5.111.php",
 "SHA256SUMS.txt",
])
assert names==expected,(names,expected)
assert all(int(a["size"])>0 for a in x["assets"])
print("P02_V25111_RELEASE_METADATA=PASS")
print("RELEASE_ID="+str(x["id"]))
PY

mkdir -p "$REMOTE"
gh release download "$TAG" --repo "$REPO" --dir "$REMOTE"
cp SHA256SUMS.txt "$REMOTE/EXPECTED_SHA256SUMS.txt"
(
  cd "$REMOTE"
  sha256sum -c EXPECTED_SHA256SUMS.txt
)
python3 - "$OUT" "$REMOTE" <<'PY'
import hashlib,sys
from pathlib import Path
a,b=map(Path,sys.argv[1:3])
names=[p.name for p in a.iterdir() if p.is_file()]
for name in names:
    if name=="SHA256SUMS.txt":
        pass
    pa=a/name; pb=b/name
    assert pb.exists(),name
    assert pa.stat().st_size==pb.stat().st_size,name
    assert hashlib.sha256(pa.read_bytes()).hexdigest()==hashlib.sha256(pb.read_bytes()).hexdigest(),name
print("P02_V25111_REMOTE_ASSET_READBACK=PASS")
PY

echo "P02_V25111_FORMAL_RELEASE=PASS"
