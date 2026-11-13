#!/usr/bin/env bash
# P07-M05 新服务器初始化: real CloudPanel bootstrap on a disposable FREE GitHub VM.
# It is intentionally NOT a genuine pristine Debian13 VPS. Never Owner production.
set -Eeuo pipefail
umask 077
fail_env(){ echo "P07_M05_FREE_NATIVE=BLOCKED_ENV_$1" >&2; exit 12; }
[[ "$GITHUB_ACTIONS" == true &&
   "$GITHUB_REPOSITORY" == llhzx2018/core-free-runner-public &&
   "$GITHUB_REF" == refs/heads/feat/p07-unified-independent-module-router-20261112 &&
   "$P07_M05_THROWAWAY_GITHUB_VM" == YES_I_ACKNOWLEDGE_EPHEMERAL_GH_VM &&
   -n "$GITHUB_RUN_ID" && "$(id -u)" == 0 ]] || fail_env NOT_A_VERIFIED_EPHEMERAL_VM
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail_env UNSUPPORTED_TEST_OS
# Official CloudPanel matrix: Ubuntu24.04 allows MySQL8.4 or MariaDB10.11.
# Debian13 MariaDB11.8 is a different independent proof, not substituted here.
ENGINE="${P07_M05_NATIVE_DB_ENGINE:-MYSQL_8.4}"
case "$ENGINE" in
  MYSQL_8.4) CLIENT=mysql; EXPECTED_VERSION='8.4.' ;;
  MARIADB_10.11) CLIENT=mariadb; EXPECTED_VERSION='10.11.' ;;
  *) fail_env DB_ENGINE_NOT_IN_UBUNTU24_ALLOWLIST ;;
esac
[[ ! -e /home/clp && ! -L /home/clp && ! -e /opt/vf-server-ops ]] ||
  fail_env EXISTING_CLOUDPANEL_OR_M03
for sibling in /opt/vfops-modules/m01 /opt/vfops-modules/m02 \
               /opt/vfops-modules/m03 /opt/vfops-modules/m04; do
  [[ ! -e "$sibling" && ! -L "$sibling" ]] || fail_env EXISTING_OTHER_MODULE
