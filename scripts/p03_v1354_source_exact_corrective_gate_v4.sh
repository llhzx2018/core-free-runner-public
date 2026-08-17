#!/usr/bin/env bash
set -Eeuo pipefail

BASE="harness/scripts/p03_v1354_source_exact_corrective_gate_v2.sh"
PATCHED="$RUNNER_TEMP/p03_v1354_source_exact_corrective_gate_v4.sh"
cp "$BASE" "$PATCHED"
python3 - "$PATCHED" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old_fixture='''grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"; curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $b" -H 'Content-Type: application/json' --data "{\\"password\\":\\"$FIXTURE_PASS\\"}" "$b/api.php?action=login" > "$GATE_ROOT/login-$port.json"'''
new_fixture='''grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"; test ! -e "$RT/index.html"; cp "$GATE_ROOT/frozen/index.html" "$RT/index.html"; cmp "$GATE_ROOT/frozen/index.html" "$RT/index.html"; echo 'POST_SETUP_INDEX_RESTORED_TO_POST_UPGRADE_FIXTURE=PASS'; curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $b" -H 'Content-Type: application/json' --data "{\\"password\\":\\"$FIXTURE_PASS\\"}" "$b/api.php?action=login" > "$GATE_ROOT/login-$port.json"'''
if s.count(old_fixture)!=1: raise SystemExit(f'fixture patch anchor count={s.count(old_fixture)}')
s=s.replace(old_fixture,new_fixture,1)
old_path='''grep -q "version_compare(\\$target,\\$current,'>')" "$PRODUCT/app/ManualUpdateService.php"'''
new_path='''grep -q "version_compare(\\$target,\\$current,'>')" "$PRODUCT/src/app/ManualUpdateService.php"'''
if s.count(old_path)!=1: raise SystemExit(f'contract path anchor count={s.count(old_path)}')
s=s.replace(old_path,new_path,1)
p.write_text(s)
PY
chmod +x "$PATCHED"
bash -n "$PATCHED"
bash "$PATCHED"
