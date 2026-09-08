#!/usr/bin/env bash
set -Eeuo pipefail
cp scripts/temp_s01_theme_update_center_v4_candidate_v5_20260907.sh /tmp/s01_update_center_v4_gate_v5.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/s01_update_center_v4_gate_v5.sh')
s = p.read_text()
assert s.count('minmax(310px, 1fr)') == 1
assert s.count('min-height: 36px;') == 1
s = s.replace('minmax(310px, 1fr)', 'minmax(300px, 1fr)', 1)
s = s.replace('min-height: 36px;', 'min-height: 40px;', 1)
p.write_text(s)
PY
bash /tmp/s01_update_center_v4_gate_v5.sh
