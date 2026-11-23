#!/usr/bin/env bash
# One-off synthetic P08 S3 transport proof on disposable GitHub-hosted VM.
# Never contact Owner VPS, Cloudflare, DNS, Production or private domains.
set -Eeuo pipefail
set +x
HOST="p08-stage-preview.example.org"
USER_NAME="p08stage"
SLUG="lp-preview"
ROOT="$(mktemp -d "${RUNNER_TEMP:-/tmp}/p08-ssh-nginx-XXXXXXXX")"
SITE="/home/$USER_NAME/vf-adops-static/$SLUG"
CREATED_USER=0
SETUP_STAGE=INIT
cleanup() {
  set +e
  if test -f "$ROOT/nginx.pid"; then sudo nginx -s stop -c "$ROOT/nginx.conf" >/dev/null 2>&1; fi
  if test -f "$ROOT/sshd.pid"; then sudo kill "$(cat "$ROOT/sshd.pid")" >/dev/null 2>&1; fi
  sudo rm -f /usr/local/share/ca-certificates/p08-s3-synthetic.crt
  if test "$CREATED_USER" = 1; then sudo userdel -r "$USER_NAME" >/dev/null 2>&1; fi
  rm -rf -- "$ROOT"
  echo "P08_S3_TRANSIENT_SSH_NGINX_CLEANUP=PASS"
}
on_exit() {
  code=$?
  if test "$code" -ne 0; then echo "P08_S3_TRANSPORT_SETUP_FAILED_STAGE=$SETUP_STAGE"; fi
  cleanup
}
trap on_exit EXIT
if id "$USER_NAME" >/dev/null 2>&1; then echo "P08_S3_TEST_USER_COLLISION=BLOCKED"; exit 2; fi
if test "${P08_ISOLATED_SSH_TEST:-}" != "YES"; then echo "P08_S3_NON_DISPOSABLE_ENV=BLOCKED"; exit 2; fi
if test "${P08_SOURCE_SHA:-}" != "97da994bfd4a6d34eff146779c3cb83771765f91"; then echo "P08_S3_PINNED_SOURCE_DRIFT=BLOCKED"; exit 2; fi
test -s "$GITHUB_WORKSPACE/private-p08/vendor/autoload.php"
test "$(git -C "$GITHUB_WORKSPACE/private-p08" rev-parse HEAD)" = "$P08_SOURCE_SHA"
command -v openssl >/dev/null
command -v ssh-keygen >/dev/null
SETUP_STAGE=APT_PACKAGES
sudo apt-get update -qq > "$ROOT/apt.log" 2>&1
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server nginx >> "$ROOT/apt.log" 2>&1
sudo systemctl stop ssh.socket ssh.service nginx.service >/dev/null 2>&1 || true
SETUP_STAGE=GENERATE_SSH_FIXTURE
sudo useradd --create-home --shell /bin/bash "$USER_NAME"
CREATED_USER=1
# Only the transient synthetic home is made traversable for real Nginx www-data.
sudo chmod 0755 "/home/$USER_NAME"
sudo usermod -p "$(openssl passwd -6 'synthetic-not-used-2026')" "$USER_NAME"
sudo install -d -o "$USER_NAME" -g "$USER_NAME" -m 0700 "/home/$USER_NAME/.ssh"
sudo install -d -o "$USER_NAME" -g "$USER_NAME" -m 0755 "/home/$USER_NAME/vf-adops-static" "$SITE" "$SITE/releases" "$SITE/.staging"
printf 'VF-ADOPS-STATIC-V1:%s\n' "$SLUG" | sudo tee "$SITE/.vf-adops-static-site" >/dev/null
sudo chown "$USER_NAME:$USER_NAME" "$SITE/.vf-adops-static-site"
sudo chmod 0644 "$SITE/.vf-adops-static-site"
ssh-keygen -q -t ed25519 -N '' -f "$ROOT/owner_key"
cat "$ROOT/owner_key.pub" | sudo tee "/home/$USER_NAME/.ssh/authorized_keys" >/dev/null
sudo chown "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.ssh/authorized_keys"
sudo chmod 0600 "/home/$USER_NAME/.ssh/authorized_keys"
ssh-keygen -q -t ed25519 -N '' -f "$ROOT/host_key"
ssh-keygen -y -f "$ROOT/host_key" | awk 'NF >= 2 {print $1 " " $2}' > "$ROOT/host_pin"
sudo mkdir -p /run/sshd
cat > "$ROOT/sshd.conf" <<EOF
Port 22
ListenAddress 127.0.0.1
HostKey $ROOT/host_key
PidFile $ROOT/sshd.pid
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
UsePAM no
AllowUsers $USER_NAME
AuthorizedKeysFile .ssh/authorized_keys
StrictModes yes
LogLevel ERROR
EOF
SETUP_STAGE=START_REAL_SSHD
sudo chown root:root "$ROOT/host_key" "$ROOT/sshd.conf"
sudo chmod 0600 "$ROOT/host_key"
sudo chmod 0644 "$ROOT/sshd.conf"
if ! sudo /usr/sbin/sshd -t -f "$ROOT/sshd.conf" > "$ROOT/sshd-preflight.log" 2>&1; then
  echo "P08_S3_SSHD_NATIVE_CONFIG=INVALID"
  exit 1
