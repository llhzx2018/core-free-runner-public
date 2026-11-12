#!/usr/bin/env bash
# P07-M05 新服务器初始化 — registered FREE GitHub runner capability preflight.
# Public-safe metadata only. NO system changes, no VM, no credential reads.
set -Eeuo pipefail
echo 'P07_M05_FREE_RUNNER_PROBE=START'
echo "P07_M05_RUNNER_OS=$(uname -s)"
echo "P07_M05_RUNNER_ARCH=$(uname -m)"
echo "P07_M05_RUNNER_CPUS=$(nproc)"
echo "P07_M05_RUNNER_MEM_AVAILABLE_KB=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
echo "P07_M05_RUNNER_ROOT_FREE_KB=$(df -Pk . | awk 'END {print $4}')"
if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
  echo 'P07_M05_FREE_KVM=AVAILABLE'
else
  echo 'P07_M05_FREE_KVM=UNAVAILABLE'
fi
if command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo 'P07_M05_QEMU_PREINSTALLED=YES'
else
  echo 'P07_M05_QEMU_PREINSTALLED=NO'
fi
if command -v cloud-localds >/dev/null 2>&1; then
  echo 'P07_M05_CLOUD_INIT_SEED_TOOL=YES'
else
  echo 'P07_M05_CLOUD_INIT_SEED_TOOL=NO'
fi
if [[ -r /proc/cpuinfo ]] && grep -Eq '(^flags.*(vmx|svm))' /proc/cpuinfo; then
  echo 'P07_M05_CPU_VIRTUALIZATION_FLAG=PRESENT'
else
  echo 'P07_M05_CPU_VIRTUALIZATION_FLAG=NOT_EXPOSED'
fi
if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
  echo 'P07_M05_VM_REAL_INSTALL_CAPABILITY=READY_FOR_FRESH_GUEST_BOOT'
else
  echo 'P07_M05_VM_REAL_INSTALL_CAPABILITY=NO_HARDWARE_ACCELERATION'
fi
echo 'P07_M05_FREE_RUNNER_PROBE=COMPLETE'
