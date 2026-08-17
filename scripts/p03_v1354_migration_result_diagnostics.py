#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

p=Path(sys.argv[1] if len(sys.argv)>1 else 'scripts/p03_v1354_formal_builder.py')
s=p.read_text(encoding='utf-8')
old="if((int)($mr['before_schema']??-1)!==VFF_SOURCE_SCHEMA||(int)($mr['after_schema']??-1)!==VFF_ATOMIC_SCHEMA||($mr['migration_id']??'')!==VFF_MIGRATION_ID||empty($mr['verified']))throw new RuntimeException('Migration 030 result mismatch.');"
new="if((int)($mr['before_schema']??-1)!==VFF_SOURCE_SCHEMA||(int)($mr['after_schema']??-1)!==VFF_ATOMIC_SCHEMA||($mr['migration_id']??'')!==VFF_MIGRATION_ID||empty($mr['verified'])){$safe=['before_schema'=>$mr['before_schema']??null,'after_schema'=>$mr['after_schema']??null,'migration_id'=>$mr['migration_id']??null,'applied'=>$mr['applied']??null,'verified'=>$mr['verified']??null,'checksum'=>$mr['checksum']??null,'pre_backup_status'=>is_array($mr['pre_migration_backup']??null)?($mr['pre_migration_backup']['status']??null):null,'pre_backup_schema'=>is_array($mr['pre_migration_backup']??null)?($mr['pre_migration_backup']['schema']??null):null];throw new RuntimeException('Migration 030 result mismatch '.json_encode($safe,JSON_UNESCAPED_SLASHES));}"
if new in s:
    print('M030_RESULT_DIAGNOSTICS=ALREADY_APPLIED');raise SystemExit(0)
if s.count(old)!=1: raise SystemExit('M030_RESULT_DIAGNOSTIC_ANCHOR_MISMATCH')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')
print('M030_RESULT_DIAGNOSTICS=PASS private_backup_path=REDACTED')
