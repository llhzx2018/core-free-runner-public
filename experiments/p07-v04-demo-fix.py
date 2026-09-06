from pathlib import Path
p=Path('experiments/p07-bench.sh')
s=p.read_text()
old="""      'Suzhou, CN'|'Ningbo, CN') state=FAIL; reason=TIMEOUT; up='-'; down='-'; lat='-' ;;
      'Speedtest.net') state=PASS; reason=NONE; up=1180.2; down=1260.4; lat=1.1 ;;
"""
new="""      'Suzhou, CN'|'Ningbo, CN') state=FAIL; reason=TIMEOUT; up='-'; down='-'; lat='-' ;;
      'China Unicom 5G') state=FAIL; reason=NODE_UNAVAILABLE; up='-'; down='-'; lat='-' ;;
      'BJ Unicom') state=PASS; reason=NONE; up=820.4; down=910.2; lat=188.1 ;;
      'China Telecom JiangSu 5G') state=FAIL; reason=NODE_UNAVAILABLE; up='-'; down='-'; lat='-' ;;
      'Zhejiang Telecom') state=PASS; reason=NONE; up=760.2; down=845.8; lat=202.4 ;;
      'JSQY'|'Duke Kunshan University') state=PASS; reason=NONE; up=700.1; down=780.5; lat=210.0 ;;
      'Speedtest.net') state=PASS; reason=NONE; up=1180.2; down=1260.4; lat=1.1 ;;
"""
if old not in s:
    raise SystemExit('demo case anchor missing')
s=s.replace(old,new,1)

old="""drain_tty_input(){
  [[ -r /dev/tty ]] || return 0
"""
new="""drain_tty_input(){
  [[ -t 0 || -t 1 ]] || return 0
  [[ -r /dev/tty ]] || return 0
"""
if old not in s:
    raise SystemExit('tty anchor missing')
s=s.replace(old,new,1)

old="""  if (( DEMO )); then
    [[ "$url" == *baidu* || "$url" == *qq.com* || "$url" == *taobao* || "$url" == *189.cn* || "$url" == *10010* || "$url" == *10086* ]] && return 1
    return 0
  fi
"""
new="""  if (( DEMO )); then
    return 0
  fi
"""
if old not in s:
    raise SystemExit('demo http anchor missing')
s=s.replace(old,new,1)

p.write_text(s)
