#!/usr/bin/env bash
# Exact v015 issued and exact v016 final-source FULL, real isolated HTTPS Chromium.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$P08_V016_FINAL_HTTPS" == YES && "$(id -u)" != 0 ]] || exit 21
edition="$1"
[[ "$edition" == old || "$edition" == target ]] || exit 22
old=369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e
final=ed96b18627cd0a63b1da20a1fd8c9b6c1808f159
tmp="$RUNNER_TEMP/p08-v016-final-https-$edition"
site="$RUNNER_TEMP/p08-v016-final-browser-$edition"
[[ ! -e "$tmp" && ! -e "$site" ]] || exit 23
mkdir -m 700 "$tmp" "$site"
PHP_PID=''; NGINX_PID=''; stage=SOURCE
cleanup() {
  rc=$?
  trap - EXIT INT TERM
  [[ -z "$NGINX_PID" ]] || kill "$NGINX_PID" >/dev/null 2>&1 || true
  [[ -z "$PHP_PID" ]] || kill "$PHP_PID" >/dev/null 2>&1 || true
  rm -rf -- "$tmp" "$site" target/tests/e2e/p08_v016_final_owner_https.spec.ts
  if [[ "$rc" == 0 ]]; then
    echo "P08_V016_FINAL_HTTPS_PRIVATE_CLEANUP_$edition=PASS"
  else
    echo "P08_V016_FINAL_HTTPS_FAILURE_STAGE_$stage=YES" >&2
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM
test "$(git -C target rev-parse HEAD)" = "$final"
test "$(cat target/VERSION)" = 0.1.16
if [[ "$edition" == old ]]; then
  gh release download v0.1.15 -R llhzx2018/vf-adops \
    -p VF_AdOps_V0.1.15_FULL.zip -D "$tmp" >/dev/null
  archive="$tmp/VF_AdOps_V0.1.15_FULL.zip"
  printf '%s  %s\n' 538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73 "$archive" | sha256sum -c --status
  source="$old"; version=0.1.15
else
  source="$final"; version=0.1.16
  for run in first second; do
    python3 -B target/scripts/build_full.py --source "$GITHUB_WORKSPACE/target" \
      --output "$tmp/full-$run.zip" --version 0.1.16 \
      --source-sha "$final" --governance-root "$GITHUB_WORKSPACE/gov"
  done
  cmp "$tmp/full-first.zip" "$tmp/full-second.zip"
  archive="$tmp/full-first.zip"
fi
unzip -tqq "$archive"; unzip -q "$archive" -d "$site"
python3 - "$site/FULL_MANIFEST.json" "$source" "$version" <<'PY'
import json,sys
a=json.load(open(sys.argv[1]))
assert a['type']=='CLEAN_FULL_ONLY' and a['project_id']=='P08'
assert a['source_sha']==sys.argv[2] and a['target_version']==sys.argv[3]
PY
echo "P08_V016_FINAL_HTTPS_REAL_FULL_$edition=PASS"
stage=FIRST_INSTALL
mkdir -p "$site/tests/compatibility"
cp target/tests/test_install_sqlite_e2e.php "$site/tests/"
cp target/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
php "$site/tests/test_install_sqlite_e2e.php"
[[ "$(readlink "$site/current")" == "releases/$source" ]] || exit 24
grep -Fq 'APP_URL="https://adops.lanlihong.com"' "$site/.env"
sed -i 's#APP_URL="https://adops.lanlihong.com"#APP_URL="https://127.0.0.1:18495"#' "$site/.env"
stage=HTTPS
openssl req -x509 -nodes -days 1 -newkey rsa:2048 -keyout "$tmp/site.key" -out "$tmp/site.crt" \
  -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1' >/dev/null 2>&1
chmod 0600 "$tmp/site.key"
cat > "$tmp/prepend.php" <<'PHP'
<?php
$_SERVER['HTTPS']='on';
$_SERVER['SERVER_PORT']='443';
$_SERVER['HTTP_X_FORWARDED_PROTO']='https';
PHP
# PHP's -S router is invoked for every request; using Laravel index.php as
# router swallows /build/assets/*.js and *.css as HTML, preventing Inertia mount.
# Serve only recognized, existing static files via the built-in static handler.
cat > "$tmp/router.php" <<'PHP'
<?php
$root = realpath($_SERVER['DOCUMENT_ROOT']);
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$candidate = ($root !== false && is_string($path))
    ? realpath($root.'/'.ltrim(rawurldecode($path), '/')) : false;
$extension = $candidate ? strtolower(pathinfo($candidate, PATHINFO_EXTENSION)) : '';
if ($root !== false && $candidate !== false
    && str_starts_with($candidate, $root.DIRECTORY_SEPARATOR)
    && is_file($candidate)
    && in_array($extension, ['js','mjs','css','png','jpg','jpeg','webp','gif','svg','ico','woff','woff2','ttf','map'], true)) {
    return false;
}
require $root.'/index.php';
PHP
php -d "auto_prepend_file=$tmp/prepend.php" -S 127.0.0.1:19495 -t "$site/public" "$tmp/router.php" > "$tmp/php.log" 2>&1 &
PHP_PID="$!"
for n in $(seq 1 45); do
  (echo > /dev/tcp/127.0.0.1/19495) >/dev/null 2>&1 && break || sleep 0.2
done
kill -0 "$PHP_PID"
cat > "$tmp/nginx.conf" <<EOF
worker_processes 1;
pid $tmp/nginx.pid;
error_log $tmp/nginx-error.log warn;
events {worker_connections 512;}
http {
  include /etc/nginx/mime.types;
  access_log off;
  server {
    listen 127.0.0.1:18495 ssl;
    server_name 127.0.0.1;
    ssl_certificate $tmp/site.crt;
    ssl_certificate_key $tmp/site.key;
    location / {
      proxy_pass http://127.0.0.1:19495;
      proxy_set_header Host 127.0.0.1:18495;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header X-Forwarded-Host 127.0.0.1:18495;
      proxy_set_header X-Real-IP 127.0.0.1;
    }
  }
}
EOF
nginx -t -p "$tmp" -c "$tmp/nginx.conf" >/dev/null
nginx -p "$tmp" -c "$tmp/nginx.conf" -g 'daemon off;' > "$tmp/nginx.log" 2>&1 &
NGINX_PID="$!"
for n in $(seq 1 60); do
  code="$(curl -sk --max-time 2 -o /dev/null -w '%{http_code}' https://127.0.0.1:18495/up || true)"
  [[ "$code" != 200 ]] || break
  sleep 0.2
done
[[ "$code" == 200 ]] || exit 31
stage=CHROMIUM
test ! -e target/tests/e2e/p08_v016_final_owner_https.spec.ts
cp scripts/p08_v016_final_owner_https.spec.ts target/tests/e2e/p08_v016_final_owner_https.spec.ts
export P08_TEST_BASE_URL=https://127.0.0.1:18495
export P08_HTTPS_VERSION="$version"
(cd target && npx playwright test tests/e2e/p08_v016_final_owner_https.spec.ts --workers=1 --reporter=list)
echo "P08_V016_FINAL_HTTPS_AUTH_AND_SAFETY_$edition=PASS"
