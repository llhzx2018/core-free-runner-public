name: TEMP P07 M03 UX review and immutable offline candidate receipt
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-offline-candidate-proof-20261124.yml'
permissions:
  contents: read
jobs:
  p07-m03-offline-candidate-proof:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-offline-candidate-proof-20261124'
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    env:
      TARGET_REPO: '{{REPOSITORY}}'
      TARGET_VERSION: '{{TARGET_VERSION}}'
      TARGET_SHA: '{{TARGET_SHA}}'
      TARGET_TREE: '{{TARGET_TREE}}'
      BASE_SHA: 'fd113376cf8e44c6a3bc00fbe47f34c2a354726a'
      PYTHONDONTWRITEBYTECODE: '1'
      PYTHONUNBUFFERED: '1'
      P07_NO_EXEC: '1'
      P07_ALLOW_NONROOT: '1'
      NO_COLOR: '1'
    steps:
      - name: Checkout canonical public runner
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - name: Verify lane exact immutable product identity
        shell: bash
        run: |
          set -Eeuo pipefail
          python3 -B scripts/ephemeral_lane_spec.py validate \
            --spec .github/ephemeral/p07-m03-offline-candidate-proof-20261124.json \
            > "$RUNNER_TEMP/p07-m03-exact-spec.log"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered \
            --spec .github/ephemeral/p07-m03-offline-candidate-proof-20261124.json \
            --input .github/workflows/temp-p07-m03-offline-candidate-proof-20261124.yml \
            > "$RUNNER_TEMP/p07-m03-exact-rendered.json"
          python3 -B - "$RUNNER_TEMP/p07-m03-exact-rendered.json" "$TARGET_SHA" <<'PY'
          import json,sys
          d=json.load(open(sys.argv[1],encoding='utf-8'))
          assert d['status']=='PASS' and d['target_sha']==sys.argv[2]
          print('P07_M03_OFFLINE_SPEC=PASS')
          PY
      - name: Checkout exact P07 private product transiently
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: '{{REPOSITORY}}'
          ref: '{{TARGET_SHA}}'
          path: .p07-private
          fetch-depth: 0
          token: ${{ secrets.VF_PRIVATE_READ_TOKEN }}
          persist-credentials: false
      - name: Verify private source and immutable source tree
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          test "$(git -C "$P" rev-parse HEAD)" = "$TARGET_SHA"
          test "$(git -C "$P" rev-parse 'HEAD^{tree}')" = "$TARGET_TREE"
          test "$(cat "$P/VERSION")" = "$TARGET_VERSION"
          git -C "$P" cat-file -e "$BASE_SHA^{commit}"
          test -f "$P/.github/checks/prove_p07_safe_batch_package.sh"
          test -f "$P/scripts/check_p07_terminal_ux.py"
          test -f "$P/scripts/check_p07_modules.py"
          test "$(git -C "$P" status --porcelain --untracked-files=all)" = ""
          echo P07_M03_OFFLINE_EXACT_PRIVATE_SHA_TREE=PASS
      - name: Prove original native P07 terminal UI contract and bounded scope
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          test -d "$P/.git"
          failed=0
          prove() {
            label="$1"; shift
            if (cd "$P" && "$@") > "$RUNNER_TEMP/p07-m03-native-ux-$label.log" 2>&1; then
              echo "P07_M03_NATIVE_UX_$label=PASS"
            else
              python3 -B - "$RUNNER_TEMP/p07-m03-native-ux-$label.log" "$label" <<'PY'
          import pathlib,sys
          message=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8',errors='replace')
          mapping={
            '测试方法或断言缺失':'STALE_EVIDENCE_TEST',
            '发现新交互源码':'UNREGISTERED_UI_SOURCE',
            '未为本次所有交互源码提供 UX 证据':'UNCLAIMED_UI',
            'Git 改动范围不可核验':'DIFF_UNVERIFIED',
            '改动用户界面缺少':'EVIDENCE_MISSING',
            'UX 证据的源码路径':'REVIEW_SCOPE_MISMATCH',
          }
          code=next((v for k,v in mapping.items() if k in message),'OTHER')
          print('P07_M03_NATIVE_UX_FAIL_REASON_'+sys.argv[2]+'='+code)
          PY
              echo "P07_M03_NATIVE_UX_$label=FAIL"
              failed=1
            fi
          }
          prove CANONICAL_CHECK python3 -B scripts/check_p07_terminal_ux.py
          prove MODULE_SCOPE python3 -B scripts/check_p07_modules.py
          prove UX_CONTRACT python3 -B -m unittest discover -s tests -p test_p07_terminal_ux_contract.py -q
          prove MODULE_CONTRACT python3 -B -m unittest discover -s tests -p test_p07_module_contract.py -q
          prove PR_BASE_CHECK python3 -B scripts/check_p07_terminal_ux.py --base-ref "$BASE_SHA"
          if test "$failed" -ne 0; then
            echo P07_M03_NATIVE_UX_EQUIVALENT=FAIL
            exit 73
          fi
          echo P07_M03_NATIVE_UX_EQUIVALENT=PASS
      - name: Reuse immutable offline package machine proof without rerunning install
        if: always()
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          OLD_SHA=7227fa4d600f0fa9c2dcd975a83ef5e039fcd665
          test "$(git -C "$P" rev-parse HEAD)" = "$TARGET_SHA"
          git -C "$P" cat-file -e "$OLD_SHA^{commit}"
          differences="$(git -C "$P" diff --name-only "$OLD_SHA" "$TARGET_SHA")"
          test "$differences" = "docs/ux-reviews/p07-m03-d04-safe-batch-20261120.json"
          # Previous exact source produced a genuine independent machine
          # receipt for the unchanged packaging inputs and installed ZIP.
          # Run 45372681622; it is not a Formal Release approval.
          echo P07_M03_OFFLINE_CANDIDATE_INPUTS_UNCHANGED=PASS
          echo P07_M03_OFFLINE_INSTALL_UPGRADE_ROLLBACK=PREVIOUS_MACHINE_PROOF_REUSED
          echo P07_M03_NO_RELEASE_NO_REAL_VPS_NO_MIGRATION=PASS
      - name: Always wipe transient private source and test logs
        if: always()
        shell: bash
        run: |
          set +e
          rm -rf -- "$GITHUB_WORKSPACE/.p07-private"
          rm -f -- "$RUNNER_TEMP"/p07-m03-offline-*.log \
                   "$RUNNER_TEMP/p07-m03-exact-spec.log" \
                   "$RUNNER_TEMP/p07-m03-exact-rendered.json"
          echo P07_M03_OFFLINE_PRIVATE_CLEANUP=PASS
