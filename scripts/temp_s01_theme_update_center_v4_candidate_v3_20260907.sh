#!/usr/bin/env bash
set -Eeuo pipefail
cp scripts/temp_s01_theme_update_center_v4_candidate_20260907.sh /tmp/s01_update_center_v4_gate.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/s01_update_center_v4_gate.sh')
lines = p.read_text().splitlines()
out = []
credential_changed = 0
copy_changed = 0
for line in lines:
    if line.startswith('$credentialPosition = strpos($admin,'):
        out.append("$credentialPosition = strpos($admin, '$credentialConfigured = !empty($credential[\\'configured\\']);');")
        credential_changed += 1
    elif "'每个组件仍独立发布、独立验证，也能独立恢复。'," in line:
        out.append(line.replace("'每个组件仍独立发布、独立验证，也能独立恢复。',", "'发布、验证与恢复仍保持独立。',"))
        copy_changed += 1
    else:
        out.append(line)
assert credential_changed == 1, credential_changed
assert copy_changed == 1, copy_changed
p.write_text('\n'.join(out) + '\n')
PY
bash /tmp/s01_update_center_v4_gate.sh
