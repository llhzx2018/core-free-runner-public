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
  for vm in old; do
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
test "$(git -C "$ROOT/.p07-private-exact" rev-parse HEAD)" = fc346593199b98198819a609103d774f3145e7e9
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
  if test "$ready" != true; then echo P07_M03_D04_CLOUD_VM_SSH=FAILED; exit 62; fi
  ssh_vm "$ip" 'cloud-init status --wait' >/dev/null
  echo P07_M03_D04_NATIVE_DEBIAN13_SSH=PASS
done
for ip in "$OLD"; do
  ssh_vm "$ip" 'bash -se' <<'INSTALL'
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/root/p07-apt.log 2>&1
apt-get install -y -qq curl wget sudo rsync sqlite3 cron python3 >>/root/p07-apt.log 2>&1
curl -fsSL --connect-timeout 20 --max-time 120 https://installer.cloudpanel.io/ce/v2/install.sh -o /root/p07-installer.sh
echo '8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476  /root/p07-installer.sh' | sha256sum -c >/dev/null
timeout --signal=TERM --kill-after=20s 1200s env DB_ENGINE=MARIADB_11.8 bash /root/p07-installer.sh >/root/p07-cloudpanel.log 2>&1
clpctl --version >/dev/null
test -f /home/clp/htdocs/app/data/db.sq3
INSTALL
  echo P07_M03_D04_OFFICIAL_CLOUDPANEL_MARIADB_11_8=PASS
done

ssh_vm "$OLD" 'bash -se' <<'DIAG'
set -u
export DEBIAN_FRONTEND=noninteractive
echo P07_M03_D04_DATABASE_FIXTURE_DIAG_BEGIN=YES
db_os_status="$(systemctl is-active mariadb 2>/dev/null || systemctl is-active mysql 2>/dev/null || true)"
echo "P07_M03_D04_MARIADB_SERVICE=$db_os_status"
if mariadb --batch --skip-column-names -e 'SELECT VERSION()' >/dev/null 2>&1; then
  echo P07_M03_D04_ROOT_SOCKET_SQL=PASS
else
  echo P07_M03_D04_ROOT_SOCKET_SQL=UNAVAILABLE
fi
if clpctl db:show:master-credentials >/dev/null 2>&1; then
  echo P07_M03_D04_CLOUDPANEL_MASTER_CREDENTIALS=AVAILABLE
else
  echo P07_M03_D04_CLOUDPANEL_MASTER_CREDENTIALS=UNAVAILABLE
fi
if test -f /home/clp/htdocs/app/data/db.sq3; then
  table_count="$(sqlite3 /home/clp/htdocs/app/data/db.sq3 "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='database_server';" 2>/dev/null || true)"
  echo "P07_M03_D04_CP_DATABASE_SERVER_TABLE_COUNT=$table_count"
  if test "$table_count" = 1; then
    server_count="$(sqlite3 /home/clp/htdocs/app/data/db.sq3 "SELECT COUNT(*) FROM database_server;" 2>/dev/null || true)"
    echo "P07_M03_D04_CP_REGISTERED_DB_SERVERS=$server_count"
  fi
fi
echo P07_M03_D04_CLOUDPANEL_INITIAL_BROWSER_PAGE=START
if curl -kfsSL --connect-timeout 8 --max-time 45 --max-redirs 5 \
  https://127.0.0.1:8443/ -o /root/p07-initial-page.html >/dev/null 2>&1; then
  echo P07_M03_D04_CLOUDPANEL_INITIAL_BROWSER_PAGE=FETCHED
else
  echo P07_M03_D04_CLOUDPANEL_INITIAL_BROWSER_PAGE=HTTP_FAILED
fi
if test "$table_count" = 1; then
  server_count="$(sqlite3 /home/clp/htdocs/app/data/db.sq3 "SELECT COUNT(*) FROM database_server;" 2>/dev/null || true)"
  echo "P07_M03_D04_CP_DB_SERVERS_AFTER_FIRST_HTTPS_GET=$server_count"
fi
if clpctl user:list >/dev/null 2>&1; then
  echo P07_M03_D04_CP_ADMIN_INTERFACE=WORKING
