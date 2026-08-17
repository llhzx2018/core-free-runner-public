#!/usr/bin/env bash
set -Eeuo pipefail

BASE="harness/scripts/p03_v1354_source_exact_corrective_gate_v2.sh"
PATCHED="$RUNNER_TEMP/p03_v1354_source_exact_corrective_gate_v3.sh"
cp "$BASE" "$PATCHED"
python3 - "$PATCHED" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old='''grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"; curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $b" -H 'Content-Type: application/json' --data "{\\"password\\":\\"$FIXTURE_PASS\\"}" "$b/api.php?action=login" > "$GATE_ROOT/login-$port.json"'''
new='''grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/setup-post-$port.txt"; test ! -e "$RT/index.html"; cp "$GATE_ROOT/frozen/index.html" "$RT/index.html"; cmp "$GATE_ROOT/frozen/index.html" "$RT/index.html"; echo 'POST_SETUP_INDEX_RESTORED_TO_POST_UPGRADE_FIXTURE=PASS'; curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $b" -H 'Content-Type: application/json' --data "{\\"password\\":\\"$FIXTURE_PASS\\"}" "$b/api.php?action=login" > "$GATE_ROOT/login-$port.json"'''
if s.count(old)!=1: raise SystemExit(f'fixture patch anchor count={s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
PY
chmod +x "$PATCHED"
bash -n "$PATCHED"
bash "$PATCHED"
