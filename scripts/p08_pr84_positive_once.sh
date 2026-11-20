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
proxy_pid=""
cleanup(){
  for pid in "$webpid" "$nginxpid" "$proxy_pid"; do
    [[ -z "$pid" ]] || kill "$pid" >/dev/null 2>&1 || true
  done
  if [[ -f /usr/local/share/ca-certificates/p08-pr84-positive-api.crt ]]; then
    sudo rm -f /usr/local/share/ca-certificates/p08-pr84-positive-api.crt || true
    sudo update-ca-certificates >/dev/null 2>&1 || true
  fi
}
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

# Build a real executable native Atomic ZIP, but only with an EPHEMERAL commit.
# This is NOT a future official GitHub tag/Release/channel.
phase VITE_ASSETS npm run build --prefix p08
python3 - <<'PY'
from pathlib import Path
v=Path("p08/VERSION")
assert v.read_text().strip()=="0.1.13"
v.write_text("0.1.14\n")
n=Path("p08/public/p08-install-build.txt")
s=n.read_text()
assert "0.1.13" in s
n.write_text(s.replace("0.1.13","0.1.14").replace("DEVELOPMENT_CANDIDATE_NOT_ISSUED","ISOLATED_ONLY_NOT_PUBLISHED"))
PY
git -C p08 config user.name "P08 Ephemeral Test"
git -C p08 config user.email "p08-ephemeral@invalid.example"
phase TEST_ONLY_GIT_ADD git -C p08 add VERSION public/p08-install-build.txt
phase TEST_ONLY_GIT_COMMIT git -C p08 commit -m "isolated v014 candidate; never pushed"
target="$(git -C p08 rev-parse HEAD)"
[[ "$target" =~ ^[a-f0-9]{40}$ && "$target" != "$issued" ]] || exit 48
unzip -p "$archive" FULL_MANIFEST.json >"$work/013-issued-manifest.json"
source_manifest_sha="$(sha256sum "$work/013-issued-manifest.json" | cut -d' ' -f1)"
phase BUILD_TEMP_FULL python3 -B p08/scripts/build_full.py \
  --source p08 --output "$work/014-full.zip" --version 0.1.14 \
  --source-sha "$target" --governance-root gov
phase BUILD_TEMP_ATOMIC python3 -B p08/scripts/build_atomic.py \
  --source p08 --output "$work/014-update.zip" \
  --source-version 0.1.13 --source-sha "$issued" \
  --source-full-manifest-sha256 "$source_manifest_sha" \
  --previous-full-manifest "$work/013-issued-manifest.json" \
  --target-version 0.1.14 --target-sha "$target"
fixture="$RUNNER_TEMP/p08-pr84-positive-fixture"
mkdir -m 700 "$fixture"
mv "$work/014-update.zip" "$fixture/VF_AdOps_V0.1.14_UPDATE.zip"
mv "$work/014-full.zip" "$fixture/VF_AdOps_V0.1.14_FULL.zip"
python3 - "$fixture" "$issued" "$source_manifest_sha" "$target" <<'PY'
import hashlib,json,sys
from pathlib import Path
folder=Path(sys.argv[1])
old,manifest,target=sys.argv[2:]
version="0.1.14"
def asset(id,name):
    file=folder/name
    return {"id":id,"name":name,"size":file.stat().st_size,
            "sha256":hashlib.sha256(file.read_bytes()).hexdigest()}
atomic=asset(84552114,"VF_AdOps_V0.1.14_UPDATE.zip")
full=asset(84552115,"VF_AdOps_V0.1.14_FULL.zip")
channel={
 "schema_version":"1.0","project_id":"P08","component_id":"APP",
 "project_slug":"vf-adops","repository":"llhzx2018/vf-adops",
 "enabled":True,"update_type":"ATOMIC","channel":"stable",
 "backup_required":True,"rollback_supported":True,
 "production_auto_apply":False,"signature_required":False,
 "signature_algorithm":None,"from_versions":["0.1.13"],
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
echo "P08_PR84_$engine"_TEMP_014_BYTES_AND_METADATA=PASS

# Localhost TLS: expected genuine hostname api.github.com, all calls routed to
# strict no-upstream fake issuer and never to any official GitHub endpoint.
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
 -keyout "$work/github.key" -out "$work/github.crt" \
 -subj '/CN=api.github.com' -addext 'subjectAltName=DNS:api.github.com' \
 -addext 'basicConstraints=critical,CA:TRUE' \
 -addext 'keyUsage=critical,digitalSignature,keyCertSign,cRLSign' \
 >>"$log" 2>&1
sudo install -m 0644 "$work/github.crt" /usr/local/share/ca-certificates/p08-pr84-positive-api.crt
phase ISOLATED_TRUST sudo update-ca-certificates
events="$RUNNER_TEMP/p08-pr84-positive-events.log"
P08_PR84_UNISSUED_POSITIVE=YES \
 python3 -u scripts/p08_pr84_positive_tls_proxy.py \
 "$fixture" "$work/github.crt" "$work/github.key" "$events" \
 > "$work/proxy.log" 2>&1 &
proxy_pid="$!"
for i in $(seq 1 60); do
  grep -Fxq 'P08_PR84_ISOLATED_POSITIVE_TLS_PROXY=READY' "$work/proxy.log" 2>/dev/null && break
  sleep 0.2
done
kill -0 "$proxy_pid"
export HTTPS_PROXY=http://127.0.0.1:19184
export https_proxy=http://127.0.0.1:19184
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
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
echo "P08_PR84_$engine"_LOCAL_SYNTHETIC_CHANNEL_ONLY=READY

# This browser controls genuine issued v013 PHP and the independently spawned
# site-user old-v013 worker: all exposed metadata is fake, package bytes real.
cp scripts/p08_pr84_positive_owner.spec.ts p08/tests/e2e/pr84-positive-isolated.spec.ts
cd p08
P08_TEST_BASE_URL=https://127.0.0.1:18519 \
P08_PR84_UNISSUED_POSITIVE=YES P08_ISOLATED_INSTALL_TEST=YES \
P08_TEST_DB_DRIVER="$engine" \
 npx playwright test tests/e2e/pr84-positive-isolated.spec.ts --workers=1 --reporter=list \
 >>"$log" 2>&1 || { echo "P08_PR84_$engine"_POSITIVE_BROWSER=FAIL; exit 50; }
cd ..
[[ "$(readlink "$site/current")" == "releases/$target" ]] || exit 51
[[ "$(cat "$site/current/VERSION")" == "0.1.14" ]] || exit 52
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
 grep -Fxq "$role" "$events" || { echo "P08_PR84_$engine"_LOOPBACK_ROUTE_MISSING=FAIL;exit 54; }
done
echo "P08_PR84_$engine"_AUTHENTICATED_FIRST_FORWARD_AND_ROOTLESS_NATIVE_ATOMIC=PASS
echo "P08_PR84_$engine"_OFFICIAL_014_RELEASE=NOT_ISSUED
echo "P08_PR84_$engine"_PRODUCTION=UNCHANGED
