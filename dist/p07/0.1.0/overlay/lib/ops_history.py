#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, stat
from datetime import datetime, timezone
from pathlib import Path

DEFAULT = Path(os.environ.get("VFOPS_HISTORY_FILE", "/var/lib/vf-server-ops/history/events.jsonl"))

def clean(value: str, limit: int) -> str:
    return (value or "").replace("\n"," ").replace("\r"," ").strip()[:limit]

def append_event(path: Path, action: str, result: str, detail: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    payload={"ts":datetime.now(timezone.utc).isoformat(timespec="seconds"),"action":clean(action,80),"result":clean(result,24),"detail":clean(detail,160)}
    with path.open("a",encoding="utf-8") as fh:
        fh.write(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n")
    os.chmod(path,stat.S_IRUSR|stat.S_IWUSR)

def read_events(path: Path, limit: int) -> list[dict]:
    if not path.is_file():
        return []
    rows=[]
    for line in path.read_text(encoding="utf-8",errors="replace").splitlines():
        try:
            row=json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row,dict):
            rows.append(row)
    return rows[-limit:][::-1]

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--file",default=str(DEFAULT))
    sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("append"); a.add_argument("--action",required=True); a.add_argument("--result",required=True); a.add_argument("--detail",default="")
    l=sub.add_parser("list"); l.add_argument("--limit",type=int,default=20); l.add_argument("--json",action="store_true")
    args=p.parse_args(); path=Path(args.file)
    if args.cmd=="append":
        append_event(path,args.action,args.result,args.detail); return 0
    rows=read_events(path,max(1,min(args.limit,100)))
    if args.json: print(json.dumps(rows,ensure_ascii=False)); return 0
    for row in rows: print(f"{row.get('ts','')}\t{row.get('result','')}\t{row.get('action','')}\t{row.get('detail','')}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
