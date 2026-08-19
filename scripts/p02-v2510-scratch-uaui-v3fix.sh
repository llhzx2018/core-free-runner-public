#!/usr/bin/env bash
set -Eeuo pipefail
sed -i '/^git fetch origin feature\/v2\.5\.10-scratch-uaui$/d;/^git checkout -B feature\/v2\.5\.10-scratch-uaui origin\/feature\/v2\.5\.10-scratch-uaui$/d' scripts/p02-v2510-scratch-uaui-v3.sh
python3 - <<'PY'
from pathlib import Path
p=Path('scripts/p02-v2510-scratch-uaui-v3.sh')
s=p.read_text(encoding='utf-8')
s=s.replace("p.write_text(c.rstrip()+override+'\\n',encoding='utf-8')","p.write_text((c.rstrip()+override).rstrip()+'\\n',encoding='utf-8')")
p.write_text(s,encoding='utf-8')
PY
bash scripts/p02-v2510-scratch-uaui-v3.sh
