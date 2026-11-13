#!/usr/bin/env bash
# P07-M05 新服务器初始化 · real blank Debian 13 guest; optional KVM on an
# explicitly authorized disposable GH runner, otherwise TCG ENGINE-only.
# Never run CloudPanel FULL on unaccelerated TCG or any Owner VPS.
# No DNS, no production or private data. Private source is transient.
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
# Never mistake "KVM available" for "QEMU actually using KVM".
# An explicit FULL request MUST refuse unavailable hardware acceleration,
# not silently run a 38-minute TCG CloudPanel installation.
vm_mode=TCG
vm_opts=(-accel tcg,thread=multi -cpu max)
case "${P07_M05_EXPLICIT_FULL_INSTALL_ON_KVM:-NO}" in
  NO) ;;
  YES)
    [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]] ||
      blocked EXPLICIT_KVM_REQUEST_WITHOUT_ACCESS
    vm_mode=KVM
    vm_opts=(-accel kvm -cpu host)
    ;;
  *) blocked INVALID_ACCELERATION_OPT_IN ;;
esac
echo "P07_M05_DEBIAN13_VM_ACCELERATION=$vm_mode"
qemu-system-x86_64 \
  -machine q35 \
  "${vm_opts[@]}" -smp 4 -m 5120 \
  -drive file="$work/$image",if=virtio,format=qcow2,cache=writeback \
  -drive file="$work/seed.img",if=virtio,format=raw \
  -netdev user,id=p07net,hostfwd=tcp:127.0.0.1:22442-:22 \
  -device virtio-net-pci,netdev=p07net \
  -display none -serial "file:$work/guest-serial.log" \
  -monitor none -daemonize -pidfile "$work/qemu.pid" ||
  blocked QEMU_TCG_BOOT_FAILURE
guest_ssh(){
  limit="$P07_GUEST_SSH_TIMEOUT"
  timeout "$limit" ssh -q -T -i "$work/key" -p 22442 -o BatchMode=yes \
    -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 "$@"
}
guest_scp(){
  scp -q -i "$work/key" -P 22442 -o BatchMode=yes \
    -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no \
    -o ConnectTimeout=8 "$@"
}
P07_GUEST_SSH_TIMEOUT=30
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
  'sudo bash /tmp/p07-m05-private-trial.run --install-only >/dev/null' ||
 blocked MODULE_INSTALL_IN_GUEST
guest_ssh p07test@127.0.0.1 \
  'test "$(sudo readlink /opt/vfops-modules/m05/current)" = "releases/0.1.0-m05-candidate2"' ||
 blocked MODULE_BUILD_READBACK_IN_GUEST
echo P07_M05_DEBIAN13_QEMU_REAL_MODULE_INSTALL=PASS
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
# A prior exact-source free hosted TCG guest ran CloudPanel for 2300s and
# timed out (run #43256040818, exit=124). Never rerun that 38-minute
# experiment automatically on software virtualization. This CI lane owns the
# REAL Debian13 preflight proof, not a false claim of CloudPanel INSTALL PASS.
if [[ "$vm_mode" == TCG ]]; then
  # Direct Debian 13 engine-only stage: verify the ACTUAL MariaDB 11.8
  # daemon on a real guest, plus existing-DB protection. This is NOT
  # CloudPanel installation; it happens AFTER clean-M05 preflight proof.
  if [[ "${P07_M05_VERIFY_DEBIAN13_MARIADB118_DAEMON:-NO}" == "YES" ]]; then
    echo P07_M05_DEBIAN13_DIRECT_DB_STAGE=START
    # Package originates from verified Debian 13 official apt repos.
    # Never install this database onto a host with user/business data.
    guest_ssh p07test@127.0.0.1 \
      'sudo env DEBIAN_FRONTEND=noninteractive apt-get -qq update >/tmp/p07-m05-apt-private.log 2>&1' ||
      blocked DEBIAN13_APT_INDEX_UPDATE
    P07_GUEST_SSH_TIMEOUT=1350 guest_ssh p07test@127.0.0.1 \
      'sudo env DEBIAN_FRONTEND=noninteractive apt-get -qq -y --no-install-recommends install mariadb-server >>/tmp/p07-m05-apt-private.log 2>&1' ||
      blocked DEBIAN13_MARIADB118_APT_INSTALL
    guest_ssh p07test@127.0.0.1 \
      'test "$(sudo systemctl is-active mariadb)" = "active" &&
       sudo mariadb --batch --skip-column-names -e "SELECT VERSION()" | grep -Eq "^11\\.8\\." &&
       sudo mariadb --batch --skip-column-names -e "SELECT 2+3" | grep -qx "5"' ||
      blocked DEBIAN13_MARIADB118_SERVICE_OR_SQL_READBACK
    echo P07_M05_DEBIAN13_REAL_MARIADB118_DAEMON=PASS
    echo P07_M05_DEBIAN13_REAL_MARIADB118_SQL=PASS
    # M05 must DENY CloudPanel install on a non-empty DB host, including
    # the case where the engine happens to be the selected engine.
    guest_ssh p07test@127.0.0.1 \
      'if sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate target-status --bootstrap-preflight >/dev/null 2>&1; then exit 31; fi;
       if sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate bootstrap-local --db-engine MARIADB_11.8 --confirm BOOTSTRAP_LOCAL_CLOUDPANEL >/dev/null 2>&1; then exit 32; fi;
       sudo mariadb --batch --skip-column-names -e "SELECT VERSION()" | grep -Eq "^11\\.8\\.";
       test ! -e /home/clp && ! command -v clpctl' ||
      blocked DEBIAN13_INSTALLED_DB_NO_OVERWRITE_PROTECTION
    echo P07_M05_DEBIAN13_EXISTING_DB_INSTALL_REJECTED=PASS
    echo P07_M05_DEBIAN13_EXISTING_DB_RETAINED=PASS
  fi
  echo P07_M05_DEBIAN13_ACTUAL_EMPTY_VM_PREFLIGHT=PASS
  echo P07_M05_DEBIAN13_CLOUDPANEL_INSTALL=BLOCKED_TCG_FULL_INSTALL_TIMEOUT
  if [[ "${P07_M05_VERIFY_DEBIAN13_MARIADB118_DAEMON:-NO}" == "YES" ]]; then
    echo P07_M05_DEBIAN13_MARIADB118_DAEMON_READBACK=PASS_ENGINE_ONLY
  else
    echo P07_M05_DEBIAN13_MARIADB118_DAEMON_READBACK=NOT_RUN
  fi
  echo P07_M05_DEBIAN13_FOUR_OTHER_MODULES=UNTOUCHED
  echo P07_M05_GITHUB_PUBLIC_PRIVATE_ARTIFACT=NONE
  echo P07_M05_OWNER_SERVER=UNTOUCHED
  echo P07_M05_DNS=UNTOUCHED
  exit 0
