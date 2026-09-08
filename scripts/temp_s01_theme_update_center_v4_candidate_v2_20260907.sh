#!/usr/bin/env bash
set -Eeuo pipefail
cp scripts/temp_s01_theme_update_center_v4_candidate_20260907.sh /tmp/s01_update_center_v4_gate.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/s01_update_center_v4_gate.sh')
lines = p.read_text().splitlines()
out = []
changed = 0
for line in lines:
    if line.startswith('$credentialPosition = strpos($admin,'):
        out.append("$credentialPosition = strpos($admin, '$credentialConfigured = !empty($credential[\\'configured\\']);');")
        changed += 1
    else:
        out.append(line)
assert changed == 1, changed
p.write_text('\n'.join(out) + '\n')
PY
bash /tmp/s01_update_center_v4_gate.sh
