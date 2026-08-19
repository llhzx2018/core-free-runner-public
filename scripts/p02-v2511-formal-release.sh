#!/usr/bin/env bash
set -Eeuo pipefail
TMP="$RUNNER_TEMP/p02-v2511-formal-release.sh"
cp scripts/p02-v2510-formal-release.sh "$TMP"
python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(encoding='utf-8')
s=s.replace('2.5.10','2.5.11')
s=s.replace('32225789953','32227564011')
# Keep the formal notes tied to the actual final OWNER UX refinement.
old='''V2.5.11 refines Scratch Tabs UX/UI after the V2.5.9 Notepad-replacement layer entered real personal use.\n\n- Scratch workspace uses an immersive low-noise header while active.\n- The launcher is simplified from “临时 + count” to “临时 count”.\n- Tabs are denser and more Notepad-like; inactive close controls stay visually quiet.\n- The tab strip hides the horizontal scrollbar and supports wheel-based horizontal navigation.\n- Actions are condensed to 最近关闭 / 整理 / 返回 and autosave status to 已保存.\n- Typing updates only the active tab title instead of rebuilding the entire tab strip on every keystroke.\n- Candidate real-browser Run 32227564011 passed desktop/mobile UX/UI, multi-tab, autosave and Fresh Install gates.'''
new='''V2.5.11 is the superseding Scratch Tabs UX/UI release for Production V2.5.9. The previously published V2.5.10 release was not installed by OWNER and its update authority was disabled before this release.\n\n- Explicitly clicking a Scratch TAB opens that document at the top instead of restoring a prior bottom scroll position.\n- Desktop Scratch workspace uses one compact top row; the base VF Library header is hidden while Scratch mode is active.\n- The current document line count is shown together with autosave state, e.g. “42 行 · 已保存”.\n- Compact Notepad-like tabs, quiet close controls, wheel horizontal navigation and low-noise actions remain.\n- Typing updates only the active tab title instead of rebuilding the entire tab strip on every keystroke.\n- Candidate real-browser Run 32227564011 passed single-row chrome, TAB-top behavior, live line count, autosave, mobile overflow and Fresh Install gates.'''
if old in s:s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
PY
bash "$TMP"
