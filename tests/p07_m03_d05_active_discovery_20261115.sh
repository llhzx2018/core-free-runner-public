#!/usr/bin/env bash
# P07-M03-D04 服务器迁移: isolated Debian13 x2; synthetic business data only.
set -Eeuo pipefail
case "$P07_D05_SOURCE_ENGINE" in
  MYSQL_8.4|MARIADB_11.8) ;;
  *) echo P07_D05_SOURCE_ENGINE_UNSUPPORTED; exit 77 ;;
esac
umask 077
ROOT="$(pwd)"
WORK="$RUNNER_TEMP/p07-d05-cloudpanel-active"
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
  echo P07_D05_ACTIVE_VMS_PRIVATE_SOURCE_CLEANED=YES
}
trap cleanup EXIT
ssh_vm() {
  local ip="$1"; shift
  ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile="$WORK/known_hosts" -o ConnectTimeout=9 root@"$ip" "$@"
}
test "$(git -C "$ROOT/.p07-private-d05active" rev-parse HEAD)" = ee48366a31dfe9a08dd75cf563cbada4b288432f
test -c /dev/kvm && sudo test -w /dev/kvm
test -c /dev/net/tun || { echo P07_D05_ACTIVE_TUN_UNAVAILABLE; exit 61; }
sudo apt-get update -qq >/dev/null
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq qemu-system-x86 qemu-utils cloud-image-utils iproute2 iptables openssh-client rsync >/dev/null
echo P07_D05_ACTIVE_KVM_QEMU=PASS
cd "$WORK"
BASE="https://cdimage.debian.org/images/cloud/trixie/latest"
IMAGE="debian-13-generic-amd64.qcow2"
curl --retry 2 --connect-timeout 20 --max-time 180 -fsSLo SHA512SUMS "$BASE/SHA512SUMS"
curl --retry 2 --connect-timeout 20 --max-time 360 -fsSLo "$IMAGE" "$BASE/$IMAGE"
grep -E "[[:space:]](\*|)$IMAGE$" SHA512SUMS > image.sha512
test -s image.sha512
sha512sum -c image.sha512 >/dev/null
echo P07_D05_ACTIVE_OFFICIAL_DEBIAN13_IMAGE_VERIFIED=PASS
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
  if test "$ready" != true; then echo P07_D05_ACTIVE_CLOUD_VM_SSH=FAILED; exit 62; fi
  ssh_vm "$ip" 'cloud-init status --wait' >/dev/null
  echo P07_D05_ACTIVE_NATIVE_DEBIAN13_SSH=PASS
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
  echo P07_D05_ACTIVE_UNSUPPORTED_FIXTURE_ENGINE >&2
  exit 79
fi
INSTALL
  echo "P07_D05_ACTIVE_${engine_role}=PASS"
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
print('P07_D05_ACTIVE_CP_DATABASE_SERVER_INITIALIZED=PASS')
PY
INITIALIZE
done

# Exact installed CloudPanel binary/version and its official admin router:
# No registration, credentials or SQL is changed in this first inspection.
ssh_vm "$OLD" 'bash -se' <<'CONTROL_PLANE_DISCOVERY'
set -Eeuo pipefail
root=/home/clp/htdocs/app
test -f "$root/data/db.sq3"
echo P07_D05_ACTIVE_CLOUDPANEL_NATIVE_INSTALL=PASS
python3 - <<'PY'
from pathlib import Path
import sqlite3
p=Path('/home/clp/htdocs/app/data/db.sq3')
with sqlite3.connect(f'file:{p}?mode=ro', uri=True) as c:
    names=[row[0] for row in c.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%database%' ORDER BY name"
    )]
    assert 'database_server' in names
    columns=[x[1] for x in c.execute("PRAGMA table_info(database_server)")]
    expected={'id','host','port','is_active'}
    assert expected.issubset(columns), 'DATABASE_SERVER_SCHEMA_CHANGED'
    total=c.execute("SELECT COUNT(*) FROM database_server").fetchone()[0]
    active=c.execute("SELECT COUNT(*) FROM database_server WHERE is_active=1").fetchone()[0]
    assert total>=1 and active==1
    print("P07_D05_ACTIVE_PANEL_DATABASE_SERVER_SCHEMA=PASS")
    print("P07_D05_ACTIVE_DEFAULT_SERVER_COUNT_VALID=PASS")
    print("P07_D05_ACTIVE_DATABASE_SERVER_COLUMN_NAMES="+",".join(sorted(columns)))
PY
root=/home/clp/htdocs/app
if test -f "$root/bin/console"; then
  cd "$root"
  if php bin/console debug:router --format=json >/root/p07-d05-routes.json 2>/root/p07-d05-console.err; then
    python3 - <<'PY'
import json
from pathlib import Path
data=json.loads(Path('/root/p07-d05-routes.json').read_text())
routes=[]
for name,props in data.items():
    path=props.get('path','')
    if 'database' in (name+' '+path).lower() or 'login' in (name+' '+path).lower() or 'setting' in (name+' '+path).lower():
        routes.append((name,path,props.get('methods',[])))
for name,path,methods in routes[:60]:
    print("P07_D05_ACTIVE_OFFICIAL_ROUTE="+name+" "+path+" "+str(methods))
print("P07_D05_ACTIVE_OFFICIAL_ROUTE_DISCOVERY=PASS")
PY
  else
    echo P07_D05_ACTIVE_OFFICIAL_ROUTE_DISCOVERY=CLI_NOT_AVAILABLE
  fi
else
  echo P07_D05_ACTIVE_OFFICIAL_ROUTE_DISCOVERY=NO_CONSOLE
