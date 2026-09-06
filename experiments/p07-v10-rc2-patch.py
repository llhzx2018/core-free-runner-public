from pathlib import Path

p=Path('experiments/p07-bench.sh')
s=p.read_text()

s=s.replace('VERSION="1.0.0-rc1"','VERSION="1.0.0-rc2"',1)

old='''  {"id":68,"name":"Singapore","server":"https://speedtest.dsgroupmedia.com","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":82,"name":"Tokyo, Japan","server":"https://librespeed.a573.net/","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"}
'''
new='''  {"id":68,"name":"Singapore","server":"https://speedtest.dsgroupmedia.com","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"},
  {"id":75,"name":"Bangalore, India","server":"https://in1.backend.librespeed.org/","dlURL":"garbage.php","ulURL":"empty.php","pingURL":"empty.php","getIpURL":"getIP.php"},
  {"id":82,"name":"Tokyo, Japan","server":"https://librespeed.a573.net/","dlURL":"backend/garbage.php","ulURL":"backend/empty.php","pingURL":"backend/empty.php","getIpURL":"backend/getIP.php"}
'''
if old not in s: raise SystemExit('server list marker not found')
s=s.replace(old,new,1)

old_cmd='''timeout 35s "$LIBRESPEED_BIN" --json --local-json "$LIBRESPEED_SERVER_JSON" --server "$id" --no-icmp --duration 1 --concurrent 1 --chunks 5 --upload-size 256 --timeout 10 --telemetry-level disabled'''
new_cmd='''timeout 45s "$LIBRESPEED_BIN" --json --local-json "$LIBRESPEED_SERVER_JSON" --server "$id" --no-icmp --duration 2 --concurrent 2 --chunks 12 --upload-size 512 --timeout 10 --telemetry-level disabled'''
if old_cmd not in s: raise SystemExit('LibreSpeed command marker not found')
s=s.replace(old_cmd,new_cmd,1)

s=s.replace("      'Singapore') up=460.7; down=590.2; lat=164.8 ;;","      'Asia South') up=460.7; down=590.2; lat=164.8 ;;",1)
old_pool="  librespeed_region_pool 'Singapore'  '68|Singapore' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true\n"
new_pool="  librespeed_region_pool 'Asia South' '68|Singapore' '75|Bangalore' && GLOBAL_FALLBACK_PASS=$((GLOBAL_FALLBACK_PASS+1)) || true\n"
if old_pool not in s: raise SystemExit('Singapore pool marker not found')
s=s.replace(old_pool,new_pool,1)

p.write_text(s)
