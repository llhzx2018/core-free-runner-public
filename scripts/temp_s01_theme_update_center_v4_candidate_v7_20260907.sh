#!/usr/bin/env bash
set -Eeuo pipefail
cp scripts/temp_s01_theme_update_center_v4_candidate_20260907.sh /tmp/s01_update_center_v4_gate.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/s01_update_center_v4_gate.sh')
lines = p.read_text().splitlines()
out = []
credential_changed = 0
contracts_injected = 0
for line in lines:
    if line.startswith('$credentialPosition = strpos($admin,'):
        out.append("$credentialPosition = strpos($admin, '$credentialConfigured = !empty($credential[\\'configured\\']);');")
        credential_changed += 1
        continue
    out.append(line)
    if line == "s = t.read_text()" and contracts_injected == 0:
        out.append("assert s.count(\"    '每个组件仍独立发布、独立验证，也能独立恢复。',\") == 1")
        out.append("s = s.replace(\"    '每个组件仍独立发布、独立验证，也能独立恢复。',\", \"    '发布、验证与恢复仍保持独立。',\", 1)")
        out.append("assert s.count(\"    'VF 在线更新使用私有发布源。保存凭证后，再检查组件更新。',\") == 1")
        out.append("s = s.replace(\"    'VF 在线更新使用私有发布源。保存凭证后，再检查组件更新。',\", \"    'VF 在线更新使用私有发布源。凭证只需配置一次，保存后即可检查全部组件。',\", 1)")
        contracts_injected += 1
assert credential_changed == 1, credential_changed
assert contracts_injected == 1, contracts_injected
s = '\n'.join(out) + '\n'
assert 'grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));' in s
s = s.replace('grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));', 'grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));', 1)
assert 'min-height: 36px;' in s
s = s.replace('min-height: 36px;', 'min-height: 40px;', 1)
p.write_text(s)
PY
bash /tmp/s01_update_center_v4_gate.sh
