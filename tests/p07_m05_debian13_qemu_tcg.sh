#!/usr/bin/env bash
# P07-M05 新服务器初始化 · real blank Debian 13 guest under QEMU TCG.
# Hosted ONLY on disposable free GitHub Actions. No /dev/kvm, no Owner VPS,
# no DNS, no production or private data. Private source is transient.
set -Eeuo pipefail
umask 077
blocked(){ echo "P07_M05_DEBIAN13_QEMU=BLOCKED_$1" >&2; exit 12; }
[[ "$GITHUB_ACTIONS" == true &&
   "$GITHUB_REPOSITORY" == llhzx2018/core-free-runner-public &&
   "$GITHUB_REF" == refs/heads/feat/p07-unified-independent-module-router-20261112 &&
   "$P07_M05_THROWAWAY_GITHUB_VM" == YES_I_ACKNOWLEDGE_EPHEMERAL_GH_VM &&
   -n "$GITHUB_RUN_ID" ]] || blocked NOT_EPHEMERAL_GITHUB
trial="$P07_M05_OFFLINE_TRIAL_FILE"
[[ "$trial" == /* && -f "$trial" && ! -L "$trial" ]] || blocked PRIVATE_TRIAL_MISSING
realpath "$trial" | grep -F /private_m05/owner-trial/ >/dev/null ||
  blocked PRIVATE_TRIAL_NOT_OWNED
echo "e42b6b3c59719f6ec189e4c62b7cfc54385aaa6e566c8f92ca5306246f022bbb  $trial" |
  sha256sum -c - >/dev/null || blocked PRIVATE_TRIAL_CHECKSUM
# Everything after this line is sandboxed inside this ephemeral Runner.
sudo apt-get -qq update
sudo DEBIAN_FRONTEND=noninteractive apt-get -qq -y install \
  qemu-system-x86 qemu-utils cloud-image-utils openssh-client >/dev/null
work="$(mktemp -d -t p07-m05-debian13-qemu.XXXXXXXX)"
cleanup(){
  if [[ -f "$work/qemu.pid" ]]; then
    kill "$(cat "$work/qemu.pid")" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$work"
}
trap cleanup EXIT
cd "$work"
image=debian-13-genericcloud-amd64.qcow2
base='https://cloud.debian.org/images/cloud/trixie/latest'
curl --fail --show-error --silent --location --retry 3 \
  "$base/SHA512SUMS" -o SHA512SUMS ||
  blocked OFFICIAL_DEBIAN_SHA512_INDEX_UNAVAILABLE
curl --fail --show-error --silent --location --retry 3 \
  "$base/$image" -o "$image" ||
  blocked OFFICIAL_DEBIAN_QCOW2_DOWNLOAD_UNAVAILABLE
grep -F " $image" SHA512SUMS | sha512sum -c --status - ||
  blocked OFFICIAL_DEBIAN_QCOW2_CHECKSUM_FAILURE
echo "P07_M05_DEBIAN13_OFFICIAL_CLOUD_IMAGE_SHA256=$(sha256sum "$image" | cut -d' ' -f1)"
qemu-img resize "$image" 24G >/dev/null
ssh-keygen -q -t ed25519 -N '' -f "$work/key"
cat > "$work/user-data" <<EOF
#cloud-config
users:
  - default
  - name: p07test
    groups: [sudo]
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]
    shell: /bin/bash
    ssh_authorized_keys:
      - $(cat "$work/key.pub")
ssh_pwauth: false
disable_root: true
EOF
cat > "$work/meta-data" <<EOF
instance-id: p07-m05-free-debian13-$(date +%s)
local-hostname: p07-m05-clean
EOF
cloud-localds "$work/seed.img" "$work/user-data" "$work/meta-data" >/dev/null
qemu-system-x86_64 \
  -machine q35 \
  -accel tcg,thread=multi \
  -cpu max -smp 4 -m 5120 \
  -drive file="$work/$image",if=virtio,format=qcow2,cache=writeback \
  -drive file="$work/seed.img",if=virtio,format=raw \
  -netdev user,id=p07net,hostfwd=tcp:127.0.0.1:22442-:22 \
  -device virtio-net-pci,netdev=p07net \
  -display none -serial "file:$work/guest-serial.log" \
  -monitor none -daemonize -pidfile "$work/qemu.pid" ||
  blocked QEMU_TCG_BOOT_FAILURE
guest_ssh(){
  ssh -q -T -i "$work/key" -p 22442 -o BatchMode=yes \
    -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 "$@"
}
guest_scp(){
  scp -q -i "$work/key" -P 22442 -o BatchMode=yes \
    -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no \
    -o ConnectTimeout=8 "$@"
}
ready=no
for i in $(seq 1 80); do
  if guest_ssh p07test@127.0.0.1 true >/dev/null 2>&1; then ready=yes; break; fi
  sleep 8
done
[[ "$ready" == yes ]] || blocked QEMU_DEBIAN13_SSH_BOOT_TIMEOUT
guest_ssh p07test@127.0.0.1 'test "$(id -u)" -gt 0 &&
 grep -qx "ID=debian" /etc/os-release &&
 grep -qx "VERSION_ID=\"13\"" /etc/os-release &&
 test ! -e /home/clp && test ! -e /var/lib/mysql &&
 ! command -v mysql && ! command -v mariadb &&
 ! command -v nginx && ! command -v clpctl' ||
 blocked NOT_AN_EMPTY_DEBIAN13_GUEST
echo P07_M05_DEBIAN13_QEMU_EMPTY_GUEST=PASS
guest_scp "$trial" p07test@127.0.0.1:/tmp/p07-m05-private-trial.run
guest_ssh p07test@127.0.0.1 \
  'sudo bash /tmp/p07-m05-private-trial.run --install-only >/dev/null &&
   test "$(readlink /opt/vfops-modules/m05/current)" = "releases/0.1.0-m05-candidate2"' ||
 blocked MODULE_INSTALL_IN_GUEST
# Execute the actual product M05 backend on a genuine empty Debian13 VM.
guest_ssh p07test@127.0.0.1 \
  'sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate target-status --bootstrap-preflight' \
  > "$work/preflight.json" ||
 blocked CLEAN_DEBIAN13_PREFLIGHT_FAILURE
python3 - "$work/preflight.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("status")=="READY" and d.get("writes_performed") is False
assert d.get("os_id")=="debian" and d.get("version_id")=="13"
assert "MARIADB_11.8" in d.get("db_engine_options",[])
assert "MYSQL_8.4" in d.get("db_engine_options",[])
print("P07_M05_DEBIAN13_ACTUAL_EMPTY_VM_PREFLIGHT=PASS")
PY
guest_ssh p07test@127.0.0.1 \
  'sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate bootstrap-local --confirm BOOTSTRAP_LOCAL_CLOUDPANEL' \
  > "$work/no-db-choice.log" 2>&1 && blocked UNSELECTED_DB_ACCEPTED
echo P07_M05_DEBIAN13_UNSELECTED_DB=REJECTED
# Opt-in actual empty guest CloudPanel install. The Guest VM itself is
# destroyed after the job, and no generated CloudPanel password is disclosed.
set +e
timeout 2300 guest_ssh p07test@127.0.0.1 \
  'sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate bootstrap-local --db-engine MARIADB_11.8 --confirm BOOTSTRAP_LOCAL_CLOUDPANEL' \
  > "$work/cloudpanel-private.log" 2>&1
rc=$?
set -e
echo "P07_M05_DEBIAN13_QEMU_CLOUDPANEL_BOOTSTRAP_RC=$rc"
if [[ "$rc" != 0 ]]; then
  echo P07_M05_DEBIAN13_QEMU_CLOUDPANEL=FAILED_OR_TIMED_OUT
  echo P07_M05_DEBIAN13_QEMU_PRIVATE_LOG_NOT_PUBLISHED=YES
  exit 13
fi
guest_ssh p07test@127.0.0.1 \
  'sudo test -f /home/clp/htdocs/app/data/db.sq3 &&
   command -v clpctl &&
   mariadb --version | grep -F "11.8."' >/dev/null ||
  blocked CLOUDPANEL_MARIADB118_POSTINSTALL_READBACK
echo P07_M05_DEBIAN13_QEMU_CLOUDPANEL_MARIADB118=PASS
echo P07_M05_DEBIAN13_QEMU_OTHER_MODULES=UNTOUCHED
echo P07_M05_GITHUB_PUBLIC_PRIVATE_ARTIFACT=NONE
echo P07_M05_OWNER_SERVER=UNTOUCHED
echo P07_M05_DNS=UNTOUCHED
