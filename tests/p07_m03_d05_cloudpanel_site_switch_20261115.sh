#!/usr/bin/env bash
# P07-M03-D04 服务器迁移: isolated Debian13 x2; synthetic business data only.
set -Eeuo pipefail
case "$P07_D05_SOURCE_ENGINE" in
  MYSQL_8.4|MARIADB_11_8) ;;
  *) echo P07_D05_SOURCE_ENGINE_UNSUPPORTED; exit 77 ;;
esac
umask 077
ROOT="$(pwd)"
WORK="$RUNNER_TEMP/p07-d05-cloudpanel-site"
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
  rm -rf -- "$ROOT/.p07-private-site"
  echo P07_D05_SITE_VMS_PRIVATE_SOURCE_CLEANED=YES
}
trap cleanup EXIT
ssh_vm() {
  local ip="$1"; shift
  ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="$WORK/known_hosts" -o ConnectTimeout=9 root@"$ip" "$@"
}
test "$(git -C "$ROOT/.p07-private-site" rev-parse HEAD)" = 0eac0ba1aa1c72a8d4f3282c9f14cdcba64b1625
test -c /dev/kvm && sudo test -w /dev/kvm
test -c /dev/net/tun || { echo P07_D05_SITE_TUN_UNAVAILABLE; exit 61; }
sudo apt-get update -qq >/dev/null
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq qemu-system-x86 qemu-utils cloud-image-utils iproute2 iptables openssh-client rsync >/dev/null
echo P07_D05_SITE_KVM_QEMU=PASS
cd "$WORK"
BASE="https://cdimage.debian.org/images/cloud/trixie/latest"
IMAGE="debian-13-generic-amd64.qcow2"
curl --retry 2 --connect-timeout 20 --max-time 180 -fsSLo SHA512SUMS "$BASE/SHA512SUMS"
curl --retry 2 --connect-timeout 20 --max-time 360 -fsSLo "$IMAGE" "$BASE/$IMAGE"
grep -E "[[:space:]](\*|)$IMAGE$" SHA512SUMS > image.sha512
test -s image.sha512
sha512sum -c image.sha512 >/dev/null
echo P07_D05_SITE_OFFICIAL_DEBIAN13_IMAGE_VERIFIED=PASS
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
  if test "$ready" != true; then echo P07_D05_SITE_CLOUD_VM_SSH=FAILED; exit 62; fi
  ssh_vm "$ip" 'cloud-init status --wait' >/dev/null
  echo P07_D05_SITE_NATIVE_DEBIAN13_SSH=PASS
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
  echo P07_D05_SITE_UNSUPPORTED_FIXTURE_ENGINE >&2
  exit 79
