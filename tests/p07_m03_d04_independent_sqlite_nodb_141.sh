#!/usr/bin/env bash
# P07-M03-D04 服务器迁移: isolated Debian13 x2; synthetic business data only.
set -Eeuo pipefail
umask 077
ROOT="$(pwd)"
WORK="$RUNNER_TEMP/p07-native-dualvm"
KEY="$WORK/id_ed25519"
OLD="172.29.71.11"
NEW="172.29.71.12"
mkdir -p "$WORK"
cleanup() {
  set +e
  for vm in old new; do
    test -f "$WORK/$vm.pid" && sudo kill "$(sudo cat "$WORK/$vm.pid")" 2>/dev/null || true
  done
  for tap in p07tapold p07tapnew; do sudo ip link del "$tap" >/dev/null 2>&1 || true; done
  sudo ip link del p07br0 >/dev/null 2>&1 || true
  sudo iptables -t nat -D POSTROUTING -s 172.29.71.0/24 -j MASQUERADE >/dev/null 2>&1 || true
  sudo rm -rf -- "$WORK"
  rm -rf -- "$ROOT/.p07-private-exact"
  echo P07_M03_D04_VMS_PRIVATE_SOURCE_CLEANED=YES
}
trap cleanup EXIT
ssh_vm() {
  local ip="$1"; shift
  ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="$WORK/known_hosts" -o ConnectTimeout=9 root@"$ip" "$@"
}
test "$(git -C "$ROOT/.p07-private-exact" rev-parse HEAD)" = 3c82ed9597eb6aae4aa0fcda45dc7425376b9985
test -c /dev/kvm && sudo test -w /dev/kvm
test -c /dev/net/tun || { echo P07_M03_D04_TUN_UNAVAILABLE; exit 61; }
sudo apt-get update -qq >/dev/null
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq qemu-system-x86 qemu-utils cloud-image-utils iproute2 iptables openssh-client rsync >/dev/null
echo P07_M03_D04_KVM_QEMU=PASS
cd "$WORK"
BASE="https://cdimage.debian.org/images/cloud/trixie/latest"
IMAGE="debian-13-generic-amd64.qcow2"
curl --retry 2 --connect-timeout 20 --max-time 180 -fsSLo SHA512SUMS "$BASE/SHA512SUMS"
curl --retry 2 --connect-timeout 20 --max-time 360 -fsSLo "$IMAGE" "$BASE/$IMAGE"
grep -E "[[:space:]](\*|)$IMAGE$" SHA512SUMS > image.sha512
test -s image.sha512
sha512sum -c image.sha512 >/dev/null
echo P07_M03_D04_OFFICIAL_DEBIAN13_IMAGE_VERIFIED=PASS
ssh-keygen -q -t ed25519 -N '' -f "$KEY"
PUB="$(cat "$KEY.pub")"
sudo ip link add p07br0 type bridge
sudo ip addr add 172.29.71.1/24 dev p07br0
sudo ip link set p07br0 up
sudo ip tuntap add dev p07tapold mode tap user "$(id -un)"
sudo ip tuntap add dev p07tapnew mode tap user "$(id -un)"
for tap in p07tapold p07tapnew; do sudo ip link set "$tap" master p07br0; sudo ip link set "$tap" up; done
sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null
sudo iptables -A FORWARD -i p07br0 -j ACCEPT
sudo iptables -A FORWARD -o p07br0 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.29.71.0/24 -j MASQUERADE
for vm in old new; do
  if test "$vm" = old; then ip="$OLD"; mac="52:54:00:77:00:11"; tap=p07tapold
  else ip="$NEW"; mac="52:54:00:77:00:12"; tap=p07tapnew; fi
  cat > "$vm-user.yml" <<EOF
#cloud-config
hostname: p07-$vm
fqdn: $vm.p07.test
manage_etc_hosts: true
disable_root: false
ssh_pwauth: false
users:
  - default
  - name: root
    lock_passwd: true
    ssh_authorized_keys:
      - $PUB
write_files:
  - path: /etc/ssh/sshd_config.d/40-p07-test.conf
    content: |
      PermitRootLogin prohibit-password
      PasswordAuthentication no
runcmd:
  - [systemctl, restart, ssh]
EOF
  cat > "$vm-net.yml" <<EOF
version: 2
ethernets:
  eth0:
    match:
      macaddress: "$mac"
    set-name: eth0
    dhcp4: false
    addresses: [$ip/24]
    routes:
      - to: default
        via: 172.29.71.1
    nameservers:
      addresses: [1.1.1.1, 8.8.8.8]
