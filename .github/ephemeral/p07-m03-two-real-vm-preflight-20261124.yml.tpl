name: TEMP P07 M03 D04 two independent Debian13 VM readiness (no CloudPanel install)
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-two-real-vm-preflight-20261124.yml'
permissions:
  contents: read
jobs:
  two-vm-readiness:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-two-real-vm-cloudpanel-preflight-20261124'
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    env:
      TARGET_REPO: '{{REPOSITORY}}'
      TARGET_VERSION: '{{TARGET_VERSION}}'
      TARGET_SHA: '{{TARGET_SHA}}'
      TARGET_TREE: '{{TARGET_TREE}}'
      NO_COLOR: '1'
      DEBIAN_FRONTEND: noninteractive
    steps:
      - name: Checkout public registered runner
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - name: Exact source lane preflight before virtual machine boot
        shell: bash
        run: |
          set -Eeuo pipefail
          python3 -B scripts/ephemeral_lane_spec.py validate --spec '.github/ephemeral/p07-m03-two-real-vm-preflight-20261124.json' > "$RUNNER_TEMP/p07-vm-spec.json"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered --spec '.github/ephemeral/p07-m03-two-real-vm-preflight-20261124.json' --input '.github/workflows/temp-p07-m03-two-real-vm-preflight-20261124.yml' > "$RUNNER_TEMP/p07-vm-audit.json"
          python3 -B - "$RUNNER_TEMP/p07-vm-audit.json" "$TARGET_SHA" <<'PY'
          import json,sys
          p=json.load(open(sys.argv[1]))
          assert p["status"]=="PASS" and p["target_sha"]==sys.argv[2]
          print("P07_D04_DEBIAN13_VM_SOURCE_IDENTITY_AUDIT=PASS")
          PY
      - name: Validate official CloudPanel VM-only boundary and free KVM requirements
        shell: bash
        run: |
          set -Eeuo pipefail
          test "$(uname -m)" = x86_64
          test -c /dev/kvm || { echo 'P07_D04_FREE_RUNNER_KVM_UNAVAILABLE'; exit 30; }
          test -r /dev/kvm && test -w /dev/kvm || sudo chmod 666 /dev/kvm
          test -r /dev/kvm && test -w /dev/kvm || { echo 'P07_D04_FREE_RUNNER_KVM_PERMISSION_BLOCK'; exit 31; }
          awk '/MemAvailable:/{if ($2 < 8000000) exit 32}' /proc/meminfo || { echo 'P07_D04_VM_RAM_INSUFFICIENT'; exit 32; }
          avail="$(df --output=avail -k "$RUNNER_TEMP" | tail -1)"
          test "$avail" -ge 8500000 || { echo 'P07_D04_VM_DISK_INSUFFICIENT'; exit 33; }
          sudo apt-get -qq update >/dev/null
          sudo apt-get -y -qq install --no-install-recommends qemu-system-x86 qemu-utils cloud-image-utils openssh-client > "$RUNNER_TEMP/p07-vm-apt.log" 2>&1 || {
            echo 'P07_D04_FREE_RUNNER_VM_PACKAGES_UNAVAILABLE'; exit 34;
          }
          command -v qemu-system-x86_64
          command -v cloud-localds
          qemu-system-x86_64 -accel help | grep -Fq kvm || { echo 'P07_D04_VM_KVM_ACCEL_NOT_SUPPORTED'; exit 35; }
          echo P07_D04_TWO_INDEPENDENT_VM_FREE_HOSTED_RUNNER_READY=PASS
      - name: Boot two real Debian13 QEMU KVM guests and verify SSH separation
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          umask 077
          T="$(mktemp -d "$RUNNER_TEMP/p07-d04-two-vm.XXXXXXXX")"
          echo "$T" > "$RUNNER_TEMP/p07-vm-directory"
          cd "$T"
          image_url='https://cdimage.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2'
          sums_url='https://cdimage.debian.org/images/cloud/trixie/latest/SHA512SUMS'
          curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error --retry 2 --max-time 420 "$image_url" -o debian13.qcow2
          curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error --retry 2 --max-time 90 "$sums_url" -o SHA512SUMS
          grep -E '^[0-9a-f]{128}  (\./)?debian-13-genericcloud-amd64.qcow2$' SHA512SUMS | sed 's@  \./@  @' | sha512sum -c - >/dev/null || {
            echo P07_D04_OFFICIAL_DEBIAN_IMAGE_HASH_UNVERIFIED; exit 36;
          }
          ssh-keygen -q -t ed25519 -N '' -f "$T/key"
          pub="$(cat "$T/key.pub")"
          cat > userdata <<EOF
          #cloud-config
          disable_root: false
          ssh_pwauth: false
          users:
            - name: root
              lock_passwd: true
              ssh_authorized_keys:
                - "$pub"
          EOF
          for side in source target; do
            cp debian13.qcow2 "$side.qcow2"
            qemu-img resize "$side.qcow2" 16G >/dev/null
            cp userdata "$side-userdata"
            printf 'instance-id: p07-%s\nlocal-hostname: p07-%s\n' "$side" "$side" > "$side-meta"
            cloud-localds "$side-seed.iso" "$side-userdata" "$side-meta"
          done
          qemu-system-x86_64 -enable-kvm -m 2600 -smp 2 \
            -drive file="$T/source.qcow2",format=qcow2,if=virtio \
            -drive file="$T/source-seed.iso",format=raw,if=virtio \
            -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22021-:22 \
            -device virtio-net-pci,netdev=net0 -display none -monitor none \
            -serial file:"$T/source-serial.log" -daemonize -pidfile "$T/source.pid"
          qemu-system-x86_64 -enable-kvm -m 2600 -smp 2 \
            -drive file="$T/target.qcow2",format=qcow2,if=virtio \
            -drive file="$T/target-seed.iso",format=raw,if=virtio \
            -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22022-:22 \
            -device virtio-net-pci,netdev=net0 -display none -monitor none \
            -serial file:"$T/target-serial.log" -daemonize -pidfile "$T/target.pid"
          for side in source target; do
            port=22021
            test "$side" = target && port=22022
            ready=0
            for trial in $(seq 1 70); do
              if ssh -q -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$T/known_hosts" \
                -o ConnectTimeout=5 -o BatchMode=yes -i "$T/key" -p "$port" root@127.0.0.1 \
                'test "$(cat /etc/os-release | grep VERSION_ID)" = "VERSION_ID=\"13\"" && test "$(uname -m)" = x86_64' >/dev/null 2>&1; then
                ready=1
                break
              fi
              sleep 5
            done
            test "$ready" = 1 || { echo "P07_D04_DEBIAN13_${side}_VM_SSH_NOT_READY"; exit 38; }
            echo "P07_D04_DEBIAN13_${side}_VM_SEPARATE_SSH=PASS"
          done
          srcid="$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22021 root@127.0.0.1 cat /etc/machine-id)"
          dstid="$(ssh -q -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$T/known_hosts" -i "$T/key" -p 22022 root@127.0.0.1 cat /etc/machine-id)"
          test -n "$srcid" && test -n "$dstid" && test "$srcid" != "$dstid" || {
            echo P07_D04_TWO_VM_INDEPENDENT_MACHINE_ID_UNPROVEN; exit 39;
          }
          echo P07_D04_TWO_INDEPENDENT_DEBIAN13_VM_BOOT_SSH_KVM=PASS
          echo P07_D04_CLOUDPANEL_INSTALLED=NOT_RUN
          echo P07_D04_SOURCE_TARGET_P07_PULL=NOT_RUN
          echo P07_D04_PRODUCTION_AND_DNS=UNTOUCHED
      - name: Always stop QEMU guests, erase keys, qcow2 and ephemeral files
        if: always()
        shell: bash
        run: |
          set +e
          if test -s "$RUNNER_TEMP/p07-vm-directory"; then
            T="$(cat "$RUNNER_TEMP/p07-vm-directory")"
            case "$T" in "$RUNNER_TEMP"/p07-d04-two-vm.*)
              for side in source target; do
                if test -f "$T/$side.pid"; then
                  pid="$(cat "$T/$side.pid")"
                  if test -n "$pid" && test "$pid" -eq "$pid" 2>/dev/null; then
                    kill "$pid" 2>/dev/null || true
                  fi
                fi
              done
              rm -rf -- "$T"
            ;; esac
          fi
          rm -f -- "$RUNNER_TEMP/p07-vm-directory" "$RUNNER_TEMP/p07-vm-spec.json" "$RUNNER_TEMP/p07-vm-audit.json" "$RUNNER_TEMP/p07-vm-apt.log"
          echo P07_D04_TRANSIENT_TWO_VM_PRIVATE_KEYS_AND_DISKS_CLEANUP=PASS