fi
if ! sudo /usr/sbin/sshd -f "$ROOT/sshd.conf" -E "$ROOT/sshd.log"; then
  if grep -qi 'Address already in use' "$ROOT/sshd.log"; then echo P08_S3_SSHD_FAIL=PORT_22_BUSY;
  elif grep -qi 'host key' "$ROOT/sshd.log"; then echo P08_S3_SSHD_FAIL=HOST_KEY;
  else echo P08_S3_SSHD_FAIL=SERVICE_START; fi
  exit 1
fi
if ! test -s "$ROOT/sshd.pid"; then echo "P08_S3_SSHD_FAIL=PID_MISSING"; exit 1; fi
SETUP_STAGE=TRUSTED_TLS_FIXTURE
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST" \
  -keyout "$ROOT/tls.key" -out "$ROOT/tls.crt" >/dev/null 2>&1
sudo cp "$ROOT/tls.crt" /usr/local/share/ca-certificates/p08-s3-synthetic.crt
sudo update-ca-certificates >/dev/null 2>&1
cat > "$ROOT/nginx.conf" <<EOF
user www-data;
worker_processes 1;
pid $ROOT/nginx.pid;
error_log $ROOT/nginx-error.log warn;
events { worker_connections 256; }
http {
  access_log off;
  server {
    listen 127.0.0.1:443 ssl;
    server_name $HOST;
    ssl_certificate $ROOT/tls.crt;
    ssl_certificate_key $ROOT/tls.key;
    root $SITE/current;
    index index.html;
    location / { try_files \$uri \$uri/ =404; }
  }
}
EOF
SETUP_STAGE=START_REAL_NGINX
sudo nginx -t -c "$ROOT/nginx.conf" >/dev/null 2>&1
sudo nginx -c "$ROOT/nginx.conf"
test -s "$ROOT/nginx.pid"
test -s "$ROOT/sshd.pid"
echo "P08_S3_NATIVE_OPENSSH_AND_NGINX_LISTENERS=PASS"
printf '%s %s\n' "$HOST" "$(cat "$ROOT/host_pin")" > "$ROOT/known_hosts"
chmod 0600 "$ROOT/known_hosts"
SETUP_STAGE=REAL_SSH_PINNED_KEY_AUTH
if ! ssh -F /dev/null -T -p 22 -i "$ROOT/owner_key" \
  -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$ROOT/known_hosts" -o GlobalKnownHostsFile=/dev/null \
  -o HostKeyAlias="$HOST" -o HostName=127.0.0.1 \
  -o HostKeyAlgorithms=ssh-ed25519 -o IdentitiesOnly=yes \
  -o IdentityAgent=none -o ForwardAgent=no \
  -o ClearAllForwardings=yes -o ProxyCommand=none -o ProxyJump=none \
  -o ConnectionAttempts=1 -o ConnectTimeout=5 \
  "$USER_NAME@$HOST" 'printf P08_SYNTHETIC_SSH_AUTH_OK' \
  > "$ROOT/ssh-preflight.log" 2>&1; then
  echo "P08_S3_TRANSPORT_SSH_AUTH=FAIL"
  exit 1
fi
if ! grep -qx 'P08_SYNTHETIC_SSH_AUTH_OK' "$ROOT/ssh-preflight.log"; then
  echo "P08_S3_TRANSPORT_SSH_STDOUT=UNVERIFIED"
  exit 1
fi
echo "P08_S3_TRANSPORT_SSH_AUTH=PASS"
export P08_TEST_APP_ROOT="$GITHUB_WORKSPACE/private-p08" P08_TEST_HOST="$HOST"
export P08_TEST_USERNAME="$USER_NAME" P08_TEST_SLUG="$SLUG" P08_TEST_ROOT="$ROOT"
export P08_TEST_SSH_PIN_FILE="$ROOT/host_pin" P08_TEST_SSH_IDENTITY_FILE="$ROOT/owner_key"
SETUP_STAGE=GATEWAY_REAL_SSH_TLS
set +e
php "$GITHUB_WORKSPACE/public-harness/scripts/temp_p08_s3_real_ssh_nginx.php" > "$ROOT/php-test.log" 2>&1
php_status=$?
set -e
if test "$php_status" -ne 0; then
  grep '^P08_S3_TRANSPORT_' "$ROOT/php-test.log" | tail -n 15 || true
  echo "P08_S3_NATIVE_SSH_NGINX_TLS=FAIL"
  exit 1
fi
if ! grep -Eq '^P08_S3_TRANSPORT_REAL_SSH_NGINX_TLS=[0-9]+/[0-9]+_PASS$' "$ROOT/php-test.log"; then
  grep '^P08_S3_TRANSPORT_' "$ROOT/php-test.log" | tail -n 15 || true
  echo "P08_S3_NATIVE_SSH_NGINX_TLS=NO_ACTUAL_PASS_RECEIPT"
  exit 1
fi
grep '^P08_S3_TRANSPORT_' "$ROOT/php-test.log"
echo "P08_S3_REAL_OPENSSH_NGINX_TLS=PASS"