EOF
  printf 'instance-id: p07-%s\nlocal-hostname: %s.p07.test\n' "$vm" "$vm" > "$vm-meta.yml"
  cloud-localds --network-config="$vm-net.yml" "$vm-seed.iso" "$vm-user.yml" "$vm-meta.yml"
  qemu-img create -q -f qcow2 -F qcow2 -b "$WORK/$IMAGE" "$vm.qcow2" 16G
  sudo qemu-system-x86_64 -name "p07-$vm" -machine q35,accel=kvm -cpu host -smp 2 -m 3584 \
    -no-reboot -display none -monitor none -serial "file:$WORK/$vm.serial" \
    -drive "file=$WORK/$vm.qcow2,format=qcow2,if=virtio" \
    -drive "file=$WORK/$vm-seed.iso,media=cdrom,readonly=on" \
    -netdev "tap,id=n0,ifname=$tap,script=no,downscript=no" \
    -device "virtio-net-pci,netdev=n0,mac=$mac" \
    -pidfile "$WORK/$vm.pid" -daemonize
done
for ip in "$OLD" "$NEW"; do
  ready=false
  for n in $(seq 1 60); do
    if ssh_vm "$ip" 'test -r /etc/debian_version' >/dev/null 2>&1; then ready=true; break; fi
    sleep 5
  done
  if test "$ready" != true; then echo P07_M03_D04_CLOUD_VM_SSH=FAILED; exit 62; fi
  ssh_vm "$ip" 'cloud-init status --wait' >/dev/null
  echo P07_M03_D04_NATIVE_DEBIAN13_SSH=PASS
done
for ip in "$OLD" "$NEW"; do
  if test "$ip" = "$OLD"; then
    selected_engine=MARIADB_11.8
    engine_role=SOURCE_MARIADB_11_8
  else
    selected_engine=MARIADB_11.8
    engine_role=TARGET_MARIADB_11_8
  fi
  ssh_vm "$ip" "P07_DB_ENGINE=$selected_engine bash -se" <<'INSTALL'
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/root/p07-apt.log 2>&1
apt-get install -y -qq curl wget sudo rsync sqlite3 cron python3 >>/root/p07-apt.log 2>&1
curl -fsSL --connect-timeout 20 --max-time 120 https://installer.cloudpanel.io/ce/v2/install.sh -o /root/p07-installer.sh
echo '8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476  /root/p07-installer.sh' | sha256sum -c >/dev/null
timeout --signal=TERM --kill-after=20s 1200s env DB_ENGINE="$P07_DB_ENGINE" bash /root/p07-installer.sh >/root/p07-cloudpanel.log 2>&1
clpctl --version >/dev/null
test -f /home/clp/htdocs/app/data/db.sq3
if test "$P07_DB_ENGINE" = MYSQL_8.4; then
  systemctl is-active --quiet mysql
  mysqld --version | grep -Eq '8[.]4[.]'
elif test "$P07_DB_ENGINE" = MARIADB_11.8; then
  systemctl is-active --quiet mariadb
  mariadbd --version | grep -Eq '11[.]8[.]'
else
  echo P07_M03_D04_UNSUPPORTED_FIXTURE_ENGINE >&2
  exit 79
fi
INSTALL
  echo "P07_M03_D04_${engine_role}=PASS"
  ssh_vm "$ip" 'bash -se' <<'INITIALIZE'
set -Eeuo pipefail
clpctl user:add --userName=p07testadmin --email=p07testadmin@example.com --firstName=P07 --lastName=Fixture --password='SyntheticOnly2026ABC!' --role=admin --timezone=UTC --status=1 >/root/p07-first-admin.log 2>&1
curl -kfsSL --max-time 45 https://127.0.0.1:8443/ -o /root/p07-first-page.html >/dev/null
python3 - <<'PY'
import sqlite3
p='/home/clp/htdocs/app/data/db.sq3'
with sqlite3.connect('file:'+p+'?mode=ro',uri=True) as con:
 row=con.execute('SELECT COUNT(*), SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) FROM database_server').fetchone()
assert row and int(row[0] or 0)>0 and int(row[1] or 0)>0
print('P07_M03_D04_CP_DATABASE_SERVER_INITIALIZED=PASS')
PY
INITIALIZE
done

test "$CASE_KIND" = SQLITE || test "$CASE_KIND" = NO_DB
if test "$CASE_KIND" = SQLITE; then
  SITE=sqlite.p07.example.com; SITEUSER=p07sqlite
else
  SITE=static.p07.example.com; SITEUSER=p07static
