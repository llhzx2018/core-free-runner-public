#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BACKUP_DIR=Path(os.environ.get("VFOPS_BACKUP_DIR","/var/backups/vf-server-ops"))

def run(cmd:list[str])->tuple[int,str]:
    try:
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=5,check=False)
        return p.returncode,(p.stdout or p.stderr).strip()
    except (OSError,subprocess.TimeoutExpired):
        return 127,""

def service_any(names:list[str])->tuple[str,str]:
    if not shutil.which("systemctl"):
        return "WARN","当前环境没有 systemctl"
    for name in names:
        rc,out=run(["systemctl","is-active",name])
        if rc==0 and out=="active":
            return "OK",f"{name} 正常"
    return "WARN","未检测到活动服务："+" / ".join(names)

def mem_info()->dict[str,int]:
    out={}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k,v=line.split(":",1); out[k]=int(v.strip().split()[0])*1024
    except Exception:
        pass
    return out

def latest_backup_age_hours()->float|None:
    newest=None
    if BACKUP_DIR.is_dir():
        for p in BACKUP_DIR.glob("*/verification.json"):
            try:
                if '"PASS"' not in p.read_text(encoding="utf-8",errors="ignore"): continue
                newest=max(newest or 0,p.stat().st_mtime)
            except OSError:
                continue
    if not newest: return None
    return max(0,(datetime.now(timezone.utc).timestamp()-newest)/3600)

def collect()->dict:
    rows=[]
    def add(key,label,status,detail): rows.append({"key":key,"label":label,"status":status,"detail":detail})
    required=[ROOT/"bin/vfops-user",ROOT/"bin/vfops",ROOT/"lib/terminal_ui.sh",ROOT/"VERSION",ROOT/"BUILD_ID"]
    missing=[str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    add("p07","P07 自身","ERROR" if missing else "OK","缺少："+ "、".join(missing) if missing else "运行文件完整")
    cp=Path("/home/clp").exists() or shutil.which("clpctl") is not None
    add("cloudpanel","CloudPanel","OK" if cp else "WARN","已检测" if cp else "未检测到 CloudPanel")
    for key,label,names in (("nginx","Nginx",["nginx"]),("mysql","MySQL",["mysql","mysqld","percona-server"])):
        st,detail=service_any(names); add(key,label,st,detail)
    php=Path("/run/php").is_dir() and bool(list(Path("/run/php").glob("php*-fpm.sock")))
    add("php","PHP-FPM","OK" if php else "WARN","发现活动 socket" if php else "未发现 PHP-FPM socket")
    usage=shutil.disk_usage("/"); pct=round(usage.used/usage.total*100) if usage.total else 0
    add("disk","磁盘","ERROR" if pct>=95 else "WARN" if pct>=85 else "OK",f"根分区已使用 {pct}%")
    mi=mem_info(); total=mi.get("MemTotal",0); avail=mi.get("MemAvailable",0); mpct=round((1-avail/total)*100) if total else 0
    add("memory","内存","WARN" if mpct>=90 else "OK",f"内存已使用约 {mpct}%")
    stotal=mi.get("SwapTotal",0); sfree=mi.get("SwapFree",0); spct=round((1-sfree/stotal)*100) if stotal else 0
    add("swap","Swap","WARN" if stotal and spct>=80 else "OK","未配置 Swap" if not stotal else f"Swap 已使用约 {spct}%")
    age=latest_backup_age_hours()
    if age is None: add("backup","最近备份","WARN","未发现已验证的 P07 本地备份")
    elif age>72: add("backup","最近备份","WARN",f"最近已验证备份约 {round(age)} 小时前")
    else: add("backup","最近备份","OK",f"最近已验证备份约 {round(age,1)} 小时前")
    verdict="ERROR" if any(x["status"]=="ERROR" for x in rows) else "WARN" if any(x["status"]=="WARN" for x in rows) else "OK"
    return {"schema":"p07.ops-diagnostics.v1","verdict":verdict,"checks":rows}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--json",action="store_true"); p.add_argument("--summary",action="store_true"); args=p.parse_args()
    data=collect()
    if args.json: print(json.dumps(data,ensure_ascii=False)); return 0
    if args.summary:
        print(f"{data['verdict']}\t{sum(1 for x in data['checks'] if x['status']!='OK')}"); return 0
    for x in data["checks"]: print(f"{x['status']}\t{x['label']}\t{x['detail']}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
