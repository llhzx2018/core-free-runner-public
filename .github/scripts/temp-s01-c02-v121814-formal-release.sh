#!/usr/bin/env bash
set -Eeuo pipefail
CANDIDATE=3a89aca6ea87e0bfabeab2cc414388ad3188bd9a
EXPECTED_BYTES=3226305
EXPECTED_SHA=c4da72b16a6ab2abe3886240528d9e778cb1614a6cbcdd308c0e86e4bfdd2550
ASSET=vf-tools-ops_V1.21.814.zip
TAG=v1.21.814

main_sha="$(gh api repos/llhzx2018/vf-tools-ops/branches/main --jq .commit.sha)"
dev_sha="$(gh api repos/llhzx2018/vf-tools-ops/branches/develop --jq .commit.sha)"
test "$main_sha" = "$CANDIDATE"
test "$dev_sha" = "$CANDIDATE"
test "$(git rev-parse HEAD)" = "$CANDIDATE"
echo PROMOTED_SOURCE_IDENTITY=PASS

mkdir -p /tmp/v121814-release
python3 - <<'PY'
from pathlib import Path
import hashlib,re,zipfile
files=[]
for p in Path('.').rglob('*'):
    if not p.is_file() or p.is_symlink(): continue
    rel=p.as_posix().lstrip('./'); parts=rel.split('/')
    if any(x.lower() in {'.git','.github','test','tests','doc','docs','evidence','private','tmp','temp','cache','log','logs'} for x in parts): continue
    if re.search(r'\.(sql|sqlite|sqlite3|db|log|zip|tar|gz|bak|tmp)$',rel,re.I): continue
    if '/' not in rel:
        if rel not in {'vf-ops.php','uninstall.php'}: continue
    elif parts[0] not in {'includes','assets','languages','config'}: continue
    files.append((rel,p.read_bytes()))
files.sort(key=lambda x:x[0])
z=Path('/tmp/v121814-release/vf-tools-ops_V1.21.814.zip')
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as out:
    for rel,b in files:
        i=zipfile.ZipInfo('vf-ops/'+rel,(2026,9,5,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o100644<<16; out.writestr(i,b)
print(len(files), z.stat().st_size, hashlib.sha256(z.read_bytes()).hexdigest())
assert len(files)==901
PY
ZIP=/tmp/v121814-release/$ASSET
test "$(stat -c '%s' "$ZIP")" = "$EXPECTED_BYTES"
test "$(sha256sum "$ZIP" | awk '{print $1}')" = "$EXPECTED_SHA"
unzip -tq "$ZIP" >/dev/null
unzip -p "$ZIP" vf-ops/vf-ops.php | grep -Fq 'Version: 1.21.814'
echo EXACT_CANDIDATE_ARTIFACT=PASS

if gh release view "$TAG" --repo llhzx2018/vf-tools-ops >/dev/null 2>&1; then echo RELEASE_ALREADY_EXISTS; exit 1; fi
if gh api "repos/llhzx2018/vf-tools-ops/git/ref/tags/$TAG" >/dev/null 2>&1; then echo TAG_ALREADY_EXISTS; exit 1; fi

gh release create "$TAG" "$ZIP" \
  --repo llhzx2018/vf-tools-ops \
  --target "$CANDIDATE" \
  --title 'VF Tools Ops v1.21.814' \
  --notes 'S01-C02 Static Source Recovery V2. Fixes the proven lifecycle defect where ordinary Ops version upgrades performed full release-job cleanup and could delete an existing Static Source. Ordinary upgrades now preserve release jobs; explicit full cleanup and bounded TTL retention remain intact. If the historical Ops-private source was already removed, recovery scans only Simply Static official configured/default temp-files directory, requires a durable non-conflicting source SHA authority and exactly one byte-identical ZIP match, copies it into a fresh private inspect_only job, and re-runs the existing inspection pipeline under the existing per-job lock. Zero/ambiguous/hash-conflict cases remain fail-closed. Public readiness exposes safe aggregate recovery state only and never path/name/SHA/job identity. No M3U8 migration/schema/DB write, Seed HOLD release, JD.gg/WPvivid mutation, content write, Production activation or DNS write.'

j="$(gh api "repos/llhzx2018/vf-tools-ops/releases/tags/$TAG")"
test "$(jq -r '.target_commitish' <<<"$j")" = "$CANDIDATE"
test "$(jq -r '.draft' <<<"$j")" = false
test "$(jq -r '.prerelease' <<<"$j")" = false
test "$(jq -r --arg a "$ASSET" '.assets[]|select(.name==$a)|.size' <<<"$j")" = "$EXPECTED_BYTES"
test "$(jq -r --arg a "$ASSET" '.assets[]|select(.name==$a)|.digest' <<<"$j")" = "sha256:$EXPECTED_SHA"
echo RELEASE_ID="$(jq -r '.id' <<<"$j")"
echo ASSET_ID="$(jq -r --arg a "$ASSET" '.assets[]|select(.name==$a)|.id' <<<"$j")"
echo PUBLISHED_AT="$(jq -r '.published_at' <<<"$j")"
echo PASS_V121814_FORMAL_RELEASE
