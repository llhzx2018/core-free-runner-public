#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
python3 lane/m3-build.py
python3 - <<'PY'
import json,pathlib
built=json.loads(pathlib.Path('proof/identity.json').read_text())
tested=json.loads(pathlib.Path('proof/tested-m3-identity.json').read_text())
for key in ['source_sha','source_tree','version','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint']:
 assert built[key]==tested[key],key
print('PASS deterministic M3U8 rebuild equals tested candidate asset')
PY

