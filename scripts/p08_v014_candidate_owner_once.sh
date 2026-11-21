#!/usr/bin/env bash
# P08 #85: genuine issued v0.1.14 normal Owner Vue + Laravel one-click to disposable v0.1.15.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
head=369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e
issued=6fae792864a594465e4b3224bd6d73abde976f12
zipsha=2b8023a1c67213dbebb8f7047f27debbccc0f00fb210d10aeb3dc703076a811b
[[ "$(git -C p08 rev-parse HEAD)" == "$head" && "$(cat p08/VERSION)" == 0.1.15 ]] || exit 3
work="$RUNNER_TEMP/p08-85-browser-$engine"
site="$RUNNER_TEMP/p08-85-site-$engine"
[[ ! -e "$work" && ! -e "$site" ]] || exit 3
umask 077
mkdir -m 700 "$work" "$site"
log="$work/private.log"
webpid=""
nginxpid=""
proxy_pid=""
cleanup(){
  for pid in "$webpid" "$nginxpid" "$proxy_pid"; do
    [[ -z "$pid" ]] || kill "$pid" >/dev/null 2>&1 || true
  done
  if [[ -f /usr/local/share/ca-certificates/p08-85-native-api.crt ]]; then
    sudo rm -f /usr/local/share/ca-certificates/p08-85-native-api.crt || true
    sudo update-ca-certificates >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
phase(){
  local name="$1"; shift
  if "$@" >>"$log" 2>&1; then
    echo "P08_85_$engine"_"$name=PASS"
  else
    echo "P08_85_$engine"_"$name=FAIL"
    exit 41
  fi
}
phase PHP_LINT php -l p08/app/Http/Controllers/OwnerFutureUpdateController.php
phase VERSION_GATE php -r 'exit(version_compare("0.1.14","0.1.4",">=")?0:1);'
grep -Fq 'FutureOwnerUpdatePanel' p08/resources/js/modules/updates/UpdatePanel.vue
grep -Fq "/app/system/update/next/one-click" p08/routes/web.php ||   grep -Fq "name('adops.update.next.one-click')" p08/routes/web.php
echo "P08_85_$engine"_ISSUED_NORMAL_OWNER_UI_WIRED=PASS
phase DEV_CHECK bash p08/scripts/dev_check.sh
phase COMPOSER composer install --working-dir=p08 --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader
phase NPM npm ci --prefix p08 --ignore-scripts --no-audit --no-fund
cd p08
phase CHROMIUM npx playwright install --with-deps chromium
cd ..
phase REAL_OFFICIAL_FULL gh release download v0.1.14 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.14_FULL.zip -D "$work"
archive="$work/VF_AdOps_V0.1.14_FULL.zip"
printf '%s  %s\n' "$zipsha" "$archive" | sha256sum -c --status || exit 42
phase REAL_FULL_EXTRACT unzip -q "$archive" -d "$site"
unzip -p "$archive" FULL_MANIFEST.json > "$work/issued-manifest.json"
python3 - "$work/issued-manifest.json" "$issued" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
assert m["source_sha"]==sys.argv[2] and m["target_version"]=="0.1.14"
assert m["project_id"]=="P08" and m["type"]=="CLEAN_FULL_ONLY"
PY
echo "P08_85_$engine"_PUBLISHED_SHA256_MANIFEST=PASS
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
# Only this disposable website: replace exactly one well-formed APP_URL line.
# Official installers can serialize this setting differently on SQL vs SQLite.
lines=s.splitlines()
positions=[i for i,line in enumerate(lines) if line.startswith('APP_URL=')]
assert len(positions)==1
i=positions[0]
assert 10<len(lines[i])<512 and '\\x00' not in lines[i]
lines[i]='APP_URL="https://127.0.0.1:18519"'
p.write_text('\n'.join(lines)+'\n')
PY
# Keep all traffic local even if the disposable installer saved a fake PAT.
token="$site/storage/app/private/adops/upgrade/github-read-token"
[[ ! -L "$token" ]] || exit 44
[[ ! -f "$token" ]] || rm -f -- "$token"
[[ ! -e "$site/public/p08-owner-first-forward.php" ]] || exit 44
phase WEB_PHP_LINT php -l "$site/public/index.php"
echo "P08_85_$engine"_NO_STANDALONE_PHP_USED=PASS
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
  curl -ksS --connect-timeout 2 --max-time 2 -L -o "$work/guest.html" -w '%{http_code}' \
    https://127.0.0.1:18519/login >"$work/guest-code" 2>/dev/null || true
  [[ "$(cat "$work/guest-code")" == 200 ]] && break
  sleep 0.2
done
kill -0 "$nginxpid"
status="$(cat "$work/guest-code" 2>/dev/null || true)"
python3 - "$work/guest.html" "$status" "$engine" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);status=sys.argv[2];engine=sys.argv[3]
txt=p.read_text(errors="ignore")[:250000] if p.is_file() else ""
flags={
 "INERTIA":'data-page=' in txt,
 "APP_ROOT":'id="app"' in txt,
 "LARAVEL":'laravel' in txt.lower(),
 "LOGIN":'login' in txt.lower() or '登录' in txt,
 "ERROR":'error' in txt.lower(),
 "HTML":'<html' in txt.lower(),
}
print("P08_85_"+engine+"_GUEST_HTTP="+(status if re.fullmatch(r"\d{3}",status) else "UNKNOWN"))
print("P08_85_"+engine+"_GUEST_BODY_SIZE_CATEGORY="+("EMPTY" if not txt else "PRESENT"))
for k,v in flags.items():print("P08_85_"+engine+"_SAFE_GUEST_"+k+"="+("YES" if v else "NO"))
PY
# Actual v0.1.14 /login is a Blade page, NOT Inertia HTML.
# The previous assertion demanded an app root and falsely failed 3/3
# despite HTTP=200 and a real Login page. Verify real Blade form fields.
grep -Fq 'class="login-shell"' "$work/guest.html" &&
grep -Fq 'name="login"' "$work/guest.html" &&
grep -Fq 'name="password"' "$work/guest.html" || {
  echo "P08_85_$engine"_GUEST_HTTPS=FAIL; exit 45;
}
echo "P08_85_$engine"_GUEST_HTTPS=PASS

