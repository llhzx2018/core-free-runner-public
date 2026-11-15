#!/usr/bin/env bash
# P07-M03-D04 服务器迁移: isolated Debian13 x2; synthetic business data only.
set -Eeuo pipefail
case "$P07_D05_SOURCE_ENGINE" in
  MYSQL_8.4|MARIADB_11.8) ;;
  *) echo P07_D05_SOURCE_ENGINE_UNSUPPORTED; exit 77 ;;
esac
umask 077
ROOT="$(pwd)"
WORK="$RUNNER_TEMP/p07-d05-fresh-native"
KEY="$WORK/id_ed25519"
OLD="172.29.71.11"
NEW="172.29.71.12"
mkdir -p "$WORK"
cleanup() {
  set +e
  for vm in old; do
    test -f "$WORK/$vm.pid" && sudo kill "$(sudo cat "$WORK/$vm.pid")" 2>/dev/null || true
  done
  for tap in p07tapold; do sudo ip link del "$tap" >/dev/null 2>&1 || true; done
  sudo ip link del p07br0 >/dev/null 2>&1 || true
  sudo iptables -t nat -D POSTROUTING -s 172.29.71.0/24 -j MASQUERADE >/dev/null 2>&1 || true
  sudo rm -rf -- "$WORK"
  rm -rf -- "$ROOT/.p07-private-d05active"
  echo P07_D05_FRESH_VMS_PRIVATE_SOURCE_CLEANED=YES
}
trap cleanup EXIT
ssh_vm() {
  local ip="$1"; shift
  ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="$WORK/known_hosts" -o ConnectTimeout=9 root@"$ip" "$@"
}
test "$(git -C "$ROOT/.p07-private-d05active" rev-parse HEAD)" = ee48366a31dfe9a08dd75cf563cbada4b288432f
test -c /dev/kvm && sudo test -w /dev/kvm
test -c /dev/net/tun || { echo P07_D05_FRESH_TUN_UNAVAILABLE; exit 61; }
sudo apt-get update -qq >/dev/null
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq qemu-system-x86 qemu-utils cloud-image-utils iproute2 iptables openssh-client rsync >/dev/null
echo P07_D05_FRESH_KVM_QEMU=PASS
cd "$WORK"
BASE="https://cdimage.debian.org/images/cloud/trixie/latest"
IMAGE="debian-13-generic-amd64.qcow2"
curl --retry 2 --connect-timeout 20 --max-time 180 -fsSLo SHA512SUMS "$BASE/SHA512SUMS"
curl --retry 2 --connect-timeout 20 --max-time 360 -fsSLo "$IMAGE" "$BASE/$IMAGE"
grep -E "[[:space:]](\*|)$IMAGE$" SHA512SUMS > image.sha512
test -s image.sha512
sha512sum -c image.sha512 >/dev/null
echo P07_D05_FRESH_OFFICIAL_DEBIAN13_IMAGE_VERIFIED=PASS
ssh-keygen -q -t ed25519 -N '' -f "$KEY"
PUB="$(cat "$KEY.pub")"
sudo ip link add p07br0 type bridge
sudo ip addr add 172.29.71.1/24 dev p07br0
sudo ip link set p07br0 up
sudo ip tuntap add dev p07tapold mode tap user "$(id -un)"

for tap in p07tapold; do sudo ip link set "$tap" master p07br0; sudo ip link set "$tap" up; done
sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null
sudo iptables -A FORWARD -i p07br0 -j ACCEPT
sudo iptables -A FORWARD -o p07br0 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.29.71.0/24 -j MASQUERADE
for vm in old; do
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
for ip in "$OLD"; do
  ready=false
  for n in $(seq 1 60); do
    if ssh_vm "$ip" 'test -r /etc/debian_version' >/dev/null 2>&1; then ready=true; break; fi
    sleep 5
  done
  if test "$ready" != true; then echo P07_D05_FRESH_CLOUD_VM_SSH=FAILED; exit 62; fi
  ssh_vm "$ip" 'cloud-init status --wait' >/dev/null
  echo P07_D05_FRESH_NATIVE_DEBIAN13_SSH=PASS
done
for ip in "$OLD"; do
  if test "$ip" = "$OLD"; then
    selected_engine="$P07_D05_SOURCE_ENGINE"
    engine_role=SOURCE_CLOUDPANEL
  else
    selected_engine=MYSQL_8.4
    engine_role=TARGET_MYSQL_8_4
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
  echo P07_D05_FRESH_UNSUPPORTED_FIXTURE_ENGINE >&2
  exit 79
