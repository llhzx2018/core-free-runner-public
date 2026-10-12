#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(git -C m3target rev-parse HEAD)" = "$M3_SHA"
test "$(git -C m3target rev-parse HEAD^{tree})" = "$M3_TREE"
python3 lane/theme-build.py
mkdir -p m3run/lane
ln -s "$PWD/m3target" m3run/target
cp lane/base-channel.json m3run/lane/base-channel.json
(cd m3run && TARGET_SHA="$M3_SHA" TARGET_TREE="$M3_TREE" TARGET_VERSION="$M3_VERSION" SOURCE_VERSION="$M3_SOURCE_VERSION" python3 ../lane/m3-build.py)
cp m3run/proof/identity.json proof/m3-identity.json
cp "m3run/proof/vf-tools-m3u8_V$M3_VERSION.zip" proof/
python3 - <<'PY'
import json,pathlib,re
for name in ['identity.json','m3-identity.json']:
    built=json.loads((pathlib.Path('proof')/name).read_text())
    tested=json.loads((pathlib.Path('proof')/('tested-'+name)).read_text())
    for key in ['source_sha','source_tree','version','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint']:
        assert built[key]==tested[key],(name,key)
for root in [pathlib.Path('target/src'),pathlib.Path('m3target/src')]:
    for p in root.rglob('*'):
        if p.is_file():
            assert not re.search(rb'gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}',p.read_bytes()),str(p)
print('PASS deterministic rebuild equals both tested candidate assets; secret scan')
PY
