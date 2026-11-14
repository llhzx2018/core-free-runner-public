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
    test -f "$WORK/$vm.pid" && sudo kill "$(cat "$WORK/$vm.pid")" 2>/dev/null || true
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
ssh_vm "$OLD" 'bash -se' <<'SOURCE'
set -Eeuo pipefail
clpctl site:add:static --domainName=alpha.p07.test --siteUser=p07alpha --siteUserPassword=SyntheticOnly2026ABC > /root/p07-create.log 2>&1
clpctl site:add:static --domainName=beta.p07.test --siteUser=p07beta --siteUserPassword=SyntheticOnly2026ABC >> /root/p07-create.log 2>&1
clpctl db:add --domainName=alpha.p07.test --databaseName=p07_alpha --databaseUserName=p07_alpha_user --databaseUserPassword=SyntheticOnly2026ABC >> /root/p07-create.log 2>&1
mariadb p07_alpha -e 'CREATE TABLE p07_marker (id INT PRIMARY KEY, marker VARCHAR(40)); INSERT INTO p07_marker VALUES(1,"SYNTHETIC_MIGRATE_42");'
printf 'P07_ALPHA_STATIC_42\n' > /home/p07alpha/htdocs/alpha.p07.test/index.html
printf 'P07_BETA_STATIC_23\n' > /home/p07beta/htdocs/beta.p07.test/index.html
sqlite3 /home/p07alpha/htdocs/alpha.p07.test/test.sqlite 'CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT); INSERT INTO marker VALUES(1,"SYNTHETIC_SQLITE_42");'
mkdir -p /home/p07alpha/.vf-data
printf 'P07_EXTERNAL_ASSET_42\n' > /home/p07alpha/.vf-data/proof.txt
test "$(mariadb -N p07_alpha -e 'SELECT marker FROM p07_marker WHERE id=1')" = SYNTHETIC_MIGRATE_42
test "$(sqlite3 /home/p07alpha/htdocs/alpha.p07.test/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_SQLITE_42
test "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: alpha.p07.test' http://127.0.0.1/)" = 200
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
ssh_vm "$NEW" 'bash -se' <<'TARGET'
set -Eeuo pipefail
CMD=/opt/vf-server-ops/bin/vfops
"$CMD" server-migrate plan --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --confirm-source-helper-staging ALLOW_SOURCE_HELPER_STAGING >/root/p07-plan.json 2>/root/p07-plan.err
python3 - <<'PY'
import json
p=json.load(open('/root/p07-plan.json'))
assert p['status']=='READY'
assert p['site_count']==2
assert p['mysql_database_count']==1
assert p['sqlite_asset_count']==1
assert p['source_scope_kind']=='ALL_SOURCE_SITES'
assert p['automatic_dns_change'] is False
assert p['existing_target_overwrite_allowed'] is False
print('P07_M03_D04_REAL_ALL_SITES_PLAN=PASS')
PY
"$CMD" server-migrate prepare --source-ip 172.29.71.11 --identity-file /root/.ssh/p07_test_key \
  --confirm PREPARE_PULL_MIGRATION >/root/p07-prepare.json 2>/root/p07-prepare.err
python3 - <<'PY'
import json
p=json.load(open('/root/p07-prepare.json'))
assert p['status']=='PREPARED'
assert p['site_count']==2
print('P07_M03_D04_REAL_TARGET_PREPARED=PASS')
PY
test "$(cat /home/p07alpha/htdocs/alpha.p07.test/index.html)" = P07_ALPHA_STATIC_42
test "$(cat /home/p07beta/htdocs/beta.p07.test/index.html)" = P07_BETA_STATIC_23
test "$(sqlite3 /home/p07alpha/htdocs/alpha.p07.test/test.sqlite 'SELECT value FROM marker WHERE id=1')" = SYNTHETIC_SQLITE_42
test "$(mariadb -N p07_alpha -e 'SELECT marker FROM p07_marker WHERE id=1')" = SYNTHETIC_MIGRATE_42
test "$(cat /home/p07alpha/.vf-data/proof.txt)" = P07_EXTERNAL_ASSET_42
test "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: alpha.p07.test' http://127.0.0.1/)" = 200
echo P07_M03_D04_TARGET_HTTP_FILES_SQL_SQLITE_PRIVATE=PASS
TARGET
ssh_vm "$OLD" 'bash -se' <<'VERIFY'
set -Eeuo pipefail
test "$(mariadb -N p07_alpha -e 'SELECT marker FROM p07_marker WHERE id=1')" = SYNTHETIC_MIGRATE_42
test "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: alpha.p07.test' http://127.0.0.1/)" = 200
VERIFY
echo P07_M03_D04_SOURCE_CONTINUES_OPERATING=PASS
echo P07_M03_D04_DNS_CUTOVER=NOT_RUN
echo P07_M03_D04_ISOLATED_TWO_REAL_CLOUDPANEL_HOSTS=PASS
