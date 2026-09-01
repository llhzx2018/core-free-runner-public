#!/usr/bin/env bash
set -u

source_script="$GITHUB_WORKSPACE/runner/scripts/temp-s01-c02-owner-runtime-v2.sh"
instrumented=/tmp/vf-s01-owner-runtime-http-instrumented.sh

python3 - "$source_script" "$instrumented" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text(encoding='utf-8')
anchor = "rsync -a --delete --exclude='.git' ops/ \"$WP_PATH/wp-content/plugins/vf-ops/\"\n"
if anchor not in src:
    raise SystemExit('runtime instrumentation insertion anchor missing')
insert = anchor + "python3 \"$GITHUB_WORKSPACE/runner/scripts/temp-s01-c02-http-handler-instrument.py\" | tee \"$EVIDENCE_DIR/http-handler-instrumentation.txt\"\n"
src = src.replace(anchor, insert, 1)
Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
chmod +x "$instrumented"

set +e
bash "$instrumented"
rc=$?
set -e

if [ -f "$WP_PATH/wp-content/debug.log" ]; then
  cp "$WP_PATH/wp-content/debug.log" "$EVIDENCE_DIR/wordpress-debug-http-instrumented.log"
fi
if [ -f "$EVIDENCE_DIR/wp-server.log" ]; then
  grep -F 'S01_HTTP_REPAIR:' "$EVIDENCE_DIR/wp-server.log" > "$EVIDENCE_DIR/http-handler-markers.log" || true
fi
printf 'HTTP_INSTRUMENTED_RUNTIME_EXIT=%s\n' "$rc" > "$EVIDENCE_DIR/http-instrumented-runtime-exit.txt"
exit "$rc"
