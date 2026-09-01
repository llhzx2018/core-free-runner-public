#!/usr/bin/env bash
set -Eeuo pipefail
: "${PORT:?}"
: "${ADMIN_PASS:?}"
: "${EVID:?}"
ROOT="$GITHUB_WORKSPACE/product/src"
rm -rf "$EVID" /tmp/p01-anon.cookies
mkdir -p "$EVID/screens"
php -S 127.0.0.1:$PORT -t "$ROOT" >"$EVID/server.log" 2>&1 &
echo $! >/tmp/p01-anonymous-grid.pid
for i in $(seq 1 60); do
  if curl -fsS -c /tmp/p01-anon.cookies -b /tmp/p01-anon.cookies "http://127.0.0.1:$PORT/setup.php" -o "$EVID/setup.html"; then break; fi
  sleep .25
done
CSRF=$(python3 - "$EVID/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)
curl -fsS -L -c /tmp/p01-anon.cookies -b /tmp/p01-anon.cookies -X POST "http://127.0.0.1:$PORT/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=P01 Anonymous Grid Gate' \
  --data-urlencode "admin_password=$ADMIN_PASS" \
  --data-urlencode "admin_password_confirm=$ADMIN_PASS" \
  -o "$EVID/setup-post.html"
P01_ROOT="$ROOT" php "$GITHUB_WORKSPACE/runner/scripts/p01_anonymous_grid_seed.php" | tee "$EVID/seed.txt"
grep -Fx P01_ANONYMOUS_GRID_SEED=PASS "$EVID/seed.txt"
