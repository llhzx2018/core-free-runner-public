#!/usr/bin/env bash
set -Eeuo pipefail

REPO="llhzx2018/vf-library"
TAG="v2.5.122"
VERSION="2.5.122"
SOURCE_SHA="36fc7cc80f7c1acda20d34af18d96b4cb5fa23b4"
SOURCE_TREE="49a9923b1eb39074c4a26ee4be07c65b814049c3"
PRODUCT="$PWD/product"
OUT="$PRODUCT/build/formal-release"
REMOTE="$RUNNER_TEMP/p02-v25122-remote-release"

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
python3 scripts/build-release.py   --out build/formal-release   --source-version 2.5.81   --source-version 2.5.82   --source-version 2.5.102   --source-version 2.5.103   --source-version 2.5.104   --source-version 2.5.105   --source-version 2.5.111   --source-version 2.5.112   --source-version 2.5.113   --source-version 2.5.114   --source-version 2.5.115   --source-version 2.5.116   --source-version 2.5.117   --source-version 2.5.118   --source-version 2.5.119   --source-version 2.5.120   --source-version 2.5.121   --source-commit "$SOURCE_SHA"   --source-tree "$SOURCE_TREE"   --source-ref main   --release-summary "Settings Production horizontal closure: keep the nine-page IA while aligning Basic and Content paired settings, de-noising normal Import capability state, compacting Import refresh, and removing inherited spacing from System background jobs. Production-screenshot findings are closed without changing Schema, data model, auth, update mechanism, or page ownership. Schema remains 2401 with no migration."

cd "$OUT"
sha256sum -c SHA256SUMS.txt
for z in *.zip; do unzip -t "$z" >/dev/null; done
mapfile -t ASSETS < <(find . -maxdepth 1 -type f -printf '%f\n' | sort)
test "${#ASSETS[@]}" -eq 8

gh release create "$TAG" --repo "$REPO" --target "$SOURCE_SHA" --title "P02 · VF Library V2.5.122" --notes-file "VF_Library_V2.5.122_RELEASE_NOTES.md" "${ASSETS[@]}"

TAG_SHA="$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq '.object.sha')"
test "$TAG_SHA" = "$SOURCE_SHA"
RELEASE_JSON="$RUNNER_TEMP/p02-v25122-release.json"
gh api "repos/$REPO/releases/tags/$TAG" > "$RELEASE_JSON"

python3 - "$RELEASE_JSON" "$SOURCE_SHA" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["tag_name"]=="v2.5.122"
assert x["draft"] is False and x["prerelease"] is False
assert x["target_commitish"]==sys.argv[2]
expected=sorted([
 "VF_Library_V2.5.122_ATOMIC.zip",
 "VF_Library_V2.5.122_FULL.zip",
 "VF_Library_V2.5.122_RELEASE_MANIFEST.json",
 "VF_Library_V2.5.122_RELEASE_NOTES.md",
 "VF_Library_V2.5.122_SOURCE.zip",
 "VF_Library_V2.5.122_UPDATE.zip",
 "repair-v2.5.122.php",
 "SHA256SUMS.txt",
])
assert sorted(a["name"] for a in x["assets"])==expected
assert all(int(a["size"])>0 for a in x["assets"])
print("P02_V25122_RELEASE_METADATA=PASS")
print("RELEASE_ID="+str(x["id"]))
PY

mkdir -p "$REMOTE"
gh release download "$TAG" --repo "$REPO" --dir "$REMOTE"
cp SHA256SUMS.txt "$REMOTE/EXPECTED_SHA256SUMS.txt"
( cd "$REMOTE" && sha256sum -c EXPECTED_SHA256SUMS.txt )
python3 - "$OUT" "$REMOTE" <<'PY'
import hashlib,sys
from pathlib import Path
a,b=map(Path,sys.argv[1:3])
for p in a.iterdir():
    if not p.is_file(): continue
    q=b/p.name
    assert q.exists(),p.name
    assert p.stat().st_size==q.stat().st_size,p.name
    assert hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256(q.read_bytes()).hexdigest(),p.name
print("P02_V25122_REMOTE_ASSET_READBACK=PASS")
PY

echo "P02_V25122_FORMAL_RELEASE=PASS"
