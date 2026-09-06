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
p.write_text(s.replace(old,new,1))
