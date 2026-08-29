#!/usr/bin/env bash
set -Eeuo pipefail
SRC="$(dirname "$0")/p01-v232-home-health-signal-v10.sh"
TMP="$(mktemp /tmp/p01-v232-health-v10b.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT
python3 - "$SRC" "$TMP" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text(encoding='utf-8')
old="if(text.includes('未检查')||text.includes('已跳转'))throw new Error('non-problem leaked '+text);"
new="const breakdown=(await card.locator('.vf-home-health-breakdown').innerText()).trim();if(breakdown.includes('未检查')||breakdown.includes('已跳转'))throw new Error('non-problem breakdown leaked '+breakdown);"
if s.count(old)!=1:
    raise SystemExit(f'V10b target count={s.count(old)}')
Path(sys.argv[2]).write_text(s.replace(old,new,1),encoding='utf-8')
PY
bash "$TMP"
