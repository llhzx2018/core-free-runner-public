#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT="$PWD/product"
SOURCE_SHA="3453596234f47207bc610141450e50bad295da61"
SOURCE_TREE="b875fa454923f0c4352e9ed20a37f4ea2c6a8c5e"
FROM_VERSIONS="2.5.81 2.5.82 2.5.102 2.5.103 2.5.104 2.5.105 2.5.111 2.5.112 2.5.113 2.5.114 2.5.115 2.5.116 2.5.117 2.5.118 2.5.119 2.5.120 2.5.121 2.5.122"

cd "$PRODUCT"
test "$(git show -s --format=%T "$SOURCE_SHA")" = "$SOURCE_TREE"
git checkout --detach "$SOURCE_SHA"
test "$(git rev-parse HEAD)" = "$SOURCE_SHA"
test "$(git show -s --format=%T HEAD)" = "$SOURCE_TREE"
test "$(cat VERSION)" = "2.5.123"
python3 scripts/generate-source-manifest.py
git diff --exit-code -- SOURCE_MANIFEST.json SOURCE_MANIFEST.txt
python3 scripts/verify-source-manifest.py

export VF_RELEASE_SOURCE_SHA="$SOURCE_SHA"
export VF_RELEASE_SOURCE_TREE="$SOURCE_TREE"
export VF_RELEASE_SOURCE_REF="main"
export VF_RELEASE_FROM_VERSIONS="$FROM_VERSIONS"
bash scripts/verify-release-artifacts.sh
echo P02_V25123_DETERMINISTIC_RELEASE_PREFLIGHT=PASS

cd "$PWD/.."
TMP_MATRIX="$RUNNER_TEMP/p02-v25123-upgrade-matrix.sh"
sed   -e 's/TARGET="2.5.121"/TARGET="2.5.123"/'   -e 's/SOURCES=(2.5.81 2.5.82 2.5.102 2.5.103 2.5.104 2.5.105 2.5.111 2.5.112 2.5.113 2.5.114 2.5.115 2.5.116 2.5.117 2.5.118 2.5.119 2.5.120)/SOURCES=(2.5.81 2.5.82 2.5.102 2.5.103 2.5.104 2.5.105 2.5.111 2.5.112 2.5.113 2.5.114 2.5.115 2.5.116 2.5.117 2.5.118 2.5.119 2.5.120 2.5.121 2.5.122)/'   -e 's/p02-v25121/p02-v25123/g'   -e 's/P02-V25121/P02-V25123/g'   -e 's/V25121/V25123/g'   -e 's/P02_V25121/P02_V25123/g'   -e 's/\.version=="2.5.121"/.version=="2.5.123"/g'   runner/requests/p02-v25121-upgrade-matrix.sh > "$TMP_MATRIX"
bash "$TMP_MATRIX"

echo P02_V25123_FORMAL_RELEASE_GATE=PASS
