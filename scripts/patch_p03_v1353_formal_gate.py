#!/usr/bin/env python3
from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else 'scripts/p03_v1353_formal_gate.sh')
s = p.read_text(encoding='utf-8')

old_scope = '  local suffix="$1" port="$2" runtime="$GATE_ROOT/$suffix-runtime" data="$GATE_ROOT/$suffix-data" cookie="$GATE_ROOT/$suffix-cookie" base="http://127.0.0.1:$port" name="p03-$suffix"'
new_scope = '  local suffix="$1" port="$2"\n  local runtime="$GATE_ROOT/${suffix}-runtime" data="$GATE_ROOT/${suffix}-data" cookie="$GATE_ROOT/${suffix}-cookie" base="http://127.0.0.1:${port}" name="p03-${suffix}"'
if s.count(old_scope) != 1:
    raise SystemExit('expected harness scope line not found exactly once')
s = s.replace(old_scope, new_scope, 1)

old_db_before = "DB_BEFORE=$(sha256sum \"$RDB\"|awk '{print $1}')"
old_db_after = "DB_AFTER=$(sha256sum \"$RDB\"|awk '{print $1}')"
if s.count(old_db_before) != 1 or s.count(old_db_after) != 1:
    raise SystemExit('expected rollback DB fingerprint lines not found')
s = s.replace(old_db_before, "DB_BEFORE=$(sqlite3 \"$RDB\" '.dump' | sha256sum | awk '{print $1}')", 1)
s = s.replace(old_db_after, "DB_AFTER=$(sqlite3 \"$RDB\" '.dump' | sha256sum | awk '{print $1}')", 1)

old_wrong = '''setup_case wrong-source 18084
WR="$GATE_ROOT/wrong-source-runtime"; WC="$GATE_ROOT/wrong-source-cookie"; WB='http://127.0.0.1:18084'
sed -i "s/define('VFAB_VERSION', '1.35.2');/define('VFAB_VERSION', '1.35.1');/" "$WR/app/bootstrap.php"'''
new_wrong = '''echo 'NEGATIVE_WRONG_SOURCE_EXACT_V1351_BEGIN'
git worktree add --detach "$GATE_ROOT/wrong-source-worktree" "$WRONG_SOURCE_COMMIT" >/dev/null
python3 "$GATE_ROOT/wrong-source-worktree/scripts/build_runtime.py" "$GATE_ROOT/runtime-v1351" >/dev/null
grep -Fq "define('VFAB_VERSION', '1.35.1');" "$GATE_ROOT/runtime-v1351/app/bootstrap.php"
PROD_SAVE="$PROD"
PROD="$GATE_ROOT/runtime-v1351"
setup_case wrong-source 18084
PROD="$PROD_SAVE"
WR="$GATE_ROOT/wrong-source-runtime"; WC="$GATE_ROOT/wrong-source-cookie"; WB='http://127.0.0.1:18084'
grep -Fq "define('VFAB_VERSION', '1.35.1');" "$WR/app/bootstrap.php"
echo 'WRONG_SOURCE_FIXTURE_VERSION_1.35.1=PASS' '''
if s.count(old_wrong) != 1:
    raise SystemExit('expected wrong-source block not found exactly once')
s = s.replace(old_wrong, new_wrong, 1)

old_reject = "grep -q '版本不允许' \"$GATE_ROOT/wrong-source-result.html\""
if s.count(old_reject) != 1:
    raise SystemExit('wrong-source rejection assertion not found')
s = s.replace(old_reject, old_reject + "\necho 'WRONG_SOURCE_REJECTION_PAGE=PASS'", 1)

old_cleanup = 'docker rm -f p03-wrong-source >/dev/null'
if s.count(old_cleanup) != 1:
    raise SystemExit('wrong-source cleanup line not found')
s = s.replace(old_cleanup, old_cleanup + '\ngit worktree remove --force "$GATE_ROOT/wrong-source-worktree" >/dev/null', 1)

s = s.replace('setup_case rollback 18083', "echo 'NEGATIVE_ROLLBACK_SETUP_BEGIN'\nsetup_case rollback 18083", 1)
s = s.replace('test "$DB_BEFORE" = "$DB_AFTER"', 'echo "DB_LOGICAL_BEFORE=$DB_BEFORE DB_LOGICAL_AFTER=$DB_AFTER"\ntest "$DB_BEFORE" = "$DB_AFTER"', 1)
s = s.replace('test "$SRC_BEFORE" = "$SRC_AFTER"', 'echo "SOURCE_BEFORE=$SRC_BEFORE SOURCE_AFTER=$SRC_AFTER"\ntest "$SRC_BEFORE" = "$SRC_AFTER"', 1)

p.write_text(s, encoding='utf-8', newline='\n')
print('P03_FORMAL_HARNESS_PATCH=PASS')
