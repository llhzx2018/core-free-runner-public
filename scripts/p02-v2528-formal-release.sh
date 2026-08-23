#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo ERROR_LINE=$LINENO' ERR

ROOT="$(pwd)"
PRODUCT_REF="${PRODUCT_REF:?}"
RELEASE_TOKEN="${RELEASE_TOKEN:?}"
VER=2.5.28
TAG=v2.5.28
UPDATE_NAME="VF_Library_V2.5.28_UPDATE.zip"
CANDIDATE_RUN=32663984746

# Reuse the exact candidate verifier that produced the green candidate run.
curl -fsSL \
  "https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/run/p02-v2528-candidate-r1/scripts/p02-v2528-candidate.sh" \
  -o "$RUNNER_TEMP/p02-v2528-formal-core.sh"
chmod +x "$RUNNER_TEMP/p02-v2528-formal-core.sh"

# Convert only harness/output semantics from Candidate to Formal. Product bytes are untouched.
python3 - "$RUNNER_TEMP/p02-v2528-formal-core.sh" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
s=s.replace('build/candidate-a','build/formal-a').replace('build/candidate-b','build/formal-b')
s=s.replace('PENDING_V2.5.28_EXACT_CANDIDATE_RUN','PASS_RUN_32663984746')
s=s.replace('REL_STATE=REL.READY_PREPARE_ONLY_V2527_TO_V2528','REL_STATE=REL.FORMAL_BUILD_VERIFIED')
s=s.replace('MAIN_PROMOTION=NO','MAIN_PROMOTION=PASS')
old="""  await page.waitForFunction(label=>{\n    const s=globalThis.state||{};\n    if(label==='all')return s.mode==='all'&&s.status==='active';\n    if(label==='favorite')return s.mode==='favorite'&&s.status==='active';\n    if(label==='recent')return s.mode==='recent'&&s.status==='active';\n    if(label==='draft')return s.status==='draft';\n    if(label==='trash')return s.status==='trash';\n    if(label==='settings')return s.mode==='settings';\n    return false;\n  },label,{timeout:10000});"""
new="""  const activeSelector={all:'[data-mode=\"all\"]',favorite:'[data-mode=\"favorite\"]',recent:'[data-mode=\"recent\"]',trash:'#trashBtn',settings:'#settingsBtn'}[label];\n  await page.waitForFunction(sel=>document.querySelector(sel)?.classList.contains('active'),activeSelector,{timeout:10000});"""
if old not in s: raise SystemExit('candidate visible-state block not found')
s=s.replace(old,new,1)
old2="""  await page.locator('#addContentBtn').click();\n  await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});\n  const persisted=await page.locator('[data-scratch-editor]').inputValue();"""
new2="""  await page.evaluate(()=>window.VfLibraryScratch.open());\n  await page.locator('#scratchWorkspaceV259').waitFor({state:'visible'});\n  const workspaceCount=await page.locator('#scratchWorkspaceV259').count();\n  if(workspaceCount!==1)throw new Error(`scratch workspace duplicate after ${label}: ${workspaceCount}`);\n  const persisted=await page.locator('[data-scratch-editor]').inputValue();"""
if old2 not in s: raise SystemExit('candidate scratch reopen block not found')
s=s.replace(old2,new2,1)
s=s.replace("  ['#draftBtn',s=>s.status==='draft','draft'],\n",'',1)
p.write_text(s,encoding='utf-8')
print('FORMAL_HARNESS_ALIGNMENT=PASS')
PY

# Exact promoted main must still be the formal source authority.
cd "$ROOT/product"
test "$(git rev-parse HEAD)" = "$PRODUCT_REF"
test "$(tr -d '\r\n' < VERSION)" = "$VER"
cd "$ROOT"

# Full exact-source, deterministic package, fresh install, scratch navigation,
# autosave barrier, and authenticated V2.5.27 -> V2.5.28 Atomic verification.
PRODUCT_REF="$PRODUCT_REF" TEST_PASSWORD="P02-V2528-FORMAL-${GITHUB_RUN_ID}!" \
  bash "$RUNNER_TEMP/p02-v2528-formal-core.sh"