fi
python3 - <<'PY'
import ssl,urllib.request,html.parser
class Inputs(html.parser.HTMLParser):
 def __init__(self): super().__init__(); self.names=[]
 def handle_starttag(self,t,a):
  if t=='input':
   d=dict(a)
   self.names.append((d.get('name',''),d.get('type','')))
for path in ('/login','/admin/login'):
 try:
  req=urllib.request.Request('https://127.0.0.1:8443'+path)
  with urllib.request.urlopen(req,context=ssl._create_unverified_context(),timeout=12) as response:
   data=response.read(150000).decode('utf8','replace')
   p=Inputs();p.feed(data)
   clean=[n+':'+t for n,t in p.names if n and t!='password'][:15]
   print('P07_D05_ACTIVE_LOGIN_FORM_ROUTE='+path)
   print('P07_D05_ACTIVE_LOGIN_FIELDS='+','.join(clean))
 except Exception:
  print('P07_D05_ACTIVE_LOGIN_FORM_ROUTE_UNVERIFIED='+path)
PY
echo P07_D05_ACTIVE_REAL_CLOUDPANEL_CONTROL_PLANE_DISCOVERY=PASS
CONTROL_PLANE_DISCOVERY


# Bounded second gate: official authenticated Admin form only on synthetic CP VM.
scp -q -i "$KEY" -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$WORK/known_hosts" \
  "$ROOT/.p07-private-d05active/lib/db_engine_conversion_cloudpanel_active.py" \
  root@"$OLD":/root/db_engine_conversion_cloudpanel_active.py

ssh_vm "$OLD" "P07_D05_SOURCE_ENGINE=$P07_D05_SOURCE_ENGINE bash -se" <<'CP_UI_LAB'
set -Eeuo pipefail
stage=PREPARE
error() { rc=$?; echo "P07_D05_ACTIVE_UI_FAILED_AT=$stage RC=$rc"; exit "$rc"; }
trap error ERR
printf 'P07_D05_EPHEMERAL_CLOUDPANEL_VM_ONLY\n' >/root/.p07-d05-synthetic-qemu
chmod 0600 /root/.p07-d05-synthetic-qemu
stage=SOURCE_CP_INSTANCE
test -f /home/clp/htdocs/app/data/db.sq3
echo P07_D05_ACTIVE_SOURCE_PANEL_ONLY=PASS
stage=TARGET_ENGINE_PROVISION
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/root/p07-d05-target-apt.log 2>&1
apt-get install -y -qq docker.io >/root/p07-d05-target-docker.log 2>&1
systemctl start docker
docker info >/dev/null
if test "$P07_D05_SOURCE_ENGINE" = MYSQL_8.4; then
  target_image=mariadb:11.8
  target_cli=mariadb
  target_pw_var=MARIADB_ROOT_PASSWORD
  target_ver='11.8.'
else
  target_image=mysql:8.4
  target_cli=mysql
  target_pw_var=MYSQL_ROOT_PASSWORD
  target_ver='8.4.'
fi
pw='P07_Synthetic_D05_Root_Only!'
docker run -d --name p07-d05-active-target \
  --label 'org.kewaro.p07.d05.active=synthetic' \
  -p 127.0.0.1:13307:3306 \
  -e "$target_pw_var=$pw" "$target_image" \
  >/root/p07-d05-target-container.id
ready=0
for n in $(seq 1 90); do
 if docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target \
    "$target_cli" -uroot -e 'SELECT 1' >/dev/null 2>&1; then
    ready=1; break
 fi
 sleep 2
done
test "$ready" -eq 1
docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target "$target_cli" \
  -uroot --batch --skip-column-names -e 'SELECT @@version' | grep -Fq "$target_ver"
docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target "$target_cli" \
 -uroot -e \
 "CREATE USER 'p07d05admin'@'%' IDENTIFIED BY 'P07_Synthetic_D05_Control_Only!'; GRANT ALL PRIVILEGES ON *.* TO 'p07d05admin'@'%' WITH GRANT OPTION;"
echo P07_D05_ACTIVE_ISOLATED_TARGET_ENGINE=PASS
stage=READ_ONLY_METADATA_GUARD
python3 - <<'PY'
import sys
sys.path.insert(0,'/root')
from db_engine_conversion_cloudpanel_active import inspect_cloudpanel_active
r=inspect_cloudpanel_active(target_port=13307)
assert r["server_count"]==1
assert not r["target_server_port_registered"]
assert not r["active_switch_proven"]
assert not r["writes_performed"]
print('P07_D05_ACTIVE_PRODUCT_READONLY_CP_SCHEMA=PASS')
PY
stage=BROWSER_READY
echo P07_D05_ACTIVE_BROWSER_FIXTURE_READY=PASS
CP_UI_LAB
stage=REAL_BROWSER_UI
python3 -m venv "$WORK/playwrightvenv"
"$WORK/playwrightvenv/bin/pip" install -q playwright==1.55.0
"$WORK/playwrightvenv/bin/python" -m playwright install chromium >/dev/null
P07_D05_SSH_KEY="$KEY" P07_ALLOW_SYNTHETIC_D05=1 \
 P07_D05_SOURCE_ENGINE="$P07_D05_SOURCE_ENGINE" \
 timeout --signal=TERM --kill-after=10s 220s \
 "$WORK/playwrightvenv/bin/python" "$ROOT/tests/p07_m03_d05_cp_browser_lab_20261115.py"
echo P07_D05_ACTIVE_OFFICIAL_BROWSER_TEST=PASS
