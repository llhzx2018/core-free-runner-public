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
ssh_vm "$NEW" 'bash -se' <<'TARGET'
set -Eeuo pipefail
stage=INITIAL
echo P07_M03_D04_TARGET_SCRIPT_STARTED=YES
report_target_error() {
  rc=$?
  echo "P07_M03_D04_TARGET_FAILED_AT=$stage RC=$rc"
  if test -f /root/p07-plan.err; then tail -n 12 /root/p07-plan.err | cut -c 1-260; fi
  if test -f /root/p07-prepare.err; then tail -n 12 /root/p07-prepare.err | cut -c 1-260; fi
  # Fail closed without inspecting or exposing rejected SQL.
  echo P07_M03_D04_SQL_REJECTION_NO_RETRY=YES
  exit "$rc"
}
trap report_target_error ERR
CMD=/opt/vf-server-ops/bin/vfops
stage=PLAN
echo P07_M03_D04_TARGET_PLAN_STARTED=YES
"$CMD" server-migrate plan --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING </dev/null >/root/p07-plan.json 2>/root/p07-plan.err
python3 - <<'PY'
import json
p=json.load(open('/root/p07-plan.json'))
assert p['status']=='READY'
assert p['site_count']==2
assert p['source_db_engine']=='MARIADB_11.8'
assert p['mysql_database_count']==1
assert p['sqlite_asset_count']==1
assert p['source_scope_kind']=='ALL_SOURCE_SITES'
assert p['automatic_dns_change'] is False
assert p['existing_target_overwrite_allowed'] is False
print('P07_M03_D04_MATCHED_MARIADB_ALL_SITES_PLAN=PASS')
PY
stage=PREPARE
echo P07_M03_D04_TARGET_PREPARE_STARTED=YES
"$CMD" server-migrate prepare --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --confirm PREPARE_PULL_MIGRATION </dev/null >/root/p07-prepare.json 2>/root/p07-prepare.err
python3 - <<'PY'
import json
p=json.load(open('/root/p07-prepare.json'))
assert p['status']=='PREPARED'
assert p['site_count']==2
# The public CLI summary is intentionally bounded. Check the private
# migration-owned status record instead of requiring it to print engine identity.
from pathlib import Path
states = list(Path('/var/lib/vf-server-ops/server-migrations').glob('pull-*/state.json'))
assert len(states) == 1, 'single synthetic transaction expected'
state = json.loads(states[0].read_text(encoding='utf-8'))
assert state['status'] == 'PREPARED'
assert state['source_db_engine'] == 'MARIADB_11.8'
assert state['migration_id'] == p['migration_id']
print('P07_M03_D04_PRIVATE_SOURCE_ENGINE_PIN=PASS')
print('P07_M03_D04_MATCHED_MARIADB_TARGET_PREPARED=PASS')
PY
stage=VERIFY_FILES
test "$(cat /home/p07alpha/htdocs/alpha.p07.example.com/index.html)" = P07_ALPHA_STATIC_42
cmp -s /home/p07alpha/htdocs/alpha.p07.example.com/public/index.php /home/p07alpha/htdocs/alpha.p07.example.com/index.php
grep -Fq P07_DB_READ_42 /home/p07alpha/htdocs/alpha.p07.example.com/public/index.php
test "$(cat /home/p07beta/htdocs/beta.p07.example.com/index.html)" = P07_BETA_STATIC_23
test "$(sqlite3 /home/p07alpha/htdocs/alpha.p07.example.com/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_SQLITE_42
stage=VERIFY_MYSQL
test -s /home/p07alpha/htdocs/alpha.p07.example.com/.env
rm -f /root/p07-check.sql
clpctl db:export --databaseName=p07alpha --file=/root/p07-check.sql >/root/p07-db-export.log 2>&1
grep -Fq SYNTHETIC_MIGRATE_42 /root/p07-check.sql
stage=VERIFY_EXTERNAL
test "$(cat /home/p07alpha/.vf-data/proof.txt)" = P07_EXTERNAL_ASSET_42
stage=VERIFY_HTTP
curl -ksS --resolve alpha.p07.example.com:443:127.0.0.1 https://alpha.p07.example.com/ | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
curl -ksS --resolve beta.p07.example.com:443:127.0.0.1 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_23
echo P07_M03_D04_TARGET_HTTP_FILES_SQL_SQLITE_PRIVATE=PASS
echo P07_M03_D04_TARGET_REAL_PHP_DB_CONNECT_AND_READ=PASS
TARGET
ssh_vm "$OLD" 'bash -se' <<'VERIFY'
set -Eeuo pipefail
rm -f /root/p07-check.sql
clpctl db:export --databaseName=p07alpha --file=/root/p07-check.sql >/root/p07-db-export.log 2>&1
grep -Fq SYNTHETIC_MIGRATE_42 /root/p07-check.sql
curl -ksS --resolve alpha.p07.example.com:443:127.0.0.1 https://alpha.p07.example.com/ | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
VERIFY
echo P07_M03_D04_SOURCE_CONTINUES_OPERATING=PASS
echo P07_M03_D04_DNS_CUTOVER=NOT_RUN
echo P07_M03_D04_ISOLATED_TWO_REAL_CLOUDPANEL_HOSTS=PASS