done
trial="$P07_M05_OFFLINE_TRIAL_FILE"
[[ "$trial" == /* && -f "$trial" && ! -L "$trial" ]] || fail_env PRIVATE_TRIAL_FILE_MISSING
realpath -- "$trial" | grep -F '/private_m05/owner-trial/' >/dev/null ||
  fail_env PRIVATE_TRIAL_WRONG_PATH
echo "e42b6b3c59719f6ec189e4c62b7cfc54385aaa6e566c8f92ca5306246f022bbb  $trial" |
 sha256sum -c - >/dev/null || fail_env PRIVATE_TRIAL_SHA_MISMATCH
bash "$trial" --install-only
CORE=/opt/vfops-modules/m05/current/bin/vfops-init-core
[[ -x "$CORE" ]] || fail_env M05_CLI_NOT_INSTALLED
echo P07_M05_FREE_NATIVE_MODULE_INSTALL=PASS
# No owner selection -> no CloudPanel installation.
if bash "$CORE" server-migrate bootstrap-local --confirm BOOTSTRAP_LOCAL_CLOUDPANEL >/dev/null 2>&1; then
  fail_env MISSING_DB_SELECTION_WAS_ACCEPTED
fi
echo P07_M05_FREE_NATIVE_UNSELECTED_DB=REJECTED
if bash "$CORE" server-migrate target-status --bootstrap-preflight >/dev/null 2>&1; then
  echo P07_M05_GITHUB_STOCK_IMAGE=ALREADY_READY
else
  echo P07_M05_GITHUB_STOCK_IMAGE=PREINSTALLED_CONFLICTS_REJECTED
fi
# The Ubuntu Actions VM is discarded after the job. Purge only known stock
# server packages, never Owner servers or any other module's data.
export DEBIAN_FRONTEND=noninteractive
packages="$(dpkg-query -W -f='${binary:Package} ${db:Status-Abbrev}\n' 2>/dev/null |
  awk '$2 ~ /^ii/ && $1 ~ /^(mysql|mariadb|nginx|apache2|percona)(-|$)/ {print $1}' |
  tr '\n' ' ')"
if [[ -n "$packages" ]]; then
  echo P07_M05_FREE_NATIVE_REMOVING_PRELOADED_APT_CONFLICTS=YES
  printf '%s\n' "$packages" | xargs -r sudo apt-get -qq -y purge >/dev/null
fi
[[ ! -e /home/clp && ! -e /opt/vf-server-ops ]] || fail_env CLEANUP_SCOPE_DRIFT
for path in /var/lib/mysql /var/lib/mariadb /etc/nginx /etc/apache2; do
  if [[ -d "$path" && ! -L "$path" ]]; then
    rm -rf --one-file-system -- "$path"
  elif [[ -e "$path" || -L "$path" ]]; then
    fail_env CONFLICT_PATH_NOT_DIRECTORY
  fi
done
if command -v mysql >/dev/null 2>&1 || command -v mariadb >/dev/null 2>&1 ||
   command -v nginx >/dev/null 2>&1 || command -v apache2 >/dev/null 2>&1; then
  fail_env CONFLICT_BINARY_LEFTOVER
fi
set +e
preflight="$(bash "$CORE" server-migrate target-status --bootstrap-preflight 2>&1)"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  echo P07_M05_FREE_NATIVE_CLEAN_PREFLIGHT=BLOCKED_NONPRISTINE_HOST
  exit 12
fi
printf '%s' "$preflight" | python3 -c '
import json,sys
r=json.load(sys.stdin)
assert r.get("status")=="READY" and r.get("writes_performed") is False
assert r.get("os_id")=="ubuntu" and r.get("version_id")=="24.04"
assert set(("MYSQL_8.4","MARIADB_10.11")).issubset(r.get("db_engine_options",[]))
'
echo P07_M05_FREE_NATIVE_CLEAN_PREFLIGHT=PASS
echo "P07_M05_FREE_NATIVE_SELECTED_DB=$ENGINE"
# Actual official CloudPanel installer invoked by exact P07-M05 product backend.
# Output is kept in transient private temp, never published to public artifact.
set +e
timeout --signal=TERM --kill-after=30 2400 \
 bash "$CORE" server-migrate bootstrap-local \
 --db-engine "$ENGINE" --confirm BOOTSTRAP_LOCAL_CLOUDPANEL \
 >"$RUNNER_TEMP/p07-m05-cloudpanel-private-install.log" 2>&1
install_rc=$?
set -e
echo "P07_M05_FREE_NATIVE_BOOTSTRAP_RC=$install_rc"
if [[ "$install_rc" -ne 0 ]]; then
  # The source's real exception includes only a safe failure code and a
  # numeric subprocess exit status; parse those but NEVER print raw output.
  P07_M05_SELECTED_DB_ENGINE="$ENGINE" python3 - "$RUNNER_TEMP/p07-m05-cloudpanel-private-install.log" <<'PY'
import os,pathlib,re,sys
raw=pathlib.Path(sys.argv[1]).read_text(encoding="utf-8",errors="ignore")
engine=os.environ["P07_M05_SELECTED_DB_ENGINE"]
cases=(
 ("CLOUDPANEL_SELECTED_DATABASE_DAEMON_MISMATCH_NO_REINSTALL","SELECTED_ENGINE_MISMATCH"),
 ("CLOUDPANEL_INSTALL_FAILED_"+engine,"INSTALLER_NONZERO_OR_PANEL_NOT_READY"),
 ("CloudPanel installation incomplete","PANEL_DATABASE_METADATA_MISSING"),
 ("CLOUDPANEL_DATABASE_OWNER_SELECTION_REQUIRED","OWNER_DATABASE_SELECTION_MISSING"),
 ("Traceback","UNHANDLED_PYTHON_ERROR"),
)
code=next((value for key,value in cases if key in raw),"UNKNOWN_SAFE_CLASS")
match=re.search(r"安装进程退出码[ ]+(-?[0-9]{1,4})",raw)
reason="UNKNOWN" if not match else str(int(match.group(1)))
print("P07_M05_FREE_NATIVE_SAFE_FAILURE_CLASS="+code)
print("P07_M05_FREE_NATIVE_CLOUDPANEL_CHILD_EXIT="+reason)
print("P07_M05_FREE_NATIVE_FAILURE_LOG_REDACTED=YES")
PY
  # Determine the exact boundary reached in product's real installer
  # pipeline WITHOUT ever reading installer stdout / credentials into CI logs.
  official=/root/cloudpanel-install.sh
  if [[ -f "$official" && ! -L "$official" ]]; then
    if echo '8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476  /root/cloudpanel-install.sh' | sha256sum -c - >/dev/null 2>&1; then
      echo P07_M05_FREE_NATIVE_OFFICIAL_INSTALLER=DOWNLOADED_AND_SHA256_PASS
    else
      echo P07_M05_FREE_NATIVE_OFFICIAL_INSTALLER=DOWNLOADED_BUT_SHA256_MISMATCH
    fi
    if bash -n "$official" >/dev/null 2>&1; then
      echo P07_M05_FREE_NATIVE_OFFICIAL_INSTALLER_SYNTAX=PASS
    else
      echo P07_M05_FREE_NATIVE_OFFICIAL_INSTALLER_SYNTAX=FAIL
    fi
  else
    echo P07_M05_FREE_NATIVE_OFFICIAL_INSTALLER=ABSENT_BEFORE_SCRIPT
  fi
  if [[ -d /run/systemd/system ]]; then
    echo P07_M05_FREE_NATIVE_SYSTEMD=AVAILABLE
  else
    echo P07_M05_FREE_NATIVE_SYSTEMD=UNAVAILABLE
  fi
  # All output is explicitly non-secret, allowlisted metadata only.
  for bin in clpctl mysql mariadb nginx; do
    if command -v "$bin" >/dev/null 2>&1; then
      echo "P07_M05_FREE_NATIVE_POSTFAIL_BINARY_$bin=FOUND"
    else
      echo "P07_M05_FREE_NATIVE_POSTFAIL_BINARY_$bin=ABSENT"
    fi
  done
  if [[ -f /home/clp/htdocs/app/data/db.sq3 ]]; then
    echo P07_M05_FREE_NATIVE_POSTFAIL_PANEL_SQLITE=PRESENT
  else
    echo P07_M05_FREE_NATIVE_POSTFAIL_PANEL_SQLITE=ABSENT
  fi
  echo P07_M05_FREE_NATIVE_CLOUDPANEL_INSTALL=FAIL_OR_ENV_BLOCKED
  echo P07_M05_FREE_NATIVE_INSTALLER_LOG=PRIVATE_NOT_PUBLISHED
  exit 13
fi
command -v clpctl >/dev/null || fail_env CLOUDPANEL_CLI_NOT_INSTALLED
command -v "$CLIENT" >/dev/null || fail_env SELECTED_DB_CLIENT_NOT_INSTALLED
"$CLIENT" --version | grep -F "$EXPECTED_VERSION" >/dev/null ||
  fail_env SELECTED_DB_ENGINE_VERSION_MISMATCH
test -f /home/clp/htdocs/app/data/db.sq3 || fail_env CLOUDPANEL_SQLITE_NOT_INSTALLED
bash "$CORE" server-migrate target-status | python3 -c '
import json,sys
s=json.load(sys.stdin).get("status")
assert s in ("CLOUDPANEL_READY","CLOUDPANEL_ADMIN_REQUIRED"),s
print("P07_M05_FREE_NATIVE_CLOUDPANEL_STATUS="+s)
'
for sibling in /opt/vfops-modules/m01 /opt/vfops-modules/m02 \
               /opt/vfops-modules/m03 /opt/vfops-modules/m04; do
  [[ ! -e "$sibling" && ! -L "$sibling" ]] || fail_env OTHER_MODULE_WAS_MODIFIED
done
# A second bootstrap against this now-populated CloudPanel must refuse
# any change of engine without touching the installed daemon.
# target-status is a READ-ONLY discovery command. Once CloudPanel exists it
# intentionally exits 0 and reports CLOUDPANEL_ADMIN_REQUIRED / CLOUDPANEL_READY
# instead of raising a process error. Correctly assert its JSON state.
already="$(bash "$CORE" server-migrate target-status --bootstrap-preflight)"
if ! printf '%s' "$already" | python3 -c '
import json,sys
r=json.load(sys.stdin)
assert r.get("status") in ("CLOUDPANEL_ADMIN_REQUIRED","CLOUDPANEL_READY")
assert r.get("writes_performed") is False
'; then
  fail_env EXISTING_CLOUDPANEL_READONLY_STATUS_WRONG
fi
echo P07_M05_FREE_NATIVE_EXISTING_CLOUDPANEL_PREFLIGHT=ALREADY_INSTALLED_NO_WRITES
if bash "$CORE" server-migrate bootstrap-local --db-engine "$ENGINE" \
  --confirm BOOTSTRAP_LOCAL_CLOUDPANEL >/dev/null 2>&1; then
  fail_env EXISTING_CLOUDPANEL_REINSTALL_NOT_BLOCKED
fi
"$CLIENT" --version | grep -F "$EXPECTED_VERSION" >/dev/null ||
  fail_env SELECTED_ENGINE_CHANGED_AFTER_REINSTALL_DENIAL
echo P07_M05_FREE_NATIVE_EXISTING_CLOUDPANEL_REINSTALL=REJECTED
echo "P07_M05_FREE_NATIVE_CLOUDPANEL_$ENGINE=PASS"
echo P07_M05_FREE_NATIVE_OTHER_FOUR_MODULES=UNCHANGED
echo P07_M05_DEBIAN13_MARIADB118=NOT_RUN
echo P07_M05_OWNER_VPS=UNTOUCHED
echo P07_M05_DNS=UNTOUCHED
