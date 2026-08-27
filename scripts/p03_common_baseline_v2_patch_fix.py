#!/usr/bin/env python3
from pathlib import Path
import sys
source=Path(__file__).with_name('p03_common_baseline_v2_patch.py').read_text(encoding='utf-8')
replacements=[
    ("sub_once('src/app/Repository.php',r\"function vfab_job_stale_seconds", "sub_once('src/app/Foundation.php',r\"function vfab_job_stale_seconds"),
    ("sub_once('src/app/Repository.php',r\"public function start", "sub_once('src/app/Foundation.php',r\"public function start"),
    ("replace_once('src/app/Repository.php','public function acquire", "replace_once('src/app/Foundation.php','public function acquire"),
    ("replace_once('src/app/Repository.php','public function heartbeat(string", "replace_once('src/app/Foundation.php','public function heartbeat(string"),
    ("replace_once('src/app/Repository.php','public function heartbeatForJob", "replace_once('src/app/Foundation.php','public function heartbeatForJob"),
    ("replace_once('src/app/Repository.php',\"$nowTs=time();", "replace_once('src/app/Foundation.php',\"$nowTs=time();"),
    ("replace_once('src/app/Repository.php',\"$heartbeat=strtotime", "replace_once('src/app/Foundation.php',\"$heartbeat=strtotime"),
]
for old,new in replacements:
    if source.count(old)!=1: raise SystemExit(f'wrapper expected one match: {old}')
    source=source.replace(old,new,1)
sys.argv=[str(Path(__file__).with_name('p03_common_baseline_v2_patch.py'))]+sys.argv[1:]
exec(compile(source,'p03_common_baseline_v2_patch.py','exec'),{'__name__':'__main__','__file__':sys.argv[0]})
