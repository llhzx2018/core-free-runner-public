#!/usr/bin/env bash
# Scope: synthetic local paths only. Never touches actual /opt, /usr/local/bin or a VPS.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d -t p07-rollback-gate.XXXXXX)"
trap 'rm -rf "$test_root"' EXIT

for mode in upgrade first_install; do
  case_root="$test_root/$mode"
  install_dir="$case_root/runtime"
  previous_dir="$case_root/runtime.previous"
  blocker="$case_root/not-a-directory"
  mkdir -p "$case_root"
  : > "$blocker"
  if [[ "$mode" == upgrade ]]; then
    mkdir -p "$install_dir"
    printf '%s\n' "previous-production-runtime" > "$install_dir/old-marker"
  fi

  # The package validates normally, then mkdir for BIN_LINK fails AFTER the
  # runtime swap. The EXIT trap must recover the old install or remove a new
  # first-install tree. All installation paths stay inside test_root.
  if P07_ALLOW_NONROOT=1 P07_NO_EXEC=1 \
      P07_PUBLIC_ROOT="file://$ROOT" \
      P07_INSTALL_DIR="$install_dir" \
      P07_PREVIOUS_DIR="$previous_dir" \
      P07_BIN_LINK="$blocker/vfops" \
      bash "$ROOT/experiments/p07-installer-rollback-candidate.sh" >"$case_root/installer.log" 2>&1; then
    printf 'P07_ROLLBACK_TEST=FAIL: unexpected installer success (%s)\n' "$mode" >&2
    exit 1
  fi

  [[ ! -e "$previous_dir" ]] || {
    printf 'P07_ROLLBACK_TEST=FAIL: stray previous runtime (%s)\n' "$mode" >&2
    exit 1
  }
  [[ ! -e "${install_dir}.new" ]] || {
    printf 'P07_ROLLBACK_TEST=FAIL: stray new runtime (%s)\n' "$mode" >&2
    exit 1
  }
  if [[ "$mode" == upgrade ]]; then
    [[ -f "$install_dir/old-marker" ]] || {
      printf 'P07_ROLLBACK_TEST=FAIL: old runtime lost\n' >&2
      exit 1
    }
    [[ "$(cat "$install_dir/old-marker")" == "previous-production-runtime" ]] || exit 1
  else
    [[ ! -e "$install_dir" ]] || {
      printf 'P07_ROLLBACK_TEST=FAIL: failed first install remained\n' >&2
      exit 1
    }
  fi
done

printf 'P07_INSTALLER_ATOMIC_ABORT_ROLLBACK_PASS\n'
