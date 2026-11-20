#!/usr/bin/env bash
# P08 PR84 isolated genuine issued FULL, three database HTTPS owner refusal.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
head=efa29c9f1095aa326adb244729c21bf3d10830e0
issued=8b385fecd132a02ac79f5b67e670783e98997c3e
zipsha=f8075f065d1413c984f80ef7531242cfc894bf272e90f6d89282074f6617c1ec
[[ "$(git -C p08 rev-parse HEAD)" == "$head" && "$(cat p08/VERSION)" == 0.1.13 ]] || exit 3
work="$RUNNER_TEMP/p08-84-browser-$engine"
site="$RUNNER_TEMP/p08-84-site-$engine"
[[ ! -e "$work" && ! -e "$site" ]] || exit 3
umask 077
mkdir -m 700 "$work" "$site"
log="$work/private.log"
webpid=""
nginxpid=""
cleanup(){ for pid in "$webpid" "$nginxpid"; do [[ -z "$pid" ]] || kill "$pid" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT
phase(){
  local name="$1"; shift
  if "$@" >>"$log" 2>&1; then
    echo "P08_PR84_$engine"_"$name=PASS"
  else
    echo "P08_PR84_$engine"_"$name=FAIL"
    exit 41
  fi
}
phase PHP_LINT php -l p08/scripts/p08_owner_first_forward_013.php
phase CONTRACT python3 -m unittest discover -s p08/tests -p test_p08_013_first_forward_contract.py -v
phase DEV_CHECK bash p08/scripts/dev_check.sh
phase COMPOSER composer install --working-dir=p08 --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader
phase NPM npm ci --prefix p08 --ignore-scripts --no-audit --no-fund
cd p08
phase CHROMIUM npx playwright install --with-deps chromium
cd ..
phase REAL_OFFICIAL_FULL gh release download v0.1.13 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.13_FULL.zip -D "$work"
archive="$work/VF_AdOps_V0.1.13_FULL.zip"
printf '%s  %s\n' "$zipsha" "$archive" | sha256sum -c --status || exit 42
phase REAL_FULL_EXTRACT unzip -q "$archive" -d "$site"
unzip -p "$archive" FULL_MANIFEST.json > "$work/issued-manifest.json"
python3 - "$work/issued-manifest.json" "$issued" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
assert m["source_sha"]==sys.argv[2] and m["target_version"]=="0.1.13"
assert m["project_id"]=="P08" and m["type"]=="CLEAN_FULL_ONLY"
PY
echo "P08_PR84_$engine"_PUBLISHED_SHA256_MANIFEST=PASS
mkdir -p "$site/tests/compatibility" "$site/tests/fixtures"
cp p08/tests/test_install_sqlite_e2e.php p08/tests/test_install_mysql_e2e.php "$site/tests/"
cp p08/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
cp p08/tests/fixtures/create_ci_databases.php "$site/tests/fixtures/"
if [[ "$engine" == sqlite ]]; then
  phase REAL_FIRST_INSTALL php "$site/tests/test_install_sqlite_e2e.php"
else
  phase NATIVE_DATABASE_CREATE php "$site/tests/fixtures/create_ci_databases.php"
  phase REAL_FIRST_INSTALL php "$site/tests/test_install_mysql_e2e.php"
fi
[[ "$(readlink "$site/current")" == "releases/$issued" ]] || exit 43
python3 - "$site/.env" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
assert 'APP_URL="https://adops.lanlihong.com"' in s
p.write_text(s.replace('APP_URL="https://adops.lanlihong.com"',
                       'APP_URL="https://127.0.0.1:18519"'))
PY
# Keep all traffic local even if the disposable installer saved a fake PAT.
token="$site/storage/app/private/adops/upgrade/github-read-token"
[[ ! -L "$token" ]] || exit 44
[[ ! -f "$token" ]] || rm -f -- "$token"
cp p08/scripts/p08_owner_first_forward_013.php "$site/public/p08-owner-first-forward.php"
chmod 0600 "$site/public/p08-owner-first-forward.php"
phase WEB_PHP_LINT php -l "$site/public/p08-owner-first-forward.php"
openssl req -x509 -nodes -days 1 -newkey rsa:2048 -keyout "$work/cert.key" -out "$work/cert.crt" \
  -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1' >>"$log" 2>&1
cat > "$work/web-env.php" <<'PHP'
<?php
$_SERVER['HTTPS']='on';
$_SERVER['SERVER_PORT']='443';
PHP
php -d "auto_prepend_file=$work/web-env.php" -S 127.0.0.1:19519 -t "$site/public" >"$work/php.log" 2>&1 &
webpid="$!"
for i in $(seq 1 70);do (echo >/dev/tcp/127.0.0.1/19519) >/dev/null 2>&1 && break;sleep 0.2;done
kill -0 "$webpid"
cat > "$work/nginx.conf" <<EOF
worker_processes 1;
pid $work/nginx.pid;
error_log $work/nginx.log warn;
events { worker_connections 256; }
http {
  include /etc/nginx/mime.types;
  access_log off;
  server {
    listen 127.0.0.1:18519 ssl;
    server_name 127.0.0.1;
    ssl_certificate $work/cert.crt;
    ssl_certificate_key $work/cert.key;
    location / {
      proxy_pass http://127.0.0.1:19519;
      proxy_set_header Host 127.0.0.1:18519;
      proxy_set_header X-Forwarded-Proto https;
    }
  }
}
EOF
nginx -c "$work/nginx.conf" -p "$work" -g 'daemon off;' >"$work/nginx-stdout.log" 2>&1 &
nginxpid="$!"
for i in $(seq 1 80);do
  curl -ksSf --connect-timeout 2 --max-time 2 https://127.0.0.1:18519/p08-owner-first-forward.php \
    >"$work/guest.html" 2>/dev/null && break
  sleep 0.2
done
kill -0 "$nginxpid"
grep -Fq '验证管理员身份' "$work/guest.html" || { echo "P08_PR84_$engine"_GUEST_HTTPS=FAIL;exit 45; }
echo "P08_PR84_$engine"_GUEST_HTTPS=PASS
cd p08
P08_TEST_BASE_URL=https://127.0.0.1:18519 \
P08_013_FIRST_FORWARD_BROWSER=YES P08_ISOLATED_INSTALL_TEST=YES \
P08_TEST_DB_DRIVER="$engine" \
  npx playwright test tests/e2e/owner-v013-first-forward.spec.ts --workers=1 --reporter=list \
  >>"$log" 2>&1 || { echo "P08_PR84_$engine"_OWNER_HTTPS_BROWSER=FAIL;exit 46; }
cd ..
echo "P08_PR84_$engine"_REAL_CHROMIUM_OWNER_CSRF_PASSWORD_NO_RELEASE=PASS
[[ ! -f "$site/storage/app/private/adops/owner-next-update/intent.json" ]] || exit 47
[[ "$(readlink "$site/current")" == "releases/$issued" ]] || exit 48
echo "P08_PR84_$engine"_NO_NEW_INTENT_NO_POINTER_CHANGE=PASS
echo "P08_PR84_$engine"_ISSUED_014_REAL_CLICK=NOT_RUN
echo "P08_PR84_$engine"_FORMAL_RELEASE=NOT_AUTHORIZED
