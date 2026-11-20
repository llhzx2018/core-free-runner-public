#!/usr/bin/env bash
# One-off authorized isolated machine gate. No Owner VPS, secrets or GH writes.
set -Eeuo pipefail
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$#" == 2 ]] || exit 22
tmp="$1"; web="$2"
[[ "$tmp" == "$RUNNER_TEMP/p08-v013-official-chain-sqlite" &&
   "$web" == "$RUNNER_TEMP/p08-r129-real-issued-r131-r155-sqlite-chain" &&
   ! -L "$web" && ! -L "$tmp" && -f "$web/.env" &&
   "$(readlink "$web/current")" == releases/dac7bc1d5410c077f32e522eb5740537f618ef9d ]] || exit 23
test "$(sha256sum "$web/current/FULL_MANIFEST.json" | cut -d' ' -f1)" = \
  607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9
# This site has NEVER moved: previous native backup paths still belong to it.
# Change only isolated mutable APP_URL, never signed app code or release index.
grep -Fq 'adops.lanlihong.com' "$web/.env"
sed -i 's#adops.lanlihong.com#127.0.0.1:18497#g' "$web/.env"
grep -Fq '127.0.0.1:18497' "$web/.env"
test "$(readlink "$web/current")" = releases/dac7bc1d5410c077f32e522eb5740537f618ef9d
cmp "$tmp/v013-update.zip" "$tmp/v013-update-second.zip"
          unzip -tqq "$tmp/v013-update.zip"
python3 "$GITHUB_WORKSPACE/tests/p08-v013-607b-old-client-synthetic-api.py" prepare "$tmp"
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout "$tmp/api.key" -out "$tmp/api.crt" -subj '/CN=api.github.com' \
  -addext 'subjectAltName=DNS:api.github.com' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,digitalSignature,keyCertSign,cRLSign' >/dev/null 2>&1
