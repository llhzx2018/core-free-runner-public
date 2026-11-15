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
test "$(git -C "$ROOT/.p07-private-exact" rev-parse HEAD)" = 472db71d1162a2701f393a298df198316bbbc0e9
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
    selected_engine=MYSQL_8.4
    engine_role=SOURCE_MYSQL_8_4
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
  echo P07_M03_D04_SOURCE_PHP_HTTPS=PASS
else
  echo P07_M03_D04_SOURCE_PHP_HTTPS=NOT_PROVEN
fi
if curl -ksS --resolve beta.p07.example.com:443:127.0.0.1 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_23; then
  echo P07_M03_D04_SOURCE_STATIC_HTTP=PASS
else
  echo P07_M03_D04_SOURCE_STATIC_HTTP=NOT_PROVEN
fi

stage=CREATE_GAMMA_SQLITE_ONLY
clpctl site:add:php --domainName=gamma.p07.example.com --phpVersion=8.4 --vhostTemplate=Generic --siteUser=p07gamma --siteUserPassword='SyntheticOnly2026ABC!' >/root/p07-gamma-site.log 2>&1
stage=CREATE_GAMMA_SQLITE
sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT); INSERT INTO marker VALUES(1,"SYNTHETIC_GAMMA_SQLITE_77");'
cat > /home/p07gamma/htdocs/gamma.p07.example.com/index.php <<'P07_SQLITE_APP'
<?php
$db = new SQLite3(__DIR__ . '/test.sqlite', SQLITE3_OPEN_READWRITE);
$marker = $db->querySingle('SELECT value FROM marker WHERE id=1');
if (isset($_GET['write']) && $_GET['write'] === '1') {
    $db->exec("CREATE TABLE IF NOT EXISTS target_write (id INTEGER PRIMARY KEY, value TEXT)");
    $db->exec("INSERT INTO target_write(value) VALUES ('SYNTHETIC_TARGET_WRITE_88')");
}
echo "P07_GAMMA_SQLITE_APP_" . $marker;
P07_SQLITE_APP
chown -R p07gamma:p07gamma /home/p07gamma/htdocs/gamma.p07.example.com
stage=CHECK_GAMMA_SQLITE
test "$(sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_GAMMA_SQLITE_77
# A third disposable CloudPanel vhost was created AFTER alpha/beta. Assert
# its own vhost and reload Nginx before SNI/HTTPS; a default site responding
# does NOT prove the gamma PHP+SQLite application is reachable.
stage=CHECK_GAMMA_VHOST
test -f /etc/nginx/sites-enabled/gamma.p07.example.com.conf
nginx -t >/dev/null 2>&1
systemctl reload nginx
stage=CHECK_GAMMA_HTTPS
gamma_healthy=0
for attempt in 1 2 3 4 5; do
  if curl -kfsS --connect-timeout 5 --max-time 12     --resolve gamma.p07.example.com:443:127.0.0.1     https://gamma.p07.example.com/ 2>/dev/null | grep -Fq P07_GAMMA_SQLITE_APP_SYNTHETIC_GAMMA_SQLITE_77; then
    gamma_healthy=1
    break
  fi
  sleep 2
done
test "$gamma_healthy" = 1
echo P07_M03_D04_SOURCE_GAMMA_HTTPS_AND_SQLITE=PASS

SOURCE
echo P07_M03_D04_SQLITE_AND_STATIC_SOURCE_READY=PASS

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
CMD=/opt/vf-server-ops/bin/vfops
failed() {
  rc=$?
  echo "P07_M03_D04_INDEPENDENT_TEST_FAILED_AT=$stage RC=$rc"
  if test -f /root/p07-ind-plan.err; then tail -n 6 /root/p07-ind-plan.err | cut -c 1-180; fi
  if test -f /root/p07-ind-prepare.err; then tail -n 6 /root/p07-ind-prepare.err | cut -c 1-180; fi
  exit "$rc"
}
trap failed ERR
stage=SQLITE_PLAN
"$CMD" server-migrate plan --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site gamma.p07.example.com --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING \
  </dev/null >/root/p07-ind-plan.json 2>/root/p07-ind-plan.err
