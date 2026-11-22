#!/usr/bin/env bash
# P08 S1 exact source disposable localhost HTTPS Chromium, never Owner Production.
set -Eeuo pipefail
set +x
umask 077
[[ "$GITHUB_ACTIONS" == true && "$CI" == true && "$P08_ISOLATED_INSTALL_TEST" == YES ]] || exit 2
[[ "$(id -u)" != 0 && "$RUNNER_TEMP" == /home/runner/work/_temp ]] || exit 2
source_dir="$GITHUB_WORKSPACE/source"
site="$RUNNER_TEMP/p08-s1-verified-full-sqlite"
[[ "$(git -C "$source_dir" rev-parse HEAD)" == dcdf58c4814b7e930b5d53365bd44aa3bfc5cd08 ]] || exit 2
[[ -f "$site/FULL_MANIFEST.json" && -f "$site/storage/app/private/adops/installation/installed.json" ]] || exit 2
work="$RUNNER_TEMP/p08-s1-https"
[[ ! -e "$work" ]] || exit 3
mkdir -m 0700 "$work"
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout "$work/site.key" -out "$work/site.crt" \
  -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1' \
  >/dev/null 2>&1
chmod 0600 "$work/site.key"
cat >"$work/prepend.php" <<'PHP'
<?php
$_SERVER['HTTPS']='on';
$_SERVER['SERVER_PORT']='443';
PHP
cat >"$work/nginx.conf" <<'NGINX'
worker_processes 1;
pid __WORK__/nginx.pid;
error_log __WORK__/nginx.log warn;
events {worker_connections 512;}
http {
  access_log off;
  include /etc/nginx/mime.types;
  server {
    listen 127.0.0.1:18488 ssl;
    server_name _;
    ssl_certificate __WORK__/site.crt;
    ssl_certificate_key __WORK__/site.key;
    root __SITE__/public;
    index index.php;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    location ~ \.php$ {return 404;}
    location / {try_files $uri @laravel;}
    location @laravel {
       proxy_pass http://127.0.0.1:19488;
       proxy_set_header Host 127.0.0.1:18488;
       proxy_set_header X-Forwarded-Proto https;
       proxy_set_header X-Forwarded-Host 127.0.0.1:18488;
       proxy_read_timeout 60s;
    }
  }
}
NGINX
sed -i "s@__WORK__@$work@g;s@__SITE__@$site@g" "$work/nginx.conf"
php -d "auto_prepend_file=$work/prepend.php" -S 127.0.0.1:19488 \
 -t "$site/public" "$site/public/index.php" >"$work/php.log" 2>&1 &
php_pid=$!
nginx_pid=""
cleanup() {
  status=$?
  if [[ -n "$nginx_pid" ]]; then kill "$nginx_pid" 2>/dev/null || true; fi
  kill "$php_pid" 2>/dev/null || true
  wait "$php_pid" 2>/dev/null || true
  rm -rf -- "$work"
  if [[ "$status" -ne 0 ]]; then echo P08_S1_REAL_HTTPS_BROWSER=BLOCKED >&2; fi
}
trap cleanup EXIT
for i in $(seq 1 40); do
  (echo >/dev/tcp/127.0.0.1/19488) >/dev/null 2>&1 && break
  sleep 0.25
done
kill -0 "$php_pid"
nginx -t -c "$work/nginx.conf" >/dev/null
nginx -c "$work/nginx.conf" -g 'daemon off;' >"$work/nginx-out.log" 2>&1 &
nginx_pid=$!
for i in $(seq 1 40); do
  if curl -ksS --connect-timeout 1 -o "$work/login.html" https://127.0.0.1:18488/login; then break; fi
  sleep 0.25
done
[[ -s "$work/login.html" ]] || exit 5
grep -Fq 'name="_token"' "$work/login.html" || exit 5
status=$(curl -k -sS -o /dev/null -w '%{http_code}' https://127.0.0.1:18488/app)
[[ "$status" == 302 ]] || exit 5
cd "$source_dir"
export P08_TEST_INSTALLED_SITE="$site"
export P08_TEST_BASE_URL=https://127.0.0.1:18488
npx playwright test tests/e2e/owner-workspace.spec.ts --workers=1 --reporter=list
echo P08_S1_R04_LOCAL_REAL_HTTPS_CHROMIUM_WORKSPACE=PASS