else
  echo P07_M03_D04_CP_ADMIN_INTERFACE=NOT_READY
fi
if clpctl site:add:php --domainName=diag.p07.example.com --phpVersion=8.4 --vhostTemplate=Generic \
  --siteUser=p07diag --siteUserPassword='SyntheticOnly2026ABC!' > /root/p07-create-site.log 2>&1; then
  echo P07_M03_D04_CP_PHP_SITE=PASS
else
  echo P07_M03_D04_CP_PHP_SITE=FAIL
fi
echo P07_M03_D04_TEST_BEFORE_ADMIN=START
if clpctl db:add --domainName=diag.p07.example.com --databaseName=p07_diag_before \
  --databaseUserName=p07_diag_before --databaseUserPassword='SyntheticOnly2026ABC!' \
  > /root/p07-db-before.log 2>&1; then
  echo P07_M03_D04_TEST_BEFORE_ADMIN=PASS
else
  echo P07_M03_D04_TEST_BEFORE_ADMIN=FAIL
fi
echo "P07_M03_D04_BEFORE_DB_CLI_OUTPUT_BYTES=$(wc -c < /root/p07-db-before.log)"
if clpctl user:add --userName=p07testadmin --email=p07testadmin@example.com \
  --firstName=P07 --lastName=Fixture --password='SyntheticOnly2026ABC!' \
  --role=admin --timezone=UTC --status=1 \
  >/root/p07-add-admin.log 2>&1; then
  echo P07_M03_D04_CP_FIRST_ADMIN_CREATE=PASS
else
  echo P07_M03_D04_CP_FIRST_ADMIN_CREATE=FAIL
fi
echo P07_M03_D04_CLOUDPANEL_ADMIN_WEB_PAGE=START
if curl -kfsSL --connect-timeout 8 --max-time 45 --max-redirs 5 \
  https://127.0.0.1:8443/ -o /root/p07-after-admin.html >/dev/null 2>&1; then
  echo P07_M03_D04_CLOUDPANEL_ADMIN_WEB_PAGE=FETCHED
else
  echo P07_M03_D04_CLOUDPANEL_ADMIN_WEB_PAGE=HTTP_FAILED
fi
if test "$table_count" = 1; then
  server_count="$(sqlite3 /home/clp/htdocs/app/data/db.sq3 "SELECT COUNT(*) FROM database_server;" 2>/dev/null || true)"
  echo "P07_M03_D04_CP_DB_SERVERS_AFTER_ADMIN_AND_HTTPS=$server_count"
fi
echo P07_M03_D04_TEST_AFTER_ADMIN=START
if clpctl db:add --domainName=diag.p07.example.com --databaseName=p07_diag_after \
  --databaseUserName=p07_diag_after --databaseUserPassword='SyntheticOnly2026ABC!' \
  > /root/p07-db-after.log 2>&1; then
  echo P07_M03_D04_TEST_AFTER_ADMIN=PASS
else
  echo P07_M03_D04_TEST_AFTER_ADMIN=FAIL
fi
echo "P07_M03_D04_AFTER_DB_CLI_OUTPUT_BYTES=$(wc -c < /root/p07-db-after.log)"
if mariadb --batch --skip-column-names -e 'SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME LIKE "p07_diag_%"' >/root/p07-sql-schemas.txt 2>/dev/null; then
  echo "P07_M03_D04_ACTUAL_SQL_SCHEMAS=$(wc -l < /root/p07-sql-schemas.txt)"
else
  echo P07_M03_D04_ACTUAL_SQL_SCHEMAS=UNVERIFIED
fi
if clpctl db:show:master-credentials >/dev/null 2>&1; then
  echo P07_M03_D04_CLOUDPANEL_MASTER_POST_INIT=AVAILABLE
else
  echo P07_M03_D04_CLOUDPANEL_MASTER_POST_INIT=UNAVAILABLE
fi
echo P07_M03_D04_DIAGNOSTIC_COMPLETE=YES
DIAG
echo P07_M03_D04_SINGLE_VM_DB_DIAGNOSTIC=COMPLETE