sudo install -m 0644 "$tmp/api.crt" /usr/local/share/ca-certificates/p08-v013-607b-local.crt
sudo update-ca-certificates >/dev/null 2>&1
api_pid=""; php_pid=""; tls_pid=""
cleanup(){
  code="$?"
  trap - EXIT INT TERM
  for pid in "$php_pid" "$tls_pid" "$api_pid"; do
    [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
  done
  sudo rm -f /usr/local/share/ca-certificates/p08-v013-607b-local.crt || true
  sudo update-ca-certificates >/dev/null 2>&1 || true
  if [[ "$code" -ne 0 ]]; then
    # The original PHP persists this stable SAFE code on its private intent;
    # NEVER echo the private JSON, paths, tokens, DB records or worker logs.
    php -r '
    $p=$argv[1]."/storage/app/private/adops/owner-next-update/intent.json";
    if (!is_link($p) && is_file($p) && filesize($p)<=8192) {
      $j=json_decode((string)file_get_contents($p),true);
      if(is_array($j)){
        foreach(["failure_phase","failure_code","status"] as $k){
          $v=$j[$k]??"NOT_RECORDED";
          if(is_string($v)&&preg_match("/^[A-Z][A-Z0-9_]{2,120}$/D",$v))
            echo "P08_607B_SAFE_".$k."=".$v."\n";
        }
      }
    }' "$web" || true
    echo P08_607B_HTTPS_OLD_CLIENT_MACHINE_GATE=FAIL >&2
  fi
  exit "$code"
}
trap cleanup EXIT INT TERM
python3 -u "$GITHUB_WORKSPACE/tests/p08-v013-607b-old-client-synthetic-api.py" serve "$tmp" \
  > "$tmp/local-api.log" 2>&1 &
api_pid="$!"
for i in $(seq 1 50); do
  grep -Fq 'P08_607B_NO_UPSTREAM_API_READY=PASS' "$tmp/local-api.log" && break
  sleep 0.2
done
kill -0 "$api_pid"
cat > "$tmp/browser-router.php" <<'PHP'
<?php
$_SERVER['HTTPS']='on';
$_SERVER['SERVER_PORT']=443;
$_SERVER['HTTP_HOST']='127.0.0.1:18497';
$_SERVER['SERVER_NAME']='127.0.0.1';
$root=getenv('P08_V013_OLD_SITE');
$path=parse_url((string)($_SERVER['REQUEST_URI']??'/'),PHP_URL_PATH);
$static=is_string($path)?realpath($root.'/public'.$path):false;
if($static!==false && is_string($static) && $path!=='/'
    && str_starts_with($static,$root.'/public/')
    && is_file($static) && !str_ends_with($static,'.php')) return false;
$_SERVER['SCRIPT_NAME']='/index.php';
$_SERVER['PHP_SELF']='/index.php';
require $root.'/public/index.php';
PHP
cat > "$tmp/browser-tls.py" <<'PY'
import http.client
import http.server
import ssl
import sys
cert,key=sys.argv[1:3]
class H(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*a):pass
    def relay(self):
        n=int(self.headers.get('Content-Length','0'))
        body=self.rfile.read(n) if n else None
        upstream=http.client.HTTPConnection('127.0.0.1',18079,timeout=120)
        hdr={k:v for k,v in self.headers.items() if k.lower() not in
             ('connection','transfer-encoding','proxy-connection')}
        upstream.request(self.command,self.path,body=body,headers=hdr)
        r=upstream.getresponse();data=r.read()
        self.send_response(r.status)
        for k,v in r.getheaders():
            if k.lower() not in ('connection','content-length','transfer-encoding','date','server'):
                self.send_header(k,v)
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        upstream.close()
    do_GET=do_POST=do_PUT=do_DELETE=relay
s=http.server.ThreadingHTTPServer(('127.0.0.1',18497),H)
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(cert,key)
s.socket=ctx.wrap_socket(s.socket,server_side=True)
s.serve_forever()
PY
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout "$tmp/browser.key" -out "$tmp/browser.crt" \
  -subj '/CN=127.0.0.1' >/dev/null 2>&1
export HTTPS_PROXY=http://127.0.0.1:19097
export https_proxy=http://127.0.0.1:19097
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
P08_V013_OLD_SITE="$web" php -S 127.0.0.1:18079 -t "$web/public" "$tmp/browser-router.php" \
  > "$tmp/browser-php.log" 2>&1 &
php_pid="$!"
python3 "$tmp/browser-tls.py" "$tmp/browser.crt" "$tmp/browser.key" \
  > "$tmp/browser-edge.log" 2>&1 &
tls_pid="$!"
code=000
for i in $(seq 1 60); do
  code="$(curl -ksS --connect-timeout 2 --max-time 3 -o /dev/null -w '%{http_code}' \
    https://127.0.0.1:18497/login 2>/dev/null || true)"
  [[ "$code" == 200 ]] && break
  sleep 0.2
done
[[ "$code" == 200 ]] || exit 25
test "$(readlink "$web/current")" = releases/dac7bc1d5410c077f32e522eb5740537f618ef9d
echo P08_607B_OLD_PHP_LOCALHOST_HTTPS_LOGIN=PASS
cp "$GITHUB_WORKSPACE/tests/p08-v013-607b-old-owner-click.spec.ts" \
  "$GITHUB_WORKSPACE/target/tests/e2e/v013-607b-old-owner-click.spec.ts"
(
  cd "$GITHUB_WORKSPACE/target"
  # Browser binaries are downloaded from the public Playwright CDN, not
  # from the strictly isolated api.github.com fixture proxy.
  env -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy -u ALL_PROXY -u all_proxy \
    npx playwright install chromium >/dev/null
  P08_TEST_BASE_URL=https://127.0.0.1:18497 \
    npx playwright test tests/e2e/v013-607b-old-owner-click.spec.ts \
      --config playwright.config.ts --workers=1 --reporter=line
)
test "$(readlink "$web/current")" = releases/8b385fecd132a02ac79f5b67e670783e98997c3e
test "$(cat "$web/current/VERSION")" = 0.1.13
test "$(sha256sum "$web/current/FULL_MANIFEST.json" | cut -d' ' -f1)" = \
  "$(unzip -p "$tmp/v013-full.zip" FULL_MANIFEST.json | sha256sum | cut -d' ' -f1)"
test ! -e "$web/storage/app/private/adops/maintenance/maintenance.json"
for item in channel release tag atomic; do
  grep -Fxq "$item" "$tmp/local-api-events.txt"
done
test "$(grep -Fxc atomic "$tmp/local-api-events.txt")" -eq 1
echo P08_607B_AUTHENTIC_V012_HTTPS_ONE_CLICK_NATIVE_APPLY=PASS
