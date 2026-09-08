#!/usr/bin/env bash
set -Eeuo pipefail
cp scripts/temp_s01_theme_update_center_v4_candidate_20260907.sh /tmp/s01_update_center_v4_gate.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/s01_update_center_v4_gate.sh')
lines = p.read_text().splitlines()
out = []
credential_changed = 0
injected = 0
for line in lines:
    if line.startswith('$credentialPosition = strpos($admin,'):
        out.append("$credentialPosition = strpos($admin, '$credentialConfigured = !empty($credential[\\'configured\\']);');")
        credential_changed += 1
        continue
    out.append(line)
    if line == "s = t.read_text()" and injected == 0:
        out.append("assert s.count(\"    '每个组件仍独立发布、独立验证，也能独立恢复。',\") == 1")
        out.append("s = s.replace(\"    '每个组件仍独立发布、独立验证，也能独立恢复。',\", \"    '发布、验证与恢复仍保持独立。',\", 1)")
        injected += 1
assert credential_changed == 1, credential_changed
assert injected == 1, injected
p.write_text('\n'.join(out) + '\n')
PY
bash /tmp/s01_update_center_v4_gate.sh