fi
SRCROOT="/home/$SITEUSER/htdocs/$SITE"
ssh_vm "$OLD" "KIND=$CASE_KIND bash -se" <<'SOURCE_FIXTURE'
set -Eeuo pipefail
if test "$KIND" = SQLITE; then
  domain=sqlite.p07.example.com; user=p07sqlite
  clpctl site:add:php --domainName="$domain" --phpVersion=8.4 --vhostTemplate=Generic --siteUser="$user" --siteUserPassword='SyntheticOnly2026ABC!' >/root/site-create.log 2>&1
  root="/home/$user/htdocs/$domain"
  if ! php8.4 -m | grep -iq '^sqlite3$'; then
    DEBIAN_FRONTEND=noninteractive apt-get -y -qq install php8.4-sqlite3 >/root/sqlite-extension.log 2>&1
    systemctl restart php8.4-fpm
  fi
  sqlite3 "$root/content.sqlite" 'CREATE TABLE marker(id INTEGER PRIMARY KEY, note TEXT); INSERT INTO marker VALUES(1,"SYNTHETIC_SQLITE_ORIGINAL_42");'
  cat >"$root/index.php" <<'PHP_PAGE'
<?php
$p = is_file(__DIR__.'/content.sqlite') ? __DIR__.'/content.sqlite' : dirname(__DIR__).'/content.sqlite';
$db = new SQLite3($p);
if (($_GET['write'] ?? '') === '1') $db->exec("INSERT INTO marker(note) VALUES('SYNTHETIC_TARGET_WRITE_OK')");
echo 'P07_SQLITE_OK_'.$db->querySingle('SELECT note FROM marker WHERE id=1').'_ROWS_'.$db->querySingle('SELECT COUNT(*) FROM marker');
PHP_PAGE
  install -d "$root/public"; cp "$root/index.php" "$root/public/index.php"
  chown -R "$user:$user" "$root"
  test "$(sqlite3 "$root/content.sqlite" 'PRAGMA integrity_check')" = ok
else
  domain=static.p07.example.com; user=p07static
  clpctl site:add:static --domainName="$domain" --siteUser="$user" --siteUserPassword='SyntheticOnly2026ABC!' >/root/site-create.log 2>&1
  root="/home/$user/htdocs/$domain"
  printf '<html><body>P07_NODB_HTML_42</body></html>\n' >"$root/index.html"
  install -d "$root/assets"
  printf '/* P07_NODB_CSS_42 */\n' >"$root/assets/app.css"
  chown -R "$user:$user" "$root"
fi
SOURCE_FIXTURE
printf 'P07_D04_%s_SOURCE_SYNTHETIC=PASS\n' "$CASE_KIND"
ssh_vm "$NEW" 'install -d -m 700 /root/.ssh; mkdir -p /opt/vf-server-ops'
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$WORK/known_hosts" "$KEY" root@"$NEW":/root/.ssh/p07_test_key
ssh_vm "$NEW" 'chmod 600 /root/.ssh/p07_test_key'
ssh_vm "$NEW" "ssh -i /root/.ssh/p07_test_key -o BatchMode=yes -o StrictHostKeyChecking=accept-new root@$OLD true"
test -d "$P07_RELEASE141_OVERLAY"
rsync -aq -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$WORK/known_hosts" \
  "$P07_RELEASE141_OVERLAY/bin" "$P07_RELEASE141_OVERLAY/lib" "$P07_RELEASE141_OVERLAY/components" \
  "$P07_RELEASE141_OVERLAY/BUILD_ID" "$ROOT/.p07-private-exact/VERSION" root@"$NEW":/opt/vf-server-ops/
ssh_vm "$NEW" 'chmod +x /opt/vf-server-ops/bin/*; test "$(cat /opt/vf-server-ops/BUILD_ID)" = 0.1.0-release141'
echo P07_D04_EXACT_RELEASE141_TARGET_RUNTIME=PASS
ssh_vm "$NEW" "SITE=$SITE KIND=$CASE_KIND bash -se" <<'MIGRATE'
set -Eeuo pipefail
step=START
trap 'code=$?; echo "P07_D04_BLOCKED_AT=$step"; exit "$code"' ERR
CMD=/opt/vf-server-ops/bin/vfops
step=PLAN
"$CMD" server-migrate plan --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site "$SITE" --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING \
  </dev/null >/root/m03-plan.json 2>/root/m03-plan.err
