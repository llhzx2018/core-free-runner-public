from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: p03_v1354_dist_r1_recovery_normalize.py <gate.sh>")
    path = Path(sys.argv[1])
    s = path.read_text(encoding="utf-8")

    login_anchor = """python3 - \"$REC_ROOT/login.json\" <<'PY'\nimport json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.3'\nPY\ncat >\"$REC_ROOT/publish.php\" <<'PHP'\n"""
    snapshot_block = """python3 - \"$REC_ROOT/login.json\" <<'PY'\nimport json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.3'\nPY\npython3 - \"$REC_RT\" \"$REC_ROOT/pre-upgrade-source.json\" <<'PY'\nimport base64,json,sys\nfrom pathlib import Path\nroot=Path(sys.argv[1]);out=Path(sys.argv[2]);snap={}\nfor p in root.rglob('*'):\n    if not p.is_file(): continue\n    rel=p.relative_to(root).as_posix()\n    if rel=='app/.runtime.php' or rel.startswith('repair-v'): continue\n    snap[rel]=base64.b64encode(p.read_bytes()).decode()\nout.write_text(json.dumps(snap,sort_keys=True),encoding='utf-8')\nprint(f'RECOVERY_PRE_UPGRADE_SOURCE_SNAPSHOT=PASS files={len(snap)}')\nPY\ncat >\"$REC_ROOT/publish.php\" <<'PHP'\n"""
    if s.count(login_anchor) != 1:
        raise RuntimeError("recovery login anchor mismatch")
    s = s.replace(login_anchor, snapshot_block, 1)

    pattern = re.compile(
        r"python3 - \"\$GATE_ROOT/runtime-production\" \"\$REC_RT\" <<'PY'\n"
        r"import sys\nfrom pathlib import Path\n"
        r"a=Path\(sys\.argv\[1\]\);b=Path\(sys\.argv\[2\]\);base=\{p\.relative_to\(a\)\.as_posix\(\):p\.read_bytes\(\) for p in a\.rglob\('\*'\) if p\.is_file\(\)\}\n"
        r"cur=\{p\.relative_to\(b\)\.as_posix\(\):p\.read_bytes\(\) for p in b\.rglob\('\*'\) if p\.is_file\(\) and p\.relative_to\(b\)\.as_posix\(\) not in \{'app/\.runtime\.php','repair-v1\.35\.4\.php'\}\}\n"
        r"assert cur==base,\(set\(cur\)-set\(base\),set\(base\)-set\(cur\)\)\n"
        r"print\('FAILURE_RECOVERY_SOURCE_EXACT=PASS'\)\nPY"
    )
    replacement = """python3 - \"$REC_ROOT/pre-upgrade-source.json\" \"$REC_RT\" <<'PY'\nimport base64,json,sys\nfrom pathlib import Path\nbase={k:base64.b64decode(v) for k,v in json.load(open(sys.argv[1],encoding='utf-8')).items()}\nb=Path(sys.argv[2]);cur={}\nfor p in b.rglob('*'):\n    if not p.is_file(): continue\n    rel=p.relative_to(b).as_posix()\n    if rel=='app/.runtime.php' or rel=='repair-v1.35.4.php': continue\n    cur[rel]=p.read_bytes()\nassert cur==base,(set(cur)-set(base),set(base)-set(cur))\nprint('FAILURE_RECOVERY_SOURCE_EXACT=PASS')\nPY"""
    s2, n = pattern.subn(replacement, s, count=1)
    if n != 1:
        raise RuntimeError(f"recovery comparison block mismatch: {n}")

    path.write_text(s2, encoding="utf-8")
    print("DIST_R1_RECOVERY_NORMALIZATION=PASS baseline=installed_pre_upgrade_runtime")


if __name__ == "__main__":
    main()