fi
# Opt-in actual empty guest CloudPanel install. The Guest VM itself is
# destroyed after the job, and no generated CloudPanel password is disclosed.
set +e
P07_GUEST_SSH_TIMEOUT=2300 guest_ssh p07test@127.0.0.1 \
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
# Prove the actual P07-M05 new-server-init terminal first-admin workflow
# and final CloudPanel READY on the very same Debian13 KVM guest.
# Never store a password in argv, logs, artifacts or Git: the existing
# test drives a disabled-echo PTY using one-time synthetic credentials.
[[ "$GITHUB_RUN_ID" =~ ^[0-9]+$ ]] || blocked INVALID_EPHEMERAL_RUN_ID
[[ -f "$GITHUB_WORKSPACE/tests/p07_m05_native_first_admin.py" ]] ||
  blocked REAL_FIRST_ADMIN_HARNESS_MISSING
guest_scp "$GITHUB_WORKSPACE/tests/p07_m05_native_first_admin.py" \
  p07test@127.0.0.1:/tmp/p07-m05-native-first-admin.py ||
  blocked FIRST_ADMIN_HARNESS_CANNOT_TRANSFER
P07_GUEST_SSH_TIMEOUT=300 guest_ssh p07test@127.0.0.1 \
  "sudo env GITHUB_ACTIONS=true GITHUB_REPOSITORY=llhzx2018/core-free-runner-public GITHUB_REF=refs/heads/feat/p07-unified-independent-module-router-20261112 GITHUB_RUN_ID=$GITHUB_RUN_ID P07_M05_THROWAWAY_GITHUB_VM=YES_I_ACKNOWLEDGE_EPHEMERAL_GH_VM P07_M05_TEST_REAL_FIRST_ADMIN=YES RUNNER_TEMP=/tmp python3 -B /tmp/p07-m05-native-first-admin.py" \
  > "$work/first-admin-safe-stdout.txt" 2> "$work/first-admin-private-stderr.txt" ||
  blocked FIRST_ADMIN_REAL_UI_FAILED
grep -Fxq 'P07_M05_FIRST_ADMIN_NONINTERACTIVE_DENIAL=PASS' \
  "$work/first-admin-safe-stdout.txt" ||
  blocked FIRST_ADMIN_NONINTERACTIVE_GATE_UNPROVEN
grep -Fxq 'P07_M05_FIRST_ADMIN_REAL_PRODUCT_UI=PASS' \
  "$work/first-admin-safe-stdout.txt" ||
  blocked FIRST_ADMIN_UI_UNPROVEN
grep -Fxq 'P07_M05_FIRST_ADMIN_CLOUDPANEL_READY_READBACK=PASS' \
  "$work/first-admin-safe-stdout.txt" ||
  blocked FIRST_ADMIN_READY_UNPROVEN
guest_ssh p07test@127.0.0.1 \
  'if sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate bootstrap-local --db-engine MARIADB_11.8 --confirm BOOTSTRAP_LOCAL_CLOUDPANEL >/dev/null 2>&1; then exit 33; fi;
   sudo bash /opt/vfops-modules/m05/current/bin/vfops-init-core server-migrate target-status' \
  > "$work/final-status.json" ||
  blocked POST_ADMIN_REINSTALL_REJECTED_OR_READBACK_FAILED
python3 - "$work/final-status.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
assert d.get("status")=="CLOUDPANEL_READY"
assert d.get("writes_performed") is False
print("P07_M05_DEBIAN13_CLOUDPANEL_FIRST_ADMIN_AND_READY=PASS")
print("P07_M05_DEBIAN13_CLOUDPANEL_REINSTALL_DENIED=PASS")
PY
echo P07_M05_DEBIAN13_QEMU_CLOUDPANEL_MARIADB118=PASS
echo P07_M05_DEBIAN13_QEMU_OTHER_MODULES=UNTOUCHED
echo P07_M05_GITHUB_PUBLIC_PRIVATE_ARTIFACT=NONE
echo P07_M05_OWNER_SERVER=UNTOUCHED
echo P07_M05_DNS=UNTOUCHED
