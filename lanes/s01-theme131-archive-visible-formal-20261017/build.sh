#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
python3 lane/theme-build.py
python3 - <<'PYBUILD'
import json,pathlib,re,os
built=json.loads(pathlib.Path('proof/identity.json').read_text())
tested=json.loads(pathlib.Path('proof/tested-identity.json').read_text())
assert tested['source_sha']==os.environ['TESTED_SHA']
assert built['source_sha']==os.environ['TARGET_SHA']
for key in ['source_tree','version','asset_bytes','asset_sha256','runtime_files','runtime_fingerprint']:
    assert built[key]==tested[key],key
for p in pathlib.Path('target/src').rglob('*'):
    if p.is_file():
        assert not re.search(rb'gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}',p.read_bytes()),str(p)
print('PASS deterministic Theme rebuild equals tested candidate asset; full source tree equality; secret scan')
PYBUILD
