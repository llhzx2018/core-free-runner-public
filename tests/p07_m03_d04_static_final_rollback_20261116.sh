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
test "$(git -C "$ROOT/.p07-private-exact" rev-parse HEAD)" = 80e70ba47a1f0a8dc399e0381aeb29a66a7e6c4e
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
ssh_vm "$OLD" 'bash -se' <<'SOURCE'
set -Eeuo pipefail
stage=INITIAL
report_source_fixture_error() {
  rc=$?
  echo "P07_M03_D04_SOURCE_FIXTURE_FAILED_AT=$stage RC=$rc"
  exit "$rc"
}
trap report_source_fixture_error ERR
stage=CREATE_ALPHA
clpctl site:add:php --domainName=alpha.p07.example.com --phpVersion=8.4 --vhostTemplate=Generic --siteUser=p07alpha --siteUserPassword='SyntheticOnly2026ABC!' > /root/p07-create.log 2>&1
stage=CREATE_BETA
clpctl site:add:static --domainName=beta.p07.example.com --siteUser=p07beta --siteUserPassword=SyntheticOnly2026ABC >> /root/p07-create.log 2>&1
stage=CREATE_DATABASE
clpctl db:add --domainName=alpha.p07.example.com --databaseName=p07alpha --databaseUserName=p07alphauser --databaseUserPassword='SyntheticOnly2026ABC!' > /root/p07-db-add.log 2>&1
stage=INSERT_SYNTHETIC_MYSQL
printf '%s\n' 'CREATE TABLE p07_marker (id INT PRIMARY KEY, marker VARCHAR(40));' "INSERT INTO p07_marker VALUES(1,'SYNTHETIC_MIGRATE_42');" > /root/p07-seed.sql
clpctl db:import --databaseName=p07alpha --file=/root/p07-seed.sql >/root/p07-sql-seed.log 2>&1
stage=WRITE_SYNTHETIC_FILES
printf 'P07_ALPHA_STATIC_42\n' > /home/p07alpha/htdocs/alpha.p07.example.com/index.html
install -d /home/p07alpha/htdocs/alpha.p07.example.com/public
cat > /home/p07alpha/htdocs/alpha.p07.example.com/public/index.php <<'SYNTHETIC_PHP'
<?php
declare(strict_types=1);
$cfg = __DIR__ . '/.env';
if (!is_file($cfg)) {
    $cfg = dirname(__DIR__) . '/.env';
}
$env = is_file($cfg) ? parse_ini_file($cfg, false, INI_SCANNER_RAW) : false;
if (!is_array($env)) {
    http_response_code(503);
    echo 'P07_DB_NOT_READY';
    exit;
}
try {
    $dsn = 'mysql:host=' . $env['DB_HOST'] . ';port=' . $env['DB_PORT']
        . ';dbname=' . $env['DB_DATABASE'] . ';charset=utf8mb4';
    $pw = trim((string)$env['DB_PASSWORD'], "'\"");
    $db = new PDO($dsn, (string)$env['DB_USERNAME'], $pw,
                  [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $marker = $db->query('SELECT marker FROM p07_marker WHERE id=1')->fetchColumn();
    if ($marker !== 'SYNTHETIC_MIGRATE_42') {
        throw new RuntimeException('mismatch');
    }
    echo 'P07_ALPHA_WEB_42 P07_DB_READ_42';
} catch (Throwable $e) {
    http_response_code(503);
    echo 'P07_DB_NOT_READY';
}
SYNTHETIC_PHP
cp /home/p07alpha/htdocs/alpha.p07.example.com/public/index.php /home/p07alpha/htdocs/alpha.p07.example.com/index.php
printf 'P07_BETA_STATIC_23\n' > /home/p07beta/htdocs/beta.p07.example.com/index.html
sqlite3 /home/p07alpha/htdocs/alpha.p07.example.com/test.sqlite 'CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT); INSERT INTO marker VALUES(1,"SYNTHETIC_SQLITE_42");'
mkdir -p /home/p07alpha/.vf-data
printf 'P07_EXTERNAL_ASSET_42\n' > /home/p07alpha/.vf-data/proof.txt
# Synthetic PHP application DB mapping; required for protected target credential rewrite.
cat > /home/p07alpha/htdocs/alpha.p07.example.com/.env <<'P07_ENV'
APP_NAME=P07Synthetic
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=p07alpha
DB_USERNAME=p07alphauser
DB_PASSWORD='SyntheticOnly2026ABC!'
P07_ENV
chmod 600 /home/p07alpha/htdocs/alpha.p07.example.com/.env
chown -R p07alpha:p07alpha /home/p07alpha/.vf-data /home/p07alpha/htdocs/alpha.p07.example.com
stage=CHECK_MYSQL
rm -f /root/p07-check.sql
clpctl db:export --databaseName=p07alpha --file=/root/p07-check.sql >/root/p07-db-export.log 2>&1
grep -Fq SYNTHETIC_MIGRATE_42 /root/p07-check.sql
stage=CHECK_SQLITE
test "$(sqlite3 /home/p07alpha/htdocs/alpha.p07.example.com/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_SQLITE_42
stage=CHECK_HTTP
if curl -ksS --resolve alpha.p07.example.com:443:127.0.0.1 https://alpha.p07.example.com/ | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'; then
  echo P07_M03_D04_SOURCE_PHP_HTTPS=PASS
else
  echo P07_M03_D04_SOURCE_PHP_HTTPS=NOT_PROVEN
fi
if curl -ksS --resolve beta.p07.example.com:443:127.0.0.1 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_23; then
  echo P07_M03_D04_SOURCE_STATIC_HTTP=PASS
else
  echo P07_M03_D04_SOURCE_STATIC_HTTP=NOT_PROVEN
fi
SOURCE
echo P07_M03_D04_OLD_TWO_SITES_SQL_SQLITE_EXTERNAL_HTTP=PASS
cd "$ROOT"
ssh_vm "$NEW" 'install -d -m 700 /root/.ssh; mkdir -p /opt/vf-server-ops'
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$WORK/known_hosts" \
  "$KEY" root@"$NEW":/root/.ssh/p07_test_key
ssh_vm "$NEW" 'chmod 600 /root/.ssh/p07_test_key'
ssh_vm "$NEW" "ssh -i /root/.ssh/p07_test_key -o BatchMode=yes -o StrictHostKeyChecking=accept-new root@$OLD true"
rsync -aq -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$WORK/known_hosts" \
  "$ROOT/.p07-private-exact/bin" "$ROOT/.p07-private-exact/lib" \
  "$ROOT/.p07-private-exact/VERSION" "$ROOT/.p07-private-exact/BUILD_ID" \
  root@"$NEW":/opt/vf-server-ops/
echo P07_M03_D04_EXACT_SOURCE_PR348_STAGED=PASS
ssh_vm "$NEW" 'echo P07_M03_D04_TARGET_SSH_SESSION=PASS; test -x /opt/vf-server-ops/bin/vfops; /opt/vf-server-ops/bin/vfops --version'
# Selected static site only: no SQL import, no SQLite or cross-engine data;
# the source's unrelated PHP+MariaDB site remains installed for isolation proof.
ssh_vm "$NEW" 'bash -se' <<'TARGET'
set -Eeuo pipefail
CMD=/opt/vf-server-ops/bin/vfops
# Wrong confirmation must not freeze source or change the staged task.
"$CMD" server-migrate plan --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site beta.p07.example.com --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING \
  </dev/null >/root/p07-final-plan.json 2>/root/p07-final-plan.err
python3 - <<'PY'
import json
p=json.load(open('/root/p07-final-plan.json'))
assert p['status']=='READY'
assert p['site_count']==1
assert p['mysql_database_count']==0
assert p['sqlite_asset_count']==0
assert p['source_db_engine']=='MARIADB_11.8'
assert p['source_scope_kind']=='SELECTED_SITES'
assert p['automatic_dns_change'] is False
assert p['existing_target_overwrite_allowed'] is False
print("P07_D04_STATIC_SINGLE_SITE_ENGINE_PLAN=PASS")
PY
"$CMD" server-migrate prepare --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site beta.p07.example.com --confirm PREPARE_PULL_MIGRATION \
  </dev/null >/root/p07-final-prepare.json 2>/root/p07-final-prepare.err
python3 - <<'PY'
import json
from pathlib import Path
p=json.load(open('/root/p07-final-prepare.json'))
assert p['status']=='PREPARED' and p['site_count']==1
files=list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(files)==1
st=json.loads(files[0].read_text(encoding='utf-8'))
assert st['source_db_engine']=='MARIADB_11.8'
assert st['status']=='PREPARED'
assert len(st['sites'])==1
assert st['sites'][0]['domain']=='beta.p07.example.com'
assert st['sites'][0]['mysql_databases']==[]
assert st['source_runtime_frozen'] is False
assert st['dns_changed_by_p07'] is False
Path('/root/p07-final-mid').write_text(st['migration_id'], encoding='ascii')
print("P07_D04_STATIC_SELECTED_SITE_PREPARED=PASS")
PY
test "$(cat /home/p07beta/htdocs/beta.p07.example.com/index.html)" = P07_BETA_STATIC_23
TARGET
# An independent change AFTER PREPARED, while the old site is serving traffic.
ssh_vm "$OLD" 'bash -se' <<'SOURCE_DELTA'
set -Eeuo pipefail
test "$(cat /home/p07beta/htdocs/beta.p07.example.com/index.html)" = P07_BETA_STATIC_23
printf 'P07_BETA_STATIC_FINAL_99\n' > /home/p07beta/htdocs/beta.p07.example.com/index.html
curl -kfsS --resolve beta.p07.example.com:443:127.0.0.1 \
  https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_FINAL_99
echo P07_D04_SOURCE_LIVE_DELTA_AFTER_PREPARED=PASS
SOURCE_DELTA
ssh_vm "$NEW" 'bash -se' <<'TARGET_FINAL'
set -Eeuo pipefail
CMD=/opt/vf-server-ops/bin/vfops
MID="$(cat /root/p07-final-mid)"
test -n "$MID"
set +e
"$CMD" server-migrate cutover --migration-id "$MID" \
 --confirm WRONG_CONFIRMATION </dev/null >/root/p07-final-wrong.json 2>/root/p07-final-wrong.err
rc=$?
set -e
test "$rc" -eq 13
python3 - <<'PY'
import json
from pathlib import Path
rows=list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(rows)==1
st=json.loads(rows[0].read_text(encoding='utf-8'))
assert st['status']=='PREPARED'
assert st['source_runtime_frozen'] is False
print('P07_D04_WRONG_FINAL_CONFIRMATION_NO_FREEZE=PASS')
PY
# This is a disposable synthetic host. No external DNS and no business VPS.
"$CMD" server-migrate cutover --migration-id "$MID" \
 --confirm "CUTOVER_PULL:$MID" </dev/null >/root/p07-final-cutover.json 2>/root/p07-final-cutover.err
python3 - <<'PY'
import json
from pathlib import Path
p=json.load(open('/root/p07-final-cutover.json'))
assert p['status']=='CUTOVER_PREP_READY'
rows=list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(rows)==1
st=json.loads(rows[0].read_text(encoding='utf-8'))
assert st['status']=='CUTOVER_PREP_READY'
assert st['source_runtime_frozen'] is True
assert st['dns_changed_by_p07'] is False
assert st['source_delete_allowed'] is False
assert st['existing_target_overwrite_allowed'] is False
assert st['mysql_final_count']==0
print('P07_D04_STATIC_FINAL_SYNC_PREP_READY=PASS')
PY
test "$(cat /home/p07beta/htdocs/beta.p07.example.com/index.html)" = P07_BETA_STATIC_FINAL_99
curl -kfsS --resolve beta.p07.example.com:443:127.0.0.1 \
  https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_FINAL_99
echo P07_D04_SOURCE_TO_TARGET_FINAL_DELTA=PASS
# Test that manual DNS ambiguity blocks rollback before SOURCE is unpaused:
# manipulate only this disposable VM's /etc/hosts, never public DNS.
printf '172.29.71.12 beta.p07.example.com\n' >> /etc/hosts
set +e
"$CMD" server-migrate rollback --migration-id "$MID" \
 --confirm "ROLLBACK_PULL:$MID" </dev/null >/root/p07-final-rollback-denied.json 2>/root/p07-final-rollback-denied.err
rc=$?
set -e
test "$rc" -eq 13
python3 - <<'PY'
import json
from pathlib import Path
rows=list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(rows)==1
st=json.loads(rows[0].read_text(encoding='utf-8'))
assert st['status']=='CUTOVER_PREP_READY'
assert st['source_runtime_frozen'] is True
print('P07_D04_MANUAL_ROUTE_UNVERIFIED_ROLLBACK_DENIED=PASS')
PY
# Now exclusively route this synthetic name back to the pinned old VM.
sed -i 's/172[.]29[.]71[.]12 beta[.]p07[.]example[.]com/172.29.71.11 beta.p07.example.com/' /etc/hosts
python3 - <<'PY'
import socket
ips={row[4][0] for row in socket.getaddrinfo('beta.p07.example.com',443,type=socket.SOCK_STREAM)}
assert ips=={'172.29.71.11'}
PY
"$CMD" server-migrate rollback --migration-id "$MID" \
 --confirm "ROLLBACK_PULL:$MID" </dev/null >/root/p07-final-rollback.json 2>/root/p07-final-rollback.err
python3 - <<'PY'
import json
from pathlib import Path
p=json.load(open('/root/p07-final-rollback.json'))
assert p['status']=='ROLLED_BACK'
rows=list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(rows)==1
st=json.loads(rows[0].read_text(encoding='utf-8'))
assert st['status']=='ROLLED_BACK'
assert st['source_runtime_frozen'] is False
assert st['target_runtime_activated'] is False
assert st['dns_changed_by_p07'] is False
assert st['source_delete_allowed'] is False
assert st['existing_target_overwrite_allowed'] is False
print('P07_D04_STATIC_EXPLICIT_ROLLBACK_RECEIPT=PASS')
PY
echo P07_D04_NO_PUBLIC_DNS_CHANGED=PASS
TARGET_FINAL
ssh_vm "$OLD" 'bash -se' <<'VERIFY_RESTORED'
set -Eeuo pipefail
systemctl is-active --quiet nginx
test "$(cat /home/p07beta/htdocs/beta.p07.example.com/index.html)" = P07_BETA_STATIC_FINAL_99
curl -kfsS --resolve beta.p07.example.com:443:127.0.0.1 \
 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_FINAL_99
curl -kfsS --resolve alpha.p07.example.com:443:127.0.0.1 \
 https://alpha.p07.example.com/ | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
clpctl db:export --databaseName=p07alpha --file=/root/p07-verify-rollback.sql >/root/p07-verify-rollback.log 2>&1
grep -Fq SYNTHETIC_MIGRATE_42 /root/p07-verify-rollback.sql
echo P07_D04_ORIGINAL_SOURCE_AND_UNRELATED_DB_RECOVERED=PASS
VERIFY_RESTORED
echo P07_D04_STATIC_FINAL_DELTA_AND_ROLLBACK_TWO_CLOUDPANEL_VMS=PASS
echo P07_D04_PRODUCTION_DNS_AND_OWNER_VPS=NOT_RUN