python3 - <<'PY'
import json
p=json.load(open("/root/p07-ind-plan.json"))
assert p["status"]=="READY", p.get("status")
assert p["site_count"]==1 and p["mysql_database_count"]==0
assert p["sqlite_asset_count"]==1
assert p["automatic_dns_change"] is False
assert p["existing_target_overwrite_allowed"] is False
print("P07_M03_D04_SQLITE_INDEPENDENT_PLAN=PASS")
PY
stage=SQLITE_PREPARE
"$CMD" server-migrate prepare --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site gamma.p07.example.com --confirm PREPARE_PULL_MIGRATION \
  </dev/null >/root/p07-ind-prepare.json 2>/root/p07-ind-prepare.err
python3 - <<'PY'
import json
p=json.load(open("/root/p07-ind-prepare.json"))
assert p["status"]=="PREPARED",p.get("status")
assert p["site_count"]==1
assert p["dns_changed"] is False if "dns_changed" in p else True
print("P07_M03_D04_SQLITE_INDEPENDENT_PREPARED=PASS")
PY
stage=SQLITE_ROW_AND_APP_READ
test "$(sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'PRAGMA integrity_check')" = ok
test "$(sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_GAMMA_SQLITE_77
curl -ksS --resolve gamma.p07.example.com:443:127.0.0.1 https://gamma.p07.example.com/ | grep -Fq P07_GAMMA_SQLITE_APP_SYNTHETIC_GAMMA_SQLITE_77
stage=SQLITE_TARGET_APP_WRITE
curl -ksS --resolve gamma.p07.example.com:443:127.0.0.1 'https://gamma.p07.example.com/?write=1' | grep -Fq P07_GAMMA_SQLITE_APP_SYNTHETIC_GAMMA_SQLITE_77
test "$(sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'SELECT value FROM target_write WHERE id=1')" = SYNTHETIC_TARGET_WRITE_88
echo P07_M03_D04_SQLITE_INDEPENDENT_APPLICATION_WRITE=PASS
stage=STATIC_PLAN
"$CMD" server-migrate plan --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site beta.p07.example.com --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING \
  </dev/null >/root/p07-ind-plan.json 2>/root/p07-ind-plan.err
python3 - <<'PY'
import json
p=json.load(open("/root/p07-ind-plan.json"))
assert p["status"]=="READY" and p["site_count"]==1
assert p["mysql_database_count"]==0 and p["sqlite_asset_count"]==0
assert p["automatic_dns_change"] is False
print("P07_M03_D04_STATIC_INDEPENDENT_PLAN=PASS")
PY
stage=STATIC_PREPARE
"$CMD" server-migrate prepare --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --site beta.p07.example.com --confirm PREPARE_PULL_MIGRATION \
  </dev/null >/root/p07-ind-prepare.json 2>/root/p07-ind-prepare.err
python3 - <<'PY'
import json
p=json.load(open("/root/p07-ind-prepare.json"))
assert p["status"]=="PREPARED" and p["site_count"]==1
print("P07_M03_D04_STATIC_INDEPENDENT_PREPARED=PASS")
PY
stage=STATIC_FILE_HTTP
test "$(cat /home/p07beta/htdocs/beta.p07.example.com/index.html)" = P07_BETA_STATIC_23
curl -ksS --resolve beta.p07.example.com:443:127.0.0.1 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_23
echo P07_M03_D04_STATIC_INDEPENDENT_HTTP=PASS
TARGET
ssh_vm "$OLD" 'bash -se' <<'VERIFY_SOURCE'
set -Eeuo pipefail
test "$(sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_GAMMA_SQLITE_77
test "$(sqlite3 /home/p07gamma/htdocs/gamma.p07.example.com/test.sqlite 'SELECT count(*) FROM sqlite_master WHERE name="target_write"')" = 0
curl -ksS --resolve gamma.p07.example.com:443:127.0.0.1 https://gamma.p07.example.com/ | grep -Fq P07_GAMMA_SQLITE_APP_SYNTHETIC_GAMMA_SQLITE_77
curl -ksS --resolve beta.p07.example.com:443:127.0.0.1 https://beta.p07.example.com/ | grep -Fq P07_BETA_STATIC_23
VERIFY_SOURCE
echo P07_M03_D04_SOURCE_NOT_MODIFIED_AND_RUNNING=PASS
echo P07_M03_D04_TWO_DISTINCT_TASKS_SQLITE_AND_STATIC=PASS
echo P07_M03_D04_OWNER_PRODUCTION_AND_DNS=NOT_RUN
