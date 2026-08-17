#!/usr/bin/env python3
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8')

login_anchor = """python3 - \"$REC_ROOT/login.json\" <<'PY'\nimport json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.3'\nPY\ncat >\"$REC_ROOT/publish.php\" <<'PHP'\n"""
assert s.count(login_anchor) == 1, s.count(login_anchor)
replacement = """python3 - \"$REC_ROOT/login.json\" <<'PY'\nimport json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.3'\nPY\n# Recovery baseline must be the installed, authenticated V1.35.3 runtime immediately before upgrade.\n# setup.php intentionally removes the install-bootstrap index.html, so a pre-setup source tree is not a valid recovery target.\nREC_BASELINE=\"$REC_ROOT/runtime-pre-upgrade-baseline\"\nrm -rf \"$REC_BASELINE\"\ncp -a \"$REC_RT\" \"$REC_BASELINE\"\necho 'RECOVERY_PRE_UPGRADE_BASELINE=PASS'\ncat >\"$REC_ROOT/publish.php\" <<'PHP'\n"""
s = s.replace(login_anchor, replacement, 1)

old_compare = "python3 - \"$GATE_ROOT/runtime-production\" \"$REC_RT\" <<'PY'\n"
assert s.count(old_compare) == 1, s.count(old_compare)
s = s.replace(old_compare, "python3 - \"$REC_BASELINE\" \"$REC_RT\" <<'PY'\n", 1)

p.write_text(s, encoding='utf-8')
