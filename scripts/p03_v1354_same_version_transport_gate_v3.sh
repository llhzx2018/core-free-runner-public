#!/usr/bin/env bash
set -Eeuo pipefail
BASE="harness/scripts/p03_v1354_same_version_transport_gate_v2.sh"
PATCHED="$RUNNER_TEMP/p03_v1354_same_version_transport_gate_v3.sh"
cp "$BASE" "$PATCHED"
python3 - "$PATCHED" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old='''code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); test "$code" = 409; grep -q 'Current Version/Schema must be exactly 1.35.4/30' "$GATE_ROOT/wrong-schema.html";'''
new='''grep -n "VFAB_SCHEMA_VERSION" "$RT/app/bootstrap.php"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); echo "WRONG_SCHEMA_HTTP=$code"; sed -n '1,20p' "$GATE_ROOT/wrong-schema.html"; test "$code" = 409; grep -q 'Current Version/Schema must be exactly 1.35.4/30' "$GATE_ROOT/wrong-schema.html";'''
if s.count(old)!=1: raise SystemExit(f'WRONG_SCHEMA_DIAG_ANCHOR_COUNT={s.count(old)}')
p.write_text(s.replace(old,new,1))
PY
chmod +x "$PATCHED"
bash -n "$PATCHED"
bash "$PATCHED"
