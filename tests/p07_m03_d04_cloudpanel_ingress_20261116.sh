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
test "$(git -C "$ROOT/.p07-private-exact" rev-parse HEAD)" = c7e70337c4632bd1e147c8665998e113df00588d
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
# Neither production VPS nor its DNS is contacted. Two disposable CP VMs
# are created by the archived proven fixture; source-only synthetic actions.
ssh_vm "$OLD" 'mkdir -p /opt/vf-server-ops'
rsync -aq -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$WORK/known_hosts" \
  "$ROOT/.p07-private-exact/bin" "$ROOT/.p07-private-exact/lib" \
  "$ROOT/.p07-private-exact/VERSION" "$ROOT/.p07-private-exact/BUILD_ID" \
  root@"$OLD":/opt/vf-server-ops/
ssh_vm "$OLD" 'bash -se' <<'VERIFY_CP'
set -Eeuo pipefail
P07_ROOT=/opt/vf-server-ops
export PYTHONPATH="$P07_ROOT/lib"
P07_RUN="python3 -B $P07_ROOT/lib/server_migration_pull.py"
OLD_SITE=beta.p07.example.com
KEEP_SITE=alpha.p07.example.com
stat -c 'P07_CLOUDPANEL_SOURCE_VHOST_FILE_TYPE=%F' "/etc/nginx/sites-enabled/$OLD_SITE.conf" | cut -c 1-120
source_status="$(curl -kfsS --noproxy '*' --resolve "$OLD_SITE:443:127.0.0.1" "https://$OLD_SITE/")"
test "$source_status" = P07_BETA_STATIC_23
keep_status="$(curl -kfsS --noproxy '*' --resolve "$KEEP_SITE:443:127.0.0.1" "https://$KEEP_SITE/")"
printf '%s' "$keep_status" | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
old_hash="$(sha256sum /etc/nginx/sites-enabled/"$OLD_SITE".conf | awk '{print $1}')"
other_hash="$(sha256sum /etc/nginx/sites-enabled/"$KEEP_SITE".conf | awk '{print $1}')"
stage=SOURCE_PLAN
export P07_ROOT
python3 -B - <<'PY'
import os,sys
sys.path.insert(0,os.environ["P07_ROOT"]+"/lib")
import server_migration_pull as p
x=p.source_plan_local([])
assert x["status"]=="READY"
s=[z for z in x["sites"] if z["domain"]=="beta.p07.example.com"]
assert len(s)==1
print("P07_CP_INGRESS_SOURCE_RUNTIME_TYPE="+str(s[0]["runtime"]["type"])[:40])
print("P07_CP_INGRESS_SOURCE_USER_DISTINCT="+str(len(set(a["site_user"] for a in x["sites"]))==len(x["sites"])))
PY
stage=WRONG_CONFIRM
set +e
python3 -B "$P07_ROOT/lib/server_migration_pull.py" _source-static-ingress-apply \
  --migration-id pull-20261116T061500Z-3aa98bbb --domain "$OLD_SITE" --confirm WRONG \
  </dev/null >/root/p07-fence-wrong.json 2>/root/p07-fence-wrong.err
wrong_rc=$?
set -e
test "$wrong_rc" -eq 13
test "$(sha256sum /etc/nginx/sites-enabled/"$OLD_SITE".conf | awk '{print $1}')" = "$old_hash"
systemctl is-active --quiet nginx
echo P07_CP_INGRESS_WRONG_CONFIRM_NO_WRITE=PASS
stage=APPLY
set +e
python3 -B "$P07_ROOT/lib/server_migration_pull.py" _source-static-ingress-apply \
  --migration-id pull-20261116T061500Z-3aa98bbb --domain "$OLD_SITE" \
  --confirm "FENCE_STATIC_HTTP:pull-20261116T061500Z-3aa98bbb:$OLD_SITE" \
  </dev/null >/root/p07-fence-apply.json 2>/root/p07-fence-apply.err
apply_rc=$?
set -e
if test "$apply_rc" -ne 0; then
  # Don't echo arbitrary private stderr. Only stable machine-owned safe marker.
  echo "P07_CP_INGRESS_APPLY_FAILED_RC=$apply_rc"
  test "$(sha256sum /etc/nginx/sites-enabled/"$OLD_SITE".conf | awk '{print $1}')" = "$old_hash"
  systemctl is-active --quiet nginx
  curl -kfsS --noproxy '*' --resolve "$OLD_SITE:443:127.0.0.1" "https://$OLD_SITE/" | grep -Fq P07_BETA_STATIC_23
  curl -kfsS --noproxy '*' --resolve "$KEEP_SITE:443:127.0.0.1" "https://$KEEP_SITE/" | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
  echo P07_CP_INGRESS_FAILED_CLOSED_SOURCE_SITES_LIVE=PASS
  exit 73
fi
python3 -B - <<'PY'
import json
p=json.load(open("/root/p07-fence-apply.json"))
assert p["status"]=="FENCED_HTTP_ONLY_NOT_WRITER_FENCE"
assert p["cutover_allowed"] is False
print("P07_CP_INGRESS_APPLY_RECEIPT=PASS")
PY
stage=FENCE_READBACK
curl -ksS --noproxy '*' --resolve "$OLD_SITE:443:127.0.0.1" \
   -o /dev/null -w '%{http_code}' "https://$OLD_SITE/" | grep -x 503
curl -kfsS --noproxy '*' --resolve "$KEEP_SITE:443:127.0.0.1" "https://$KEEP_SITE/" | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
test "$(sha256sum /etc/nginx/sites-enabled/"$KEEP_SITE".conf | awk '{print $1}')" = "$other_hash"
systemctl is-active --quiet nginx
echo P07_CP_INGRESS_SELECTED_503_OTHER_PHP_DB_200=PASS
stage=RESTORE
python3 -B "$P07_ROOT/lib/server_migration_pull.py" _source-static-ingress-restore \
  --migration-id pull-20261116T061500Z-3aa98bbb --domain "$OLD_SITE" \
  --confirm "RESTORE_STATIC_HTTP:pull-20261116T061500Z-3aa98bbb:$OLD_SITE" \
  </dev/null >/root/p07-fence-restore.json 2>/root/p07-fence-restore.err
python3 -B - <<'PY'
import json
p=json.load(open("/root/p07-fence-restore.json"))
assert p["status"]=="RESTORED_HTTP_ONLY"
assert p["cutover_allowed"] is False
print("P07_CP_INGRESS_RESTORE_RECEIPT=PASS")
PY
test "$(sha256sum /etc/nginx/sites-enabled/"$OLD_SITE".conf | awk '{print $1}')" = "$old_hash"
test "$(sha256sum /etc/nginx/sites-enabled/"$KEEP_SITE".conf | awk '{print $1}')" = "$other_hash"
curl -kfsS --noproxy '*' --resolve "$OLD_SITE:443:127.0.0.1" "https://$OLD_SITE/" | grep -Fq P07_BETA_STATIC_23
curl -kfsS --noproxy '*' --resolve "$KEEP_SITE:443:127.0.0.1" "https://$KEEP_SITE/" | grep -Fq 'P07_ALPHA_WEB_42 P07_DB_READ_42'
systemctl is-active --quiet nginx
echo P07_CP_INGRESS_REAL_CLOUDPANEL_SOURCE_RESTORED=PASS
VERIFY_CP
echo P07_CP_INGRESS_TWO_DISPOSABLE_CLOUDPANEL_HOSTS=PASS
echo P07_CP_INGRESS_PRODUCTION_DNS_AND_OWNER_VPS=NOT_RUN
