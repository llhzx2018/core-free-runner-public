#!/usr/bin/env bash
set -Eeuo pipefail
BASE="harness/scripts/p03_v1354_same_version_transport_gate.sh"
PATCHED="$RUNNER_TEMP/p03_v1354_same_version_transport_gate_v2.sh"
cp "$BASE" "$PATCHED"
python3 - "$PATCHED" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
old='''build_fixture "$RT" "$SUFFIX"; sed -i "s/define('VFAB_SCHEMA_VERSION', 30);/define('VFAB_SCHEMA_VERSION', 29);/" "$RT/app/bootstrap.php"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18238' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL");'''
new='''build_fixture "$RT" "$SUFFIX"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18238' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; sed -i "s/define('VFAB_SCHEMA_VERSION', 30);/define('VFAB_SCHEMA_VERSION', 29);/" "$RT/app/bootstrap.php"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL");'''
if s.count(old)!=1: raise SystemExit(f'WRONG_SCHEMA_PATCH_ANCHOR_COUNT={s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
PY
chmod +x "$PATCHED"
bash -n "$PATCHED"
bash "$PATCHED"
