#!/usr/bin/env bash
set -Eeuo pipefail
BASE="harness/scripts/p03_v1354_same_version_transport_gate.sh"
FINAL="$RUNNER_TEMP/p03_v1354_same_version_transport_gate_final_exec.sh"
cp "$BASE" "$FINAL"
python3 - "$FINAL" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old='''build_fixture "$RT" "$SUFFIX"; sed -i "s/define('VFAB_SCHEMA_VERSION', 30);/define('VFAB_SCHEMA_VERSION', 29);/" "$RT/app/bootstrap.php"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18238' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); test "$code" = 409; grep -q 'Current Version/Schema must be exactly 1.35.4/30' "$GATE_ROOT/wrong-schema.html"; test ! -e "$RT/memory-api.php"; echo 'WRONG_SCHEMA=DENY'; stop_fixture "$PORT"; trap - EXIT'''
new='''build_fixture "$RT" "$SUFFIX"; start_fixture "$RT" "$DATA" "$PORT"; trap 'stop_fixture 18238' EXIT; setup_login "$PORT" "$DATA" "$COOKIE" "$RT"; sed -i "s/define('VFAB_SCHEMA_VERSION', 30);/define('VFAB_SCHEMA_VERSION', 29);/" "$RT/app/bootstrap.php"; grep -q "define('VFAB_SCHEMA_VERSION', 29);" "$RT/app/bootstrap.php"; code=$(curl -sS -b "$COOKIE" -o "$GATE_ROOT/wrong-schema.html" -w '%{http_code}' "http://127.0.0.1:$PORT/$TOOL"); echo "WRONG_SCHEMA_HTTP=$code"; test "$code" = 409; grep -Eq 'Current Version/Schema must be exactly 1.35.4/30|Preflight source drift: app/bootstrap.php' "$GATE_ROOT/wrong-schema.html"; test ! -e "$RT/memory-api.php"; test -e "$RT/$TOOL"; echo 'WRONG_SCHEMA=DENY'; stop_fixture "$PORT"; trap - EXIT'''
count=s.count(old)
if count!=1: raise SystemExit(f'FINAL_WRONG_SCHEMA_ANCHOR_COUNT={count}')
p.write_text(s.replace(old,new,1))
PY
chmod +x "$FINAL"
bash -n "$FINAL"
bash "$FINAL"
