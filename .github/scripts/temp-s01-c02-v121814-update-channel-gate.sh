#!/usr/bin/env bash
set -Eeuo pipefail
BASE=9a4939f5432347051b112201bce0755d760c1869
CANDIDATE=25de04079a570178055fc31108e6c51559e9c8c5
OPS=3a89aca6ea87e0bfabeab2cc414388ad3188bd9a
ASSET_SHA=c4da72b16a6ab2abe3886240528d9e778cb1614a6cbcdd308c0e86e4bfdd2550
RUNTIME_FP=696059d885ec9516f7d1d44aa325161a0ec6328e089a82a7c335eb6af8eec37a

test "$(git rev-parse HEAD)" = "$CANDIDATE"
test "$(git merge-base "$BASE" "$CANDIDATE")" = "$BASE"
test "$(git diff --name-only "$BASE" "$CANDIDATE")" = 'projects/S01-C02.json'

echo UPDATE_SCOPE=PASS

jq -e '
 .schema_version=="wp-component-1.0" and
 .project_id=="S01" and .component_id=="S01-C02" and
 .target_version=="1.21.814" and
 .from_versions==["1.21.813"] and
 .release_tag=="v1.21.814" and
 .asset_name=="vf-tools-ops_V1.21.814.zip" and
 .asset_bytes==3226305 and
 .asset_sha256=="c4da72b16a6ab2abe3886240528d9e778cb1614a6cbcdd308c0e86e4bfdd2550" and
 .schema_from=="6.0.0" and .schema_to=="6.0.0" and
 .physical_locator=="vf-ops/vf-ops.php" and
 .runtime_files==901 and .runtime_file_count==901 and
 .runtime_fingerprint=="696059d885ec9516f7d1d44aa325161a0ec6328e089a82a7c335eb6af8eec37a" and
 .runtime_fingerprint_sha256=="696059d885ec9516f7d1d44aa325161a0ec6328e089a82a7c335eb6af8eec37a" and
 .released_at=="2026-09-05T05:55:50Z"
' projects/S01-C02.json >/dev/null

grep -Fq 'Candidate Gate 33948382374 PASS' projects/S01-C02.json
grep -Fq 'Formal Release 33948457392 PASS' projects/S01-C02.json
grep -Fq 'Release ID 383149876; asset ID 545435826' projects/S01-C02.json
grep -Fq 'does not require re-upload of an existing Static Source ZIP' projects/S01-C02.json

echo MANIFEST_CONTRACT=PASS

api(){ curl -fsSL -H "Authorization: Bearer ${R}" -H 'Accept: application/vnd.github+json' "$1"; }
release=$(api 'https://api.github.com/repos/llhzx2018/vf-tools-ops/releases/tags/v1.21.814')
test "$(jq -r '.target_commitish' <<<"$release")" = "$OPS"
test "$(jq -r '.id' <<<"$release")" = '383149876'
test "$(jq -r '.assets[0].id' <<<"$release")" = '545435826'
test "$(jq -r '.assets[0].name' <<<"$release")" = 'vf-tools-ops_V1.21.814.zip'
test "$(jq -r '.assets[0].size' <<<"$release")" = '3226305'
test "$(jq -r '.assets[0].digest' <<<"$release")" = "sha256:${ASSET_SHA}"

echo FORMAL_RELEASE_ASSET=PASS

for br in main develop; do
  test "$(api "https://api.github.com/repos/llhzx2018/vf-tools-ops/branches/${br}" | jq -r '.commit.sha')" = "$OPS"
done

echo OPS_PROMOTED_SOURCE=PASS

prod=$(curl -fsSL 'https://www3.m3u8.one/wp-json/vf-ops/v1/s01-static-candidate-readiness')
test "$(jq -r '.pluginVersion // empty' <<<"$prod")" = '1.21.813'
echo DIRECT_PRODUCTION_1_21_813_ONLY=PASS

echo PASS_V121814_UPDATE_CHANNEL_GATE
