#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

p=Path(sys.argv[1] if len(sys.argv)>1 else 'scripts/p03_v1354_formal_builder.py')
s=p.read_text(encoding='utf-8')
old_py="MANAGED_ROOT_FILES={'api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','robots.txt','setup.php','share.php'}"
new_py="MANAGED_ROOT_FILES={'api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','memory-api.php','robots.txt','setup.php','share.php'}"
old_php="$roots=['api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','robots.txt','setup.php','share.php'];"
new_php="$roots=['api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','memory-api.php','robots.txt','setup.php','share.php'];"

if new_py not in s:
    if s.count(old_py)!=1: raise SystemExit('BUILDER_NORMALIZE_PY_ROOT_ANCHOR_MISMATCH')
    s=s.replace(old_py,new_py,1)
if new_php not in s:
    if s.count(old_php)!=1: raise SystemExit('BUILDER_NORMALIZE_PHP_ROOT_ANCHOR_MISMATCH')
    s=s.replace(old_php,new_php,1)

if old_py in s or old_php in s: raise SystemExit('BUILDER_NORMALIZE_PARTIAL_STATE')
if s.count("memory-api.php")<2: raise SystemExit('BUILDER_NORMALIZE_MEMORY_API_INCOMPLETE')
p.write_text(s,encoding='utf-8',newline='\n')
print('FORMAL_BUILDER_MANAGED_ROOT_NORMALIZATION=PASS memory-api.php python=PASS atomic_php=PASS')