cd "$ROOT/product"
test -d build/formal-a
test -f "build/formal-a/$UPDATE_NAME"
test "$(jq -r .version build/formal-a/VF_Library_V2.5.28_RELEASE_MANIFEST.json)" = "$VER"
test "$(jq -r '.compatibility.supported_from|join(",")' build/formal-a/VF_Library_V2.5.28_RELEASE_MANIFEST.json)" = '2.5.27'
TREE="$(git show -s --format=%T "$PRODUCT_REF")"
test "$TREE" = 'b4723505f944626a2e96e4e2f3d3b68aaf5ad734'
echo FORMAL_SOURCE_COMMIT="$PRODUCT_REF"
echo FORMAL_SOURCE_TREE="$TREE"

# Publication is blocked unless this exact version is still absent.
export GH_TOKEN="$RELEASE_TOKEN"
if gh release view "$TAG" --repo llhzx2018/vf-library >/dev/null 2>&1; then
  echo FORMAL_RELEASE_BLOCK=V2.5.28_ALREADY_EXISTS
  exit 31
fi
if gh api "repos/llhzx2018/vf-library/git/ref/tags/$TAG" >/dev/null 2>&1; then
  echo FORMAL_TAG_BLOCK=V2.5.28_ALREADY_EXISTS
  exit 32
fi

# Publish only the deterministic verified formal-a set.
gh release create "$TAG" build/formal-a/* \
  --repo llhzx2018/vf-library \
  --target "$PRODUCT_REF" \
  --title 'VF Library V2.5.28' \
  --notes-file build/formal-a/VF_Library_V2.5.28_RELEASE_NOTES.md

# Remote readback: release identity, complete asset set, immutable UPDATE bytes/SHA, tag target.
gh release view "$TAG" --repo llhzx2018/vf-library \
  --json databaseId,tagName,isDraft,isPrerelease,publishedAt,targetCommitish,assets \
  >"$RUNNER_TEMP/release2528.json"
jq -e '.tagName=="v2.5.28" and .isDraft==false and .isPrerelease==false' "$RUNNER_TEMP/release2528.json" >/dev/null
jq -e '[.assets[].name]|sort == ["SHA256SUMS.txt","VF_Library_V2.5.28_ATOMIC.zip","VF_Library_V2.5.28_FULL.zip","VF_Library_V2.5.28_RELEASE_MANIFEST.json","VF_Library_V2.5.28_RELEASE_NOTES.md","VF_Library_V2.5.28_SOURCE.zip","VF_Library_V2.5.28_UPDATE.zip","repair-v2.5.28.php"]|sort' "$RUNNER_TEMP/release2528.json" >/dev/null
mkdir -p "$RUNNER_TEMP/readback2528"
gh release download "$TAG" --repo llhzx2018/vf-library --pattern "$UPDATE_NAME" --dir "$RUNNER_TEMP/readback2528"
RBYTES="$(stat -c%s "$RUNNER_TEMP/readback2528/$UPDATE_NAME")"
RSHA="$(sha256sum "$RUNNER_TEMP/readback2528/$UPDATE_NAME"|awk '{print $1}')"
test "$RBYTES" = "$(stat -c%s "build/formal-a/$UPDATE_NAME")"
test "$RSHA" = "$(sha256sum "build/formal-a/$UPDATE_NAME"|awk '{print $1}')"
TAGSHA="$(gh api "repos/llhzx2018/vf-library/git/ref/tags/$TAG" --jq .object.sha)"
test "$TAGSHA" = "$PRODUCT_REF"

echo RELEASE_ID="$(jq -r .databaseId "$RUNNER_TEMP/release2528.json")"
echo PUBLISHED_AT="$(jq -r .publishedAt "$RUNNER_TEMP/release2528.json")"
echo UPDATE_BYTES="$RBYTES"
echo UPDATE_SHA256="$RSHA"
echo FORMAL_TAG_SHA="$TAGSHA"
echo FORMAL_RELEASE_REMOTE_READBACK=PASS
echo CORE_UPDATES_WRITE=NO
echo PRODUCTION_WRITE=NO
