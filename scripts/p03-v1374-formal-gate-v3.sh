#!/usr/bin/env bash
set -Eeuo pipefail
TMP="$RUNNER_TEMP/p03-v1374-formal-gate-v3.sh"
cp scripts/p03-v1374-formal-gate.sh "$TMP"
python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
start=s.index("log 'Common Product Baseline V2 current runtime'")
end_marker="echo P03_V1374_COMMON_BASELINE_V2=PASS"
end=s.index(end_marker,start)+len(end_marker)
installed=r'''log 'Common Product Baseline V2 installed fresh runtime'
BASELINE_DATA="$RUNNER_TEMP/p03-v1374-baseline-private"
BASELINE_SESS="$RUNNER_TEMP/p03-v1374-baseline-sessions"
BASELINE_COOKIE="$RUNNER_TEMP/p03-v1374-baseline-cookie"
BASELINE_URL='http://127.0.0.1:18173'
BASELINE_CONTAINER='vf-forge-v1374-baseline-http'
rm -rf "$BASELINE_DATA" "$BASELINE_SESS" "$BASELINE_COOKIE"; mkdir -p "$BASELINE_DATA" "$BASELINE_SESS"
docker rm -f "$BASELINE_CONTAINER" >/dev/null 2>&1 || true
docker run -d --rm --name "$BASELINE_CONTAINER" -p 18173:18173 \
  -v "$TARGET_RUNTIME:/app" -v "$BASELINE_DATA:$BASELINE_DATA" -v "$BASELINE_SESS:$BASELINE_SESS" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$BASELINE_SESS" -S 0.0.0.0:18173 -t /app >/dev/null
ready=0
for i in $(seq 1 80); do if curl -fsS "$BASELINE_URL/setup.php" >/dev/null 2>&1; then ready=1; break; fi; sleep .25; done
test "$ready" = 1
curl -fsS -c "$BASELINE_COOKIE" "$BASELINE_URL/setup.php" -o "$RUNNER_TEMP/p03-v1374-baseline-setup.html"
BASELINE_CSRF=$(python3 - "$RUNNER_TEMP/p03-v1374-baseline-setup.html" <<'PY2'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY2
)
STATUS=$(curl -sS -o "$RUNNER_TEMP/p03-v1374-baseline-setup-post.html" -w '%{http_code}' -b "$BASELINE_COOKIE" -c "$BASELINE_COOKIE" \
  -H "Origin: $BASELINE_URL" --data-urlencode "setup_csrf=$BASELINE_CSRF" \
  --data-urlencode 'site_title=VF Forge V1.37.4 Baseline Fixture' --data-urlencode "data_root=$BASELINE_DATA" \
  --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$BASELINE_URL/setup.php")
test "$STATUS" = 302 -o "$STATUS" = 303
BASELINE_OUT="$RUNNER_TEMP/p03-v1374-baseline.txt"
docker run --rm -v "$TARGET_RUNTIME:/app" -v "$BASELINE_DATA:$BASELINE_DATA" -v "$BASELINE_SESS:$BASELINE_SESS" -w /app "$PHP_TEST_IMAGE" \
  php -d "session.save_path=$BASELINE_SESS" cli/baseline-verify.php | tee "$BASELINE_OUT"
grep -Fx 'DRIFT_COUNT=0' "$BASELINE_OUT"
grep -Fx 'UNKNOWN_COUNT=0' "$BASELINE_OUT"
grep -Fx 'BASELINE_FULL_PASS=YES' "$BASELINE_OUT"
grep -Fq 'BASELINE=VF-COMMON-PRODUCT-BASELINE@2.0' "$BASELINE_OUT"
grep -Fq 'PROFILE=PERSONAL_SINGLE_ADMIN' "$BASELINE_OUT"
docker rm -f "$BASELINE_CONTAINER" >/dev/null
echo P03_V1374_COMMON_BASELINE_V2=PASS'''
s=s[:start]+installed+s[end:]
marker="log 'Browser E2E responsive regression'"
insert="""log 'Install Browser E2E dependency after source/privacy gates'\nnpm init -y >/dev/null 2>&1\nnpm install --no-save playwright@1.55.0 >/dev/null\nnpx playwright install --with-deps chromium >/dev/null\n\nlog 'Browser E2E responsive regression'"""
assert s.count(marker)==1
s=s.replace(marker,insert,1)
p.write_text(s,encoding='utf-8')
PY
exec bash "$TMP"
