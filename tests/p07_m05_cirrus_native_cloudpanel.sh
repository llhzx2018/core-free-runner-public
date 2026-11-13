#!/usr/bin/env bash
# P07-M05 新服务器初始化 · one-off native Debian13 GCE platform validation.
# This PUBLIC test NEVER fetches private P07 source, user data, or credentials.
# Official CloudPanel first-install success is necessary but NOT SUFFICIENT
# for the P07-M05 exact-product full install/recovery Formal Release gate.
set -Eeuo pipefail
umask 077
fail(){ echo "P07_M05_CIRRUS_NATIVE=BLOCKED_$1"; exit 13; }
[[ "${CIRRUS_REPO_FULL_NAME:-}" == llhzx2018/core-free-runner-public &&
   "${CIRRUS_BRANCH:-}" == feat/p07-unified-independent-module-router-20261112 &&
   -z "${CIRRUS_PR:-}" &&
   -n "${CIRRUS_BUILD_ID:-}" ]] || fail WRONG_OR_UNVERIFIED_CIRRUS_CONTEXT
source /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" == 13 && "$(uname -m)" == x86_64 ]] ||
  fail NOT_REAL_DEBIAN13_AMD64
[[ "$(ps -p 1 -o comm= | tr -d '[:space:]')" == systemd ]] ||
  fail NOT_NATIVE_SYSTEMD_VM
sudo -n true || fail NO_ROOT_FOR_EPHEMERAL_VM
command -v curl >/dev/null || fail CURL_NOT_AVAILABLE
# Prove the machine is a direct Compute Engine VM, not an Ubuntu container
# masquerading as Debian. Never print instance IDs or instance metadata.
timeout 6 curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/id' \
  >/dev/null || fail NOT_GCE_NATIVE_COMPUTE
for path in /home/clp /var/lib/mysql /opt/vf-server-ops \
            /opt/vfops-modules/m01 /opt/vfops-modules/m02 \
            /opt/vfops-modules/m03 /opt/vfops-modules/m04 \
            /opt/vfops-modules/m05; do
  [[ ! -e "$path" && ! -L "$path" ]] || fail EXISTING_INSTALL_OR_MODULE
done
for executable in clpctl mysql mariadb nginx; do
  if command -v "$executable" >/dev/null 2>&1; then
    fail EXISTING_SERVICE_BINARY
  fi
done
echo P07_M05_CIRRUS_NATIVE_DEBIAN13_EMPTY_VM=PASS
echo P07_M05_CIRRUS_NATIVE_DB_ENGINE=MARIADB_11.8
echo P07_M05_CIRRUS_PRIVATE_SOURCE=NOT_CHECKED_OUT
tempdir="$(mktemp -d -t p07-m05-native-cirrus.XXXXXXXX)"
cleanup(){ rm -f -- "$tempdir/cloudpanel-install.sh" "$tempdir/private-installer.log"; rmdir "$tempdir" 2>/dev/null || true; }
trap cleanup EXIT
# Exact upstream bytes from CloudPanel official install documentation,
# not a mutable unchecked curl | bash installation.
curl --fail --silent --show-error --location --retry 3 \
  --connect-timeout 15 --max-time 90 \
  https://installer.cloudpanel.io/ce/v2/install.sh \
  -o "$tempdir/cloudpanel-install.sh" ||
  fail OFFICIAL_INSTALLER_DOWNLOAD
echo '8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476  '"$tempdir/cloudpanel-install.sh" |
  sha256sum --check --status || fail OFFICIAL_INSTALLER_SHA256_DRIFT
bash -n "$tempdir/cloudpanel-install.sh" || fail OFFICIAL_INSTALLER_SYNTAX
echo P07_M05_CIRRUS_OFFICIAL_INSTALLER_IDENTITY=PASS
# One CloudPanel installation on an ephemeral bare Debian13 VM, never VPS.
# Keep raw output transient and private: it may contain system credentials.
set +e
sudo timeout --signal=TERM --kill-after=20s 2400s \
  env DEBIAN_FRONTEND=noninteractive DB_ENGINE=MARIADB_11.8 \
  bash "$tempdir/cloudpanel-install.sh" \
  > "$tempdir/private-installer.log" 2>&1
rc=$?
set -e
echo "P07_M05_CIRRUS_OFFICIAL_INSTALL_EXIT=$rc"
if [[ "$rc" -ne 0 ]]; then
  echo P07_M05_CIRRUS_OFFICIAL_CLOUDPANEL=FAILED_OR_ENV_BLOCKED
  echo P07_M05_CIRRUS_RAW_LOG=PERSISTED_NOWHERE
  exit 13
fi
command -v clpctl >/dev/null || fail CLOUDPANEL_CLI_MISSING
command -v mariadb >/dev/null || fail MARIADB_CLIENT_MISSING
mariadb --version | grep -F '11.8.' >/dev/null || fail DB_WRONG_VERSION
sudo test -f /home/clp/htdocs/app/data/db.sq3 || fail PANEL_DB_MISSING
test "$(sudo systemctl is-active mariadb)" = active || fail MARIADB_INACTIVE
sudo mariadb --batch --skip-column-names -e 'SELECT 2+3' 2>/dev/null |
  grep -qx 5 || fail REAL_SQL_NOT_VERIFIED
echo P07_M05_CIRRUS_NATIVE_DEBIAN13_MARIADB118=PASS
echo P07_M05_CIRRUS_OFFICIAL_CLOUDPANEL_BOOTSTRAP=PASS_PLATFORM_ONLY
echo P07_M05_CIRRUS_P07_EXACT_SOURCE_FULL=NOT_RUN
echo P07_M05_CIRRUS_PRODUCT_FIRST_ADMIN_AND_ROLLBACK=NOT_RUN
echo P07_M05_CIRRUS_FORMAL_RELEASE_GATE=BLOCKED_EXACT_PRODUCT_PROOF
echo P07_M05_CIRRUS_OWNER_VPS_DNS_DATA=UNTOUCHED