fi
INSTALL
  echo "P07_D05_FRESH_${engine_role}=PASS"
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
print('P07_D05_FRESH_CP_DATABASE_SERVER_INITIALIZED=PASS')
PY
INITIALIZE
done


ssh_vm "$OLD" 'bash -se' <<'FRESH'
set -Eeuo pipefail
stage=START
on_error(){ rc=$?; echo "P07_D05_FRESH_FAILED_AT=$stage RC=$rc"; exit "$rc"; }
trap on_error ERR
test -f /home/clp/htdocs/app/data/db.sq3
stage=NATIVE_CLOUDPANEL_CREATE
clpctl site:add:php --domainName=alpha.p07.example.com --phpVersion=8.4 \
 --vhostTemplate=Generic --siteUser=p07alpha \
 --siteUserPassword='SyntheticOnly2026ABC!' >/root/d05-site.log 2>&1
clpctl db:add --domainName=alpha.p07.example.com \
 --databaseName=p07newmysql --databaseUserName=p07mysqlapp \
 --databaseUserPassword='SyntheticOnly2026ABC!' >/root/d05-db.log 2>&1
echo P07_D05_FRESH_NATIVE_MYSQL84_CLOUDPANEL_DB_CREATE=PASS

stage=ISOLATED_MARIA
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/root/d05-apt.log 2>&1
apt-get install -y -qq docker.io >/root/d05-docker.log 2>&1
systemctl start docker
pw='P07_Synthetic_Fresh_Root!'
docker run -d --name p07-d05-maria-source \
 --label 'p07.d05.synthetic=fresh' \
 -e "MARIADB_ROOT_PASSWORD=$pw" mariadb:11.8 >/root/d05-container.id
ready=0
for i in $(seq 1 90); do
 if docker exec -e "MYSQL_PWD=$pw" p07-d05-maria-source \
 mariadb -uroot -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
 sleep 2
done
test "$ready" -eq 1
docker exec -e "MYSQL_PWD=$pw" p07-d05-maria-source mariadb \
 -uroot --batch --skip-column-names -e 'SELECT @@version' | grep -Eq '^11[.]8[.]'
docker exec -i -e "MYSQL_PWD=$pw" p07-d05-maria-source mariadb -uroot <<'SQL'
CREATE DATABASE p07mariasource;
USE p07mariasource;
CREATE TABLE vf_payload (id INT PRIMARY KEY, label VARCHAR(80), metadata JSON, binary_bytes BLOB)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO vf_payload VALUES (1,'synthetic-maria-1','{"n":142}',X'01020304'),(2,'synthetic-maria-2','{"n":177}',X'ABCDEF00');
SQL
echo P07_D05_FRESH_MARIA_SOURCE_SYNTHETIC=PASS

stage=DUMP_GUARD
docker exec -e "MYSQL_PWD=$pw" p07-d05-maria-source \
 mariadb-dump -uroot --single-transaction --hex-blob --skip-comments \
 --skip-triggers p07mariasource >/root/d05-maria.sql
python3 - <<'PY'
import re
from pathlib import Path
p=Path('/root/d05-maria.sql')
data=p.read_bytes()
first,sep,rest=data.partition(b'\n')
if first.startswith(b'/*M!999999'):
 if not sep or not re.fullmatch(
    rb'/\*M!999999\\*- enable the sandbox mode \*/;?',first.rstrip(b' \t\r')
 ):
  raise SystemExit('D05_MARIA_UNKNOWN_BANNER')
 p.write_bytes(rest)
data=p.read_bytes()
if b'CREATE TABLE' not in data or re.search(
 rb'(?im)^\s*(CREATE USER|GRANT |REVOKE |SET GLOBAL|DROP DATABASE)',data
): raise SystemExit('D05_UNKNOWN_SQL_BLOCKED')
PY
echo P07_D05_FRESH_MARIA_DUMP_SQL_SAFE_FIXTURE=PASS

stage=NATIVE_CP_IMPORT
clpctl db:import --databaseName=p07newmysql --file=/root/d05-maria.sql \
 >/root/d05-import.log 2>&1
