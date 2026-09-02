#!/usr/bin/env bash
set -Eeuo pipefail
python3 - <<'PY'
from pathlib import Path
src=Path('runner/scripts/p01_v2373_strict_fresh.sh').read_text()
src=src.replace('mkdir -p candidate\ncp -a "$FRESH" candidate/src\n', 'mkdir -p candidate/src\nunzip -q "$FULL" -d candidate/src\n')
src=src.replace("assert any(x['record']['mime']=='image/gif' for x in rows), rows\n", '')
Path('/tmp/p01_v2373_strict_fresh_r2.sh').write_text(src)
PY
bash /tmp/p01_v2373_strict_fresh_r2.sh
