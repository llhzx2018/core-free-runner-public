name: TEMP P07 M03 resume audit exact candidate 147rc4 owner trial
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-147rc4-atomic-20261124.yml'
permissions:
  contents: read
jobs:
  isolated-atomic:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-147rc4-atomic-20261124'
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    env:
      TARGET_REPO: '{{REPOSITORY}}'
      TARGET_VERSION: '{{TARGET_VERSION}}'
      TARGET_SHA: '{{TARGET_SHA}}'
      TARGET_TREE: '{{TARGET_TREE}}'
      PRODUCT_SHA: '{{TARGET_SHA}}'
      NO_COLOR: '1'
      PYTHONDONTWRITEBYTECODE: '1'
      GH_TOKEN: ${{ github.token }}
    steps:
      - name: Checkout public lane contract
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - name: Public source-render audit before any private checkout
        shell: bash
        run: |
          set -Eeuo pipefail
          python3 -B scripts/ephemeral_lane_spec.py validate --spec .github/ephemeral/p07-m03-147rc4-spec.json > "$RUNNER_TEMP/p07-lane-check.json"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered --spec .github/ephemeral/p07-m03-147rc4-spec.json --input .github/workflows/temp-p07-m03-147rc4-atomic-20261124.yml > "$RUNNER_TEMP/p07-lane-audit.json"
          python3 -B - "$RUNNER_TEMP/p07-lane-audit.json" "$TARGET_SHA" <<'PY'
          import json,sys
          data=json.load(open(sys.argv[1],encoding='utf-8'))
          assert data['status']=='PASS' and data['target_sha']==sys.argv[2]
          print('P07_M03_RC4_SOURCE_LANE_PRECHECK=PASS')
          PY
      - name: Transient exact private source checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: {{REPOSITORY}}
          ref: ${{ env.TARGET_SHA }}
          token: ${{ secrets.VF_PRIVATE_READ_TOKEN }}
          fetch-depth: 1
          persist-credentials: false
          path: .p07-private
      - name: Exact-source selection, history guard, and release147 runtime closure tests
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          cd "$GITHUB_WORKSPACE/.p07-private"
          test "$(git rev-parse HEAD)" = "$PRODUCT_SHA"
          test "$(git rev-parse HEAD^{tree})" = "$TARGET_TREE"
          python3 -B -m unittest -q \
            tests.test_p07_m03_safe_batch \
            tests.test_p07_m03_trial_builder_146 \
            tests.test_p07_m03_safe_batch_terminal_ux \
            tests.test_p07_m03_resume_audit \
            tests.test_p07_m03_cloudpanel_sql_probe \
            > "$RUNNER_TEMP/p07-batch-order-tests.log" 2>&1 || {
              tail -n 50 "$RUNNER_TEMP/p07-batch-order-tests.log"
              exit 31
            }
          tail -n 3 "$RUNNER_TEMP/p07-batch-order-tests.log"
          echo BATCH_22SITE_HISTORY_UNVERIFIED_FAIL_CLOSED=PASS
          echo NINE_FILE_RELEASE147_RESUME_AUDIT_CLOSURE_UNIT=PASS
      - name: Genuine official146 install and exact candidate upgrade with fault rollback
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          product="$GITHUB_WORKSPACE/.p07-private"
          test "$(git -C "$product" rev-parse HEAD)" = "$PRODUCT_SHA"
          T="$(mktemp -d "$RUNNER_TEMP/p07-atomic.XXXXXXXX")"
          echo "$T" > "$RUNNER_TEMP/p07-atomic-current-path"
          chmod 0700 "$T"
          official="$T/release146.zip"
          candidate="$T/P07-M03-{{TARGET_VERSION}}-release147-rc4-OWNER-TRIAL.zip"
          curl --proto '=https' --tlsv1.2 -fLsS --retry 2 --max-time 180 \
            'https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-m03-v{{TARGET_VERSION}}-release146-20261122/P07-M03-{{TARGET_VERSION}}-release146.zip' -o "$official"
          echo "7b3e46c651c5ce3597e4ab535fbdc734023fc1b706fe85189a344ee600514321  $official" | sha256sum -c - >/dev/null
          python3 -B "$product/scripts/p07_m03_trial_from_official.py" \
            --official-zip "$official" --product-root "$product" \
            --product-sha "$PRODUCT_SHA" --official-build {{TARGET_VERSION}}-release146 \
            --build {{TARGET_VERSION}}-release147-rc4 --output "$candidate" > "$T/build-receipt.log"
          grep -Fq 'P07_M03_TRIAL_BUILD=PASS' "$T/build-receipt.log"
          echo GENUINE146_147RC_EXACT_SOURCE=PASS
          python3 -B - "$official" "$candidate" "$T" <<'PY'
          import pathlib,sys,zipfile
          base,candidate,folder=sys.argv[1:]
          for label,archive in (("base",base),("candidate",candidate)):
              root=pathlib.Path(folder)/label
              root.mkdir(mode=0o700)
              with zipfile.ZipFile(archive) as z:
                  for f in z.infolist():
                      name=pathlib.PurePosixPath(f.filename)
                      assert not name.is_absolute() and ".." not in name.parts and not f.is_dir()
                  z.extractall(root)
          PY
          mkdir -p "$T/runtime-parent" "$T/bin" "$T/other-modules"
          for m in m01 m02 m04 m05; do printf 'P07_SYNTHETIC_%s_42\n' "$m" > "$T/other-modules/$m"; done
          before="$(find "$T/other-modules" -type f -exec sha256sum {} \; | sort | sha256sum)"
          export P07_INSTALL_DIR="$T/runtime-parent/p07"
          export P07_PREVIOUS_DIR="$T/runtime-parent/p07.previous"
          export P07_BIN_LINK="$T/bin/vfops"
          export P07_ALLOW_NONROOT=1 P07_NO_EXEC=1
          # Official release146 wrapper verifies the published ZIP and signed runtime.
          curl --proto '=https' --tlsv1.2 -fLsS --max-time 90 \
            'https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-m03-release146-atomic.sh' \
            -o "$T/official146-installer.sh"
          bash "$T/official146-installer.sh" install > "$T/official-install.log" 2>&1
          test "$(cat "$P07_INSTALL_DIR/BUILD_ID")" = '{{TARGET_VERSION}}-release146'
          test "$(NO_COLOR=1 "$P07_BIN_LINK" --build-id)" = '{{TARGET_VERSION}}-release146'
          test ! -e "$P07_PREVIOUS_DIR"
          echo OFFICIAL146_ISOLATED_FRESH_INSTALL=PASS
          cp -a "$T/candidate" "$T/broken-candidate"
          printf 'UNTRUSTED\n' >> "$T/broken-candidate/dist/p07/{{TARGET_VERSION}}/overlay/lib/migration_cloudpanel_sql_probe.py"
          if P07_PUBLIC_ROOT="file://$T/broken-candidate" bash "$T/broken-candidate/installers/p07-final.sh" > "$T/tamper.log" 2>&1; then
            echo TAMPERED_CANDIDATE_UNEXPECTED_ACCEPT; exit 31
          fi
          test "$(cat "$P07_INSTALL_DIR/BUILD_ID")" = '{{TARGET_VERSION}}-release146'
          test ! -e "$P07_PREVIOUS_DIR"
          echo CORRUPT_CANDIDATE_REJECTED_WITH_OLD_VERSION_SAFE=PASS
          mkdir -p "$T/stubs"
          cat > "$T/stubs/mv" <<'SH'
          #!/usr/bin/env bash
          if [[ "$#" == 2 && "$1" == "$P07_INSTALL_DIR.new" && "$2" == "$P07_INSTALL_DIR" ]]; then
            echo 'ISOLATED_TEST_FAULT_INJECTED' >&2
            exit 47
          fi
          exec /usr/bin/mv "$@"
          SH
          chmod +x "$T/stubs/mv"
          if PATH="$T/stubs:$PATH" P07_PUBLIC_ROOT="file://$T/candidate" \
            bash "$T/candidate/installers/p07-final.sh" > "$T/fault.log" 2>&1; then
            echo FAULT_INJECTION_UNEXPECTED_ACCEPT; exit 32
          fi
          grep -Fq 'ISOLATED_TEST_FAULT_INJECTED' "$T/fault.log"
          test "$(cat "$P07_INSTALL_DIR/BUILD_ID")" = '{{TARGET_VERSION}}-release146'
          test "$(NO_COLOR=1 "$P07_BIN_LINK" --build-id)" = '{{TARGET_VERSION}}-release146'
          test ! -e "$P07_PREVIOUS_DIR"
          echo POST_MOVE_FAILURE_AUTO_ROLLBACK_TO_146=PASS
          P07_PUBLIC_ROOT="file://$T/candidate" \
            bash "$T/candidate/installers/p07-final.sh" > "$T/upgrade.log" 2>&1
          test "$(cat "$P07_INSTALL_DIR/BUILD_ID")" = '{{TARGET_VERSION}}-release147-rc4'
          test "$(NO_COLOR=1 "$P07_BIN_LINK" --build-id)" = '{{TARGET_VERSION}}-release147-rc4'
          test "$(cat "$P07_PREVIOUS_DIR/BUILD_ID")" = '{{TARGET_VERSION}}-release146'
          test -f "$P07_INSTALL_DIR/lib/migration_cloudpanel_sql_probe.py"
          grep -Fq 'source_assets_snapshot_sha256' "$P07_INSTALL_DIR/lib/migration_safe_batch_cli.py"
          grep -Fq 'BATCH_ALL_SOURCE_ASSETS_CHANGED_REPLAN_REQUIRED' "$P07_INSTALL_DIR/lib/migration_safe_batch_io.py"
          grep -Fq 'BATCH_MULTI_SOURCE_HISTORY_ABSENT_TRIAL_BLOCK' "$P07_INSTALL_DIR/lib/migration_safe_batch_cli.py"
          grep -Fq 'BATCH_OWNER_TRIAL_SINGLE_SITE_ONLY' "$P07_INSTALL_DIR/lib/migration_safe_batch_cli.py"
          grep -Fq '试用版已暂停整机全选' "$P07_INSTALL_DIR/components/p07-m03-safe-batch-ui.sh"
          grep -Fq 'p07_m03_resume_audit' "$P07_INSTALL_DIR/bin/vfops-migrate-ui"
          grep -Fq 'RESUME_HISTORY_CHANGED_DURING_READ' "$P07_INSTALL_DIR/lib/migration_resume_audit.py"
          grep -Fq '继续未完成迁移 · 先核实现场' "$P07_INSTALL_DIR/components/p07-m03-resume-audit-ui.sh"
          echo INSTALLED_RESUME_READONLY_ENTRY=PASS
          echo INSTALLED_22SITE_HALT_GUARD=PASS
          echo RELEASE146_TO_147RC_ATOMIC_UPGRADE=PASS
          echo RELEASE146_RECOVERY_SNAPSHOT_INTACT=PASS
          after="$(find "$T/other-modules" -type f -exec sha256sum {} \; | sort | sha256sum)"
          test "$before" = "$after"
          echo OTHER_FOUR_MODULE_SENTINELS_UNCHANGED=PASS
          echo NO_WEBSITE_OR_DATABASE_OR_DNS_WRITE=YES
          echo OWNER_TRIAL_ONLY_NOT_FORMAL=YES
      - name: Always erase transient private checkout and isolated runtime
        if: always()
        shell: bash
        run: |
          set +e
          rm -rf -- "$GITHUB_WORKSPACE/.p07-private"
          if test -s "$RUNNER_TEMP/p07-atomic-current-path"; then
            t="$(cat "$RUNNER_TEMP/p07-atomic-current-path")"
            case "$t" in "$RUNNER_TEMP"/p07-atomic.*) rm -rf -- "$t";; esac
          fi
          rm -f -- "$RUNNER_TEMP/p07-atomic-current-path"
          rm -f -- "$RUNNER_TEMP/p07-batch-order-tests.log" "$RUNNER_TEMP/p07-lane-check.json" "$RUNNER_TEMP/p07-lane-audit.json"
          echo EPHEMERAL_PRIVATE_CLEANUP=COMPLETE
