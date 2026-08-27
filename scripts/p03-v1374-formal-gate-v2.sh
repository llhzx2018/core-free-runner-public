#!/usr/bin/env bash
set -Eeuo pipefail
TMP="$RUNNER_TEMP/p03-v1374-formal-gate-v2.sh"
cp scripts/p03-v1374-formal-gate.sh "$TMP"
python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
marker="log 'Browser E2E responsive regression'"
insert="""log 'Install Browser E2E dependency after source/privacy gates'\nnpm init -y >/dev/null 2>&1\nnpm install --no-save playwright@1.55.0 >/dev/null\nnpx playwright install --with-deps chromium >/dev/null\n\nlog 'Browser E2E responsive regression'"""
assert s.count(marker)==1
p.write_text(s.replace(marker,insert,1),encoding='utf-8')
PY
exec bash "$TMP"