echo P07_D05_FRESH_MARIA_TO_NATIVE_MYSQL_CP_IMPORT=PASS

stage=REAL_PHP_PARITY
app=/home/p07alpha/htdocs/alpha.p07.example.com
cat >"$app/verify-db.php" <<'PHP'
<?php
try{
 mysqli_report(MYSQLI_REPORT_ERROR|MYSQLI_REPORT_STRICT);
 $db=new mysqli('127.0.0.1','p07mysqlapp','SyntheticOnly2026ABC!','p07newmysql',3306);
 $r=$db->query("SELECT id,label,JSON_UNQUOTE(JSON_EXTRACT(metadata,'$.n')) AS n,HEX(binary_bytes) AS b FROM vf_payload ORDER BY id");
 $x=$r->fetch_all(MYSQLI_ASSOC);
 if(count($x)!==2 || $x[0]['label']!=='synthetic-maria-1'
 || $x[1]['label']!=='synthetic-maria-2' || (int)$x[0]['n']!==142
 || (int)$x[1]['n']!==177 || $x[0]['b']!=='01020304'
 || $x[1]['b']!=='ABCDEF00'){http_response_code(503);exit;}
 header('Content-Type: text/plain');
 echo 'P07_D05_FRESH_REAL_PHP_DATA=PASS';
}catch(Throwable $e){http_response_code(503);}
PHP
if test -d "$app/public"; then cp "$app/verify-db.php" "$app/public/verify-db.php"; fi
chown p07alpha:p07alpha "$app/verify-db.php"
if test -d "$app/public"; then chown p07alpha:p07alpha "$app/public/verify-db.php"; fi
curl -kfsS --noproxy '*' --resolve alpha.p07.example.com:443:127.0.0.1 \
 https://alpha.p07.example.com/verify-db.php | grep -Fxq P07_D05_FRESH_REAL_PHP_DATA=PASS
echo P07_D05_FRESH_CP_SITE_IMPORT_JSON_BLOB_PARITY=PASS

stage=MANAGED_BACKUP_RESTORE
clpctl db:export --databaseName=p07newmysql --file=/root/d05-managed.sql \
 >/root/d05-export.log 2>&1
grep -Fq synthetic-maria-1 /root/d05-managed.sql
echo P07_D05_FRESH_CLOUDPANEL_MANAGED_EXPORT=PASS
runuser -u clp -- /usr/bin/clpctl db:backup --retentionPeriod=7 \
 >/root/d05-backup.log 2>&1
find /home/p07alpha/backups -type f -size +0c -print -quit | grep -q .
echo P07_D05_FRESH_CLOUDPANEL_MANAGED_BACKUP=PASS
clpctl db:add --domainName=alpha.p07.example.com \
 --databaseName=p07restoreverify --databaseUserName=p07restoreuser \
 --databaseUserPassword='SyntheticOnly2026ABC!' >/root/d05-restorecreate.log 2>&1
clpctl db:import --databaseName=p07restoreverify --file=/root/d05-managed.sql \
 >/root/d05-restore.log 2>&1
clpctl db:export --databaseName=p07restoreverify \
 --file=/root/d05-restored.sql >/root/d05-readback.log 2>&1
grep -Fq synthetic-maria-1 /root/d05-restored.sql
grep -Fq synthetic-maria-2 /root/d05-restored.sql
echo P07_D05_FRESH_CLOUDPANEL_RESTORE_READBACK=PASS

stage=SOURCE_UNCHANGED
test "$(docker exec -e "MYSQL_PWD=$pw" p07-d05-maria-source \
 mariadb -uroot p07mariasource -N -B -e 'SELECT COUNT(*) FROM vf_payload')" = 2
python3 - <<'PY'
import sqlite3
with sqlite3.connect('file:/home/clp/htdocs/app/data/db.sq3?mode=ro',uri=True) as c:
 count,active=c.execute("SELECT COUNT(*),SUM(is_active) FROM database_server").fetchone()
assert count==1 and active==1
print('P07_D05_FRESH_CLOUDPANEL_NATIVE_MYSQL_ACTIVE=PASS')
PY
echo P07_D05_FRESH_MARIA_SOURCE_PRESERVED=PASS
echo P07_D05_FRESH_PRODUCTION_DNS=UNCHANGED
FRESH
echo P07_D05_FRESH_NATIVE_MYSQL_TARGET_PHASE=PASS