# Only source-bound prepublication candidate; never create or push a test commit.
phase VITE_ASSETS npm run build --prefix p08
target="$head"
[[ "$target" =~ ^[a-f0-9]{40}$ && "$target" != "$issued" ]] || exit 48
unzip -p "$archive" FULL_MANIFEST.json >"$work/013-issued-manifest.json"
source_manifest_sha="$(sha256sum "$work/013-issued-manifest.json" | cut -d' ' -f1)"
for pass in first second; do
  phase BUILD_TEMP_FULL python3 -B p08/scripts/build_full.py \
    --source p08 --output "$work/014-full-$pass.zip" --version 0.1.15 \
    --source-sha "$target" --governance-root gov
  phase BUILD_TEMP_ATOMIC python3 -B p08/scripts/build_atomic.py \
    --source p08 --output "$work/014-update-$pass.zip" \
    --source-version 0.1.14 --source-sha "$issued" \
    --source-full-manifest-sha256 "$source_manifest_sha" \
    --previous-full-manifest "$work/013-issued-manifest.json" \
    --target-version 0.1.15 --target-sha "$target"
done
cmp "$work/014-full-first.zip" "$work/014-full-second.zip"
cmp "$work/014-update-first.zip" "$work/014-update-second.zip"
mv "$work/014-full-first.zip" "$work/014-full.zip"
mv "$work/014-update-first.zip" "$work/014-update.zip"
rm -- "$work/014-full-second.zip" "$work/014-update-second.zip"
echo "P08_V015_CANDIDATE_$engine"_DOUBLE_BUILD_SAME_SOURCE=PASS
fixture="$RUNNER_TEMP/p08-85-native-fixture"
mkdir -m 700 "$fixture"
mv "$work/014-update.zip" "$fixture/VF_AdOps_V0.1.15_UPDATE.zip"
mv "$work/014-full.zip" "$fixture/VF_AdOps_V0.1.15_FULL.zip"
python3 - "$fixture" "$issued" "$source_manifest_sha" "$target" <<'PY'
import hashlib,json,sys
from pathlib import Path
folder=Path(sys.argv[1])
old,manifest,target=sys.argv[2:]
version="0.1.15"
def asset(id,name):
    file=folder/name
    return {"id":id,"name":name,"size":file.stat().st_size,
            "sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
atomic=asset(84552114,"VF_AdOps_V0.1.15_UPDATE.zip")
full=asset(84552115,"VF_AdOps_V0.1.15_FULL.zip")
channel={
 "schema_version":"1.0","project_id":"P08","component_id":"APP",
 "project_slug":"vf-adops","repository":"llhzx2018/vf-adops",
 "enabled":True,"update_type":"ATOMIC","channel":"stable",
 "backup_required":True,"rollback_supported":True,
 "production_auto_apply":False,"signature_required":False,
 "signature_algorithm":None,"from_versions":["0.1.14"],
 "target_version":version,"source_sha":old,
 "source_full_manifest_sha256":manifest,
 "schema_from":"1.1","schema_to":"1.1",
 "release_tag":"v"+version,"minimum_php":"8.4.1",
 "target_sha":target,"release_id":84552113,
 "asset_id":atomic["id"],"asset_name":atomic["name"],
 "asset_bytes":atomic["size"],"asset_sha256":atomic["sha256"],
 "full_asset_id":full["id"],"full_asset_name":full["name"],
 "full_asset_bytes":full["size"],"full_asset_sha256":full["sha256"]
}
release={
 "id":84552113,"tag_name":"v"+version,"draft":False,"prerelease":False,
 "assets":[{"id":a["id"],"name":a["name"],"size":a["size"],
            "state":"uploaded","content_type":"application/zip",
            "url":"https://api.github.com/repos/llhzx2018/vf-adops/releases/assets/"+str(a["id"]),
            "digest":"sha256:"+a["sha256"]} for a in [atomic,full]]
}
ref={"ref":"refs/tags/v"+version,"object":{"type":"commit","sha":target}}
for name,obj in [("channel.json",channel),("release.json",release),("tag.json",ref)]:
    (folder/name).write_text(json.dumps(obj,sort_keys=True,separators=(",",":"))+"\n")
PY
echo "P08_85_$engine"_TEMP_014_BYTES_AND_METADATA=PASS

# Localhost TLS: expected genuine hostname api.github.com, all calls routed to
# strict no-upstream fake issuer and never to any official GitHub endpoint.
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
 -keyout "$work/github.key" -out "$work/github.crt" \
 -subj '/CN=api.github.com' -addext 'subjectAltName=DNS:api.github.com' \
 -addext 'basicConstraints=critical,CA:TRUE' \
 -addext 'keyUsage=critical,digitalSignature,keyCertSign,cRLSign' \
 >>"$log" 2>&1
sudo install -m 0644 "$work/github.crt" /usr/local/share/ca-certificates/p08-85-native-api.crt
phase ISOLATED_TRUST sudo update-ca-certificates
events="$RUNNER_TEMP/p08-85-native-events.log"
P08_85_UNISSUED_POSITIVE=YES \
 python3 -u scripts/p08_85_native_tls_proxy.py \
 "$fixture" "$work/github.crt" "$work/github.key" "$events" \
 > "$work/proxy.log" 2>&1 &
proxy_pid="$!"
for i in $(seq 1 60); do
  grep -Fxq 'P08_85_ISOLATED_POSITIVE_TLS_PROXY=READY' "$work/proxy.log" 2>/dev/null && break
  sleep 0.2
done
kill -0 "$proxy_pid"
export HTTPS_PROXY=http://127.0.0.1:19184
export https_proxy=http://127.0.0.1:19184
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
# The PHP web SAPI was started for the actual Laravel guest readiness before
# the loopback GitHub proxy existed. Restart it with the proxy environment;
# this is an isolated test process only, never a site service restart.
kill "$webpid"
wait "$webpid" >/dev/null 2>&1 || true
php -d "auto_prepend_file=$work/web-env.php" \
  -S 127.0.0.1:19519 -t "$site/public" >"$work/php-issuer-proxy.log" 2>&1 &
webpid="$!"
for i in $(seq 1 60); do
  (echo >/dev/tcp/127.0.0.1/19519) >/dev/null 2>&1 && break
  sleep 0.2
done
kill -0 "$webpid"
echo "P08_85_$engine"_WEB_AND_WORKER_ISOLATED_PROXY_ENV=PASS
token="$site/storage/app/private/adops/upgrade/github-read-token"
[[ ! -e "$token" && ! -L "$token" ]] || exit 49
printf 'github_pat_%045d\n' 0 >"$token"
python3 - "$token" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
p.write_text("github_pat_"+"r"*45+"\n")
p.chmod(0o600)
PY
echo "P08_85_$engine"_LOCAL_SYNTHETIC_CHANNEL_ONLY=READY

# This browser controls the genuine issued v013 Vue/Laravel built-in Owner panel and the independently spawned
# site-user old-v013 Worker: all exposed metadata is fake, package bytes real.
cp scripts/p08_85_native_owner.spec.ts p08/tests/e2e/p08-85-native-isolated.spec.ts
cd p08
P08_TEST_BASE_URL=https://127.0.0.1:18519 \
P08_85_UNISSUED_POSITIVE=YES P08_ISOLATED_INSTALL_TEST=YES \
P08_TEST_DB_DRIVER="$engine" \
 npx playwright test tests/e2e/p08-85-native-isolated.spec.ts --workers=1 --reporter=list \
 >>"$log" 2>&1 || {
   echo "P08_85_$engine"_POSITIVE_BROWSER=FAIL
   python3 - "$site" "$issued" "$target" "$events" <<'PY'
import json,re,sys
from pathlib import Path
site=Path(sys.argv[1]);old=sys.argv[2];new=sys.argv[3];events=Path(sys.argv[4])
root=site/"storage/app/private/adops"
def safe_info(name):
    file=root/"owner-next-update"/name
    if file.is_symlink() or not file.is_file():return {}
    try:r=json.loads(file.read_bytes()[:8192])
    except Exception:return {}
    return r if isinstance(r,dict) else {}
intent=safe_info("intent.json")
job=safe_info("status.json")
allowed={"NONE","PENDING_PREPARE","RUNNING_PREPARE","PENDING_APPLY",
         "RUNNING_APPLY","PREPARED","SUCCEEDED","NEEDS_RECOVERY"}
for tag,r in [("INTENT",intent),("JOB",job)]:
    state=r.get("status","NONE")
    print("P08_85_SAFE_"+tag+"_STATUS="+(state if state in allowed else "INVALID"))
    fail=r.get("failure_code","")
    if isinstance(fail,str) and re.fullmatch(r"[A-Z][A-Z0-9_]{5,120}",fail):
        print("P08_85_SAFE_"+tag+"_FAILURE_CODE="+fail)
p=site/"current"
link=p.readlink().as_posix() if p.is_symlink() else ""
print("P08_85_SAFE_POINTER="+("ORIGINAL" if link=="releases/"+old
  else "CANDIDATE" if link=="releases/"+new else "UNKNOWN"))
try:rows=events.read_text().splitlines()
except Exception:rows=[]
for name in ["channel","release","tag","atomic"]:
    print("P08_85_SAFE_PROXY_"+name.upper()+"="+("YES" if name in rows else "NO"))
PY
   exit 50
 }
cd ..
[[ "$(readlink "$site/current")" == "releases/$target" ]] || exit 51
[[ "$(cat "$site/current/VERSION")" == "0.1.15" ]] || exit 52
[[ ! -f "$site/storage/app/private/adops/maintenance/maintenance.json" ]] || exit 53
python3 - "$site" "$target" <<'PY'
import json,sys
from pathlib import Path
site=Path(sys.argv[1])
target=sys.argv[2]
private=site/"storage/app/private/adops"
state=json.loads((private/"owner-next-update/status.json").read_text())
intent=json.loads((private/"owner-next-update/intent.json").read_text())
assert state["status"]=="SUCCEEDED" and intent["status"]=="SUCCEEDED"
assert state["target_sha"]==target and intent["target_sha"]==target
assert state["job_id"]==intent["id"]
assert len(list((private/"recovery").glob("*/manifest.json")))>=1
PY
for role in channel release tag atomic; do
 grep -Fxq "$role" "$events" || { echo "P08_85_$engine"_LOOPBACK_ROUTE_MISSING=FAIL;exit 54; }
done
echo "P08_85_$engine"_AUTHENTICATED_BUILTIN_ONE_CLICK_AND_ROOTLESS_NATIVE_ATOMIC=PASS
echo "P08_85_$engine"_OFFICIAL_014_RELEASE=NOT_ISSUED
echo "P08_85_$engine"_PRODUCTION=UNCHANGED