python3 -B - <<'PY'
import json,os
p=json.load(open('/root/m03-plan.json'))
assert p['status']=='READY' and p['site_count']==1
assert p['mysql_database_count']==0
assert p['sqlite_asset_count']==(1 if os.environ['KIND']=='SQLITE' else 0)
assert p['automatic_dns_change'] is False
assert p['existing_target_overwrite_allowed'] is False
print('P07_D04_SINGLE_SITE_READONLY_PLAN=PASS')
PY
step=PREPARE
"$CMD" server-migrate prepare --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site "$SITE" --confirm PREPARE_PULL_MIGRATION </dev/null >/root/m03-prepare.json 2>/root/m03-prepare.err
python3 -B - <<'PY'
import json
from pathlib import Path
p=json.load(open('/root/m03-prepare.json'))
assert p['status']=='PREPARED' and p['site_count']==1
states=list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(states)==1
state=json.loads(states[0].read_text())
assert state['status']=='PREPARED' and state['migration_id']==p['migration_id']
print('P07_D04_INDEPENDENT_MIGRATION_ID_AND_PREPARED=PASS')
PY
step=VERIFY_TARGET
if test "$KIND" = SQLITE; then
  dir=/home/p07sqlite/htdocs/sqlite.p07.example.com
  test "$(sqlite3 "$dir/content.sqlite" 'PRAGMA integrity_check')" = ok
  test "$(sqlite3 "$dir/content.sqlite" 'SELECT note FROM marker WHERE id=1')" = SYNTHETIC_SQLITE_ORIGINAL_42
  test "$(sqlite3 "$dir/content.sqlite" 'SELECT COUNT(*) FROM marker')" = 1
  echo P07_D04_SQLITE_INTEGRITY_BASELINE_ROWS=PASS
else
  dir=/home/p07static/htdocs/static.p07.example.com
  grep -Fq P07_NODB_HTML_42 "$dir/index.html"
  grep -Fq P07_NODB_CSS_42 "$dir/assets/app.css"
  echo P07_D04_NO_DB_TARGET_DOCUMENTS=PASS
fi
MIGRATE
if test "$CASE_KIND" = SQLITE; then
  sourcehash="$(ssh_vm "$OLD" "sqlite3 '$SRCROOT/content.sqlite' '.dump' | sha256sum | cut -d' ' -f1")"
  targethash="$(ssh_vm "$NEW" "sqlite3 '$SRCROOT/content.sqlite' '.dump' | sha256sum | cut -d' ' -f1")"
  test "$sourcehash" = "$targethash"
  echo P07_D04_SQLITE_SNAPSHOT_LOGICAL_SHA256_MATCH=PASS
  ssh_vm "$NEW" 'bash -se' <<'SQLITE_HTTP'
set -Eeuo pipefail
if ! php8.4 -m | grep -iq '^sqlite3$'; then
  DEBIAN_FRONTEND=noninteractive apt-get -y -qq install php8.4-sqlite3 >/root/sqlite-extension.log 2>&1
  systemctl restart php8.4-fpm
fi
d=sqlite.p07.example.com
curl -kfsS --max-time 30 --resolve "$d:443:127.0.0.1" "https://$d/" | grep -Fq 'P07_SQLITE_OK_SYNTHETIC_SQLITE_ORIGINAL_42_ROWS_1'
curl -kfsS --max-time 30 --resolve "$d:443:127.0.0.1" "https://$d/?write=1" | grep -Fq 'P07_SQLITE_OK_SYNTHETIC_SQLITE_ORIGINAL_42_ROWS_2'
test "$(sqlite3 /home/p07sqlite/htdocs/$d/content.sqlite 'SELECT note FROM marker WHERE id=2')" = SYNTHETIC_TARGET_WRITE_OK
echo P07_D04_SQLITE_TARGET_REAL_HTTPS_READ_WRITE=PASS
SQLITE_HTTP
  test "$(ssh_vm "$OLD" "sqlite3 '$SRCROOT/content.sqlite' 'SELECT COUNT(*) FROM marker'")" = 1
  echo P07_D04_SQLITE_SOURCE_UNCHANGED=PASS
else
  sourcehash="$(ssh_vm "$OLD" "sha256sum '$SRCROOT/index.html' '$SRCROOT/assets/app.css' | cut -d' ' -f1")"
  targethash="$(ssh_vm "$NEW" "sha256sum '$SRCROOT/index.html' '$SRCROOT/assets/app.css' | cut -d' ' -f1")"
  test "$sourcehash" = "$targethash"
  echo P07_D04_NO_DB_SOURCE_TARGET_SHA256=PASS
  ssh_vm "$NEW" 'bash -se' <<'NO_DB_HTTP'
set -Eeuo pipefail
d=static.p07.example.com
curl -kfsS --max-time 30 --resolve "$d:443:127.0.0.1" "https://$d/" | grep -Fq P07_NODB_HTML_42
curl -kfsS --max-time 30 --resolve "$d:443:127.0.0.1" "https://$d/assets/app.css" | grep -Fq P07_NODB_CSS_42
echo P07_D04_NO_DB_REAL_HTTPS_HTML_CSS=PASS
NO_DB_HTTP
fi
printf 'P07_D04_%s_INDEPENDENT_DUAL_CLOUDPANEL=PASS\n' "$CASE_KIND"
echo P07_D04_SOURCE_STOP_DNS_CUTOVER=NOT_EXECUTED