fi
INSTALL
  echo "P07_D05_SITE_${engine_role}=PASS"
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
print('P07_D05_SITE_CP_DATABASE_SERVER_INITIALIZED=PASS')
PY
INITIALIZE
done
ssh_vm "$OLD" 'bash -se' <<'SOURCE'
set -Eeuo pipefail
stage=INITIAL
report_source_fixture_error() {
  rc=$?
  echo "P07_D05_SITE_SOURCE_FIXTURE_FAILED_AT=$stage RC=$rc"
  if test -f /root/p07-create.log; then
    tail -n 9 /root/p07-create.log | sed -E 's/(Password=)[^[:space:]]+/\1[REDACTED]/Ig' | cut -c 1-260
  fi
  if test -f /root/p07-db-add.log; then
    tail -n 12 /root/p07-db-add.log | sed -E 's/(Password=)[^[:space:]]+/\1[REDACTED]/Ig' | cut -c 1-260
  fi
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
printf '<?php echo "P07_ALPHA_WEB_42"; ?>\n' > /home/p07alpha/htdocs/alpha.p07.example.com/public/index.php
printf '<?php echo "P07_ALPHA_WEB_42"; ?>\n' > /home/p07alpha/htdocs/alpha.p07.example.com/index.php
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
if curl -ksS --resolve alpha.p07.example.com:443:127.0.0.1 https://alpha.p07.example.com/ | grep -Fq P07_ALPHA_WEB_42; then
  echo P07_D05_SITE_SOURCE_PHP_HTTPS=PASS
else
  echo P07_D05_SITE_SOURCE_PHP_HTTPS=NOT_PROVEN
fi
if curl -ksS --resolve beta.p07.example.com:443:127.0.0.1 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_23; then
  echo P07_D05_SITE_SOURCE_STATIC_HTTP=PASS
else
  echo P07_D05_SITE_SOURCE_STATIC_HTTP=NOT_PROVEN
fi
SOURCE
echo P07_D05_SITE_OLD_TWO_SITES_SQL_SQLITE_EXTERNAL_HTTP=PASS

# Report only synthetic VM engine/server identity; no credentials or SQL.

# The source and target databases are on ONE isolated CloudPanel VM:
# source native CloudPanel database + second native DB in a localhost-only container.
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$WORK/known_hosts" \
  "$ROOT/.p07-private-site/lib/db_engine_conversion_site_sandbox.py" \
  root@"$OLD":/root/db_engine_conversion_site_sandbox.py

ssh_vm "$OLD" "P07_D05_SOURCE_ENGINE=$P07_D05_SOURCE_ENGINE bash -se" <<'SYNTHETIC_SITE'
set -Eeuo pipefail
stage=INITIAL
on_failure() { rc=$?; echo "P07_D05_SITE_FAILED_AT=$stage RC=$rc"; exit "$rc"; }
trap on_failure ERR
app=/home/p07alpha/htdocs/alpha.p07.example.com
test -f "$app/.env"
printf 'P07_D05_EPHEMERAL_CLOUDPANEL_VM_ONLY\n' >/root/.p07-d05-synthetic-qemu
chmod 600 /root/.p07-d05-synthetic-qemu
stage=DOCKER_INSTALL
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/root/p07-d05-docker-apt.log 2>&1
apt-get install -y -qq docker.io >/root/p07-d05-docker-install.log 2>&1
systemctl start docker
docker info >/dev/null
stage=TARGET_ENGINE
if test "$P07_D05_SOURCE_ENGINE" = MYSQL_8.4; then
  target_image=mariadb:11.8
  target_cli=mariadb
  target_env=MARIADB_ROOT_PASSWORD
  target_expected=11.8
else
  target_image=mysql:8.4
  target_cli=mysql
  target_env=MYSQL_ROOT_PASSWORD
  target_expected=8.4
fi
syspass='P07_PUBLIC_SYNTHETIC_FIXED_2026'
docker run -d --name p07-d05-target \
  --label p07-d05.synthetic=YES \
  -p 127.0.0.1:13307:3306 \
  -e "$target_env=$syspass" "$target_image" >/root/p07-d05-container.id
ready=0
for i in $(seq 1 85); do
  if docker exec -e "MYSQL_PWD=$syspass" p07-d05-target \
      "$target_cli" -uroot -e 'SELECT 1' >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 2
done
test "$ready" -eq 1
docker exec -e "MYSQL_PWD=$syspass" p07-d05-target \
  "$target_cli" -uroot --batch --skip-column-names -e 'SELECT @@version' | grep -E "^$target_expected[.]"
echo P07_D05_SITE_TARGET_NATIVE_ENGINE=PASS

stage=SOURCE_APP
cat >"$app/db-switch.php" <<'PHP'
<?php
$path = is_file(__DIR__.'/.env') ? __DIR__.'/.env' : dirname(__DIR__).'/.env';
$env = parse_ini_file($path, false, INI_SCANNER_RAW);
if (!is_array($env) || ($env['DB_HOST'] ?? '') !== '127.0.0.1') {
    http_response_code(503); exit;
}
$port = (int)($env['DB_PORT'] ?? 0);
if (!in_array($port, [3306,13307,13308], true)) {
    http_response_code(503); exit;
}
try {
    mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
    $db = new mysqli('127.0.0.1', (string)$env['DB_USERNAME'],
        trim((string)$env['DB_PASSWORD'], "'\""),
        (string)$env['DB_DATABASE'], $port);
    if (isset($_GET['write'])) {
        if ($port !== 13307) { http_response_code(503); exit; }
        $db->query("INSERT INTO p07_marker (id,marker) VALUES (2,'TARGET_ONLY_WRITE')");
    }
    $result = $db->query('SELECT COUNT(*) AS c FROM p07_marker WHERE id=2');
    $row = $result->fetch_assoc();
    $num = (int)($row['c'] ?? -1);
    if ($num < 0 || $num > 1) { http_response_code(503); exit; }
    header('Content-Type: text/plain; charset=utf-8');
    echo 'P07_CP_SITE_'.($port === 3306 ? 'SOURCE' : 'TARGET').'_ROW2_'.$num;
} catch (Throwable $e) {
    http_response_code(503);
}
PHP
cp "$app/db-switch.php" "$app/public/db-switch.php"
chown p07alpha:p07alpha "$app/db-switch.php" "$app/public/db-switch.php"
curl -kfsS --noproxy '*' --resolve alpha.p07.example.com:443:127.0.0.1 \
  https://alpha.p07.example.com/db-switch.php |
    grep -Fxq P07_CP_SITE_SOURCE_ROW2_0
echo P07_D05_SITE_CLOUDPANEL_PHP_SOURCE=PASS

stage=DUMP_SOURCE
clpctl db:export --databaseName=p07alpha --file=/root/p07-d05-source.sql \
  >/root/p07-d05-dump.log 2>&1
test -s /root/p07-d05-source.sql
python3 - <<'PY'
from pathlib import Path
import re
p=Path('/root/p07-d05-source.sql')
data=p.read_bytes()
header, sep, rest=data.partition(b'\n')
if header.startswith(b'/*M!999999'):
    if not sep or not re.fullmatch(
        rb'/\*M!999999\\- enable the sandbox mode \*/;?[ \t\r]*',header
    ):
        raise SystemExit('P07_D05_UNKNOWN_SANDBOX_HEADER=BLOCKED')
    p.write_bytes(rest)
d=p.read_bytes()
if not d or not re.search(rb'CREATE TABLE [\x60]?p07_marker',d):
    raise SystemExit('P07_D05_SYNTHETIC_DUMP_INCOMPLETE=BLOCKED')
if re.search(rb'(?im)^\s*(CREATE USER|GRANT |REVOKE |DROP DATABASE|SET GLOBAL)',d):
    raise SystemExit('P07_D05_SYNTHETIC_SQL_CONTROL=BLOCKED')
PY
stage=TARGET_IMPORT
docker exec -e "MYSQL_PWD=$syspass" p07-d05-target "$target_cli" \
  -uroot -e 'CREATE DATABASE p07alpha CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
docker exec -i -e "MYSQL_PWD=$syspass" p07-d05-target \
  "$target_cli" -uroot p07alpha </root/p07-d05-source.sql
docker exec -e "MYSQL_PWD=$syspass" p07-d05-target "$target_cli" \
 -uroot -e \
 "CREATE USER 'p07alphauser'@'%' IDENTIFIED BY 'SyntheticOnly2026ABC!'; GRANT SELECT, INSERT ON p07alpha.* TO 'p07alphauser'@'%';"
test "$(docker exec -e "MYSQL_PWD=$syspass" p07-d05-target "$target_cli" \
 -uroot p07alpha --batch --skip-column-names \
 -e 'SELECT marker FROM p07_marker WHERE id=1')" = SYNTHETIC_MIGRATE_42
echo P07_D05_SITE_TARGET_IMPORT_USER=PASS
stage=SWITCH_WRITE_ROLLBACK
export P07_ALLOW_SYNTHETIC_D05=1
python3 - <<'PY'
import sys
sys.path.insert(0,'/root')
from db_engine_conversion_site_sandbox import inspect_cloudpanel_fixture_site
p=inspect_cloudpanel_fixture_site()
assert p["status"]=="SYNTHETIC_APP_SWITCH_READ_WRITE_PROVEN",p["status"]
assert p["site_config_restored_byte_exact"]
assert p["target_app_read_write_proven"]
assert p["cloudpanel_active_switch"]=="NOT_RUN"
assert not p["business_conversion_enabled"]
print('P07_D05_SITE_REAL_APP_TARGET_READ_WRITE_ROLLBACK=PASS')
PY
stage=FAULT_ROLLBACK
python3 - <<'PY'
import sys
sys.path.insert(0,'/root')
from db_engine_conversion_site_sandbox import inspect_cloudpanel_fixture_site
for fault,code in (
    ('after-target-probe','FAIL_CLOSED_D05_SITE_INJECTED_AFTER_CONFIG'),
    ('bad-target','FAIL_CLOSED_D05_SITE_HTTP_UNVERIFIED')
):
    p=inspect_cloudpanel_fixture_site(inject=fault)
    assert p["status"]==code,p["status"]
    assert p["site_config_restored_byte_exact"]
    assert not p["target_app_read_write_proven"]
print('P07_D05_SITE_BAD_ENDPOINT_AND_INJECTION_ROLLBACK=PASS')
PY
stage=VERIFY_SOURCE_AND_CP
test "$(grep -c '^DB_PORT=3306$' "$app/.env")" -eq 1
curl -kfsS --noproxy '*' --resolve alpha.p07.example.com:443:127.0.0.1 \
  https://alpha.p07.example.com/db-switch.php |
  grep -Fxq P07_CP_SITE_SOURCE_ROW2_0
docker exec -e "MYSQL_PWD=$syspass" p07-d05-target "$target_cli" \
  -uroot p07alpha --batch --skip-column-names \
  -e 'SELECT COUNT(*) FROM p07_marker WHERE id=2' | grep -Fxq 1
python3 - <<'PY'
import sqlite3
p='/home/clp/htdocs/app/data/db.sq3'
with sqlite3.connect('file:'+p+'?mode=ro',uri=True) as c:
    n=c.execute('SELECT COUNT(*) FROM database_server WHERE is_active=1').fetchone()[0]
assert n==1
print('P07_D05_SITE_CLOUDPANEL_ACTIVE_NOT_SWITCHED=TRUE')
PY
echo P07_D05_SITE_SOURCE_CONTINUITY=PASS
echo P07_D05_CLOUDPANEL_ACTIVE_SWITCH=NOT_PROVEN
echo P07_D05_OWNER_VPS_DNS_TOUCHED=NO
SYNTHETIC_SITE
echo P07_D05_CLOUDPANEL_SYNTHETIC_SITE_SWITCH_PHASE=PASS
