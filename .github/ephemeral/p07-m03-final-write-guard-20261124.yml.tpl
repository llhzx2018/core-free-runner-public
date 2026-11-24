name: TEMP P07 M03 target occupancy guard unit and architecture proof
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-final-write-guard-20261124.yml'
permissions:
  contents: read
jobs:
  p07-m03-guard-regression:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-final-write-guard-20261124'
    runs-on: ubuntu-24.04
    timeout-minutes: 12
    env:
      TARGET_REPO: '{{REPOSITORY}}'
      TARGET_VERSION: '{{TARGET_VERSION}}'
      TARGET_SHA: '{{TARGET_SHA}}'
      TARGET_TREE: '{{TARGET_TREE}}'
      BASE_SHA: 'fd113376cf8e44c6a3bc00fbe47f34c2a354726a'
      GOV_SHA: 'e57edc475b44df7d682c857703dabc3d75fc8193'
      PYTHONDONTWRITEBYTECODE: '1'
      PYTHONUNBUFFERED: '1'
    steps:
      - name: Checkout registered public runner
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - name: Exact ephemeral lane validation
        shell: bash
        run: |
          set -Eeuo pipefail
          python3 -B scripts/ephemeral_lane_spec.py validate \
            --spec .github/ephemeral/p07-m03-final-write-guard-20261124.json \
            > "$RUNNER_TEMP/p07-m03-lane-validate.log"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered \
            --spec .github/ephemeral/p07-m03-final-write-guard-20261124.json \
            --input .github/workflows/temp-p07-m03-final-write-guard-20261124.yml \
            > "$RUNNER_TEMP/p07-m03-lane-audit.json"
          python3 -B - "$RUNNER_TEMP/p07-m03-lane-audit.json" "$TARGET_SHA" <<'PY'
          import json,sys
          with open(sys.argv[1],encoding='utf-8') as f: result=json.load(f)
          assert result.get('status')=='PASS' and result.get('target_sha')==sys.argv[2]
          print('P07_M03_EPHEMERAL_SPEC=PASS')
          PY
          echo P07_M03_NO_CLOUDPANEL_NO_MIGRATION=YES
      - name: Transient exact private product source checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: '{{REPOSITORY}}'
          ref: '{{TARGET_SHA}}'
          path: .p07-private
          token: ${{ secrets.VF_PRIVATE_READ_TOKEN }}
          fetch-depth: 0
          persist-credentials: false
      - name: Transient pinned governance source checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          repository: llhzx2018/gov-doc
          ref: e57edc475b44df7d682c857703dabc3d75fc8193
          path: .gov-private
          token: ${{ secrets.VF_PRIVATE_READ_TOKEN }}
          persist-credentials: false
      - name: Verify exact source bytes and no writes
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          G="$GITHUB_WORKSPACE/.gov-private"
          test "$(git -C "$P" rev-parse HEAD)" = "$TARGET_SHA"
          test "$(git -C "$P" rev-parse 'HEAD^{tree}')" = "$TARGET_TREE"
          test "$(git -C "$G" rev-parse HEAD)" = "$GOV_SHA"
          test "$(cat "$P/VERSION")" = "$TARGET_VERSION"
          git -C "$P" cat-file -e "$BASE_SHA^{commit}"
          test -f "$P/lib/migration_safe_batch_io.py"
          test -f "$P/lib/migration_safe_batch_inventory.py"
          test -f "$P/tests/test_p07_m03_safe_batch.py"
          test -f "$G/governance/agent/code_architecture_lint.py"
          echo P07_M03_EXACT_PRIVATE_SOURCE_AND_GOV=PASS
      - name: Parse precise M03 Python source without bytecode
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          python3 -B - "$GITHUB_WORKSPACE/.p07-private" <<'PY'
          import ast,pathlib,sys
          root=pathlib.Path(sys.argv[1])
          paths=('lib/migration_safe_batch_io.py','lib/migration_safe_batch_inventory.py',
                 'lib/migration_safe_batch_guard.py',
                 'lib/migration_safe_batch_cli.py','lib/migration_resume_audit.py',
                 'tests/test_p07_m03_safe_batch.py',
                 'tests/test_p07_m03_cloudpanel_sql_probe.py',
                 'tests/test_p07_m03_resume_audit.py')
          for path in paths:
              ast.parse((root/path).read_text(encoding='utf-8'),filename=path)
          print('P07_M03_PYTHON_SYNTAX='+str(len(paths)))
          PY
      - name: GOV-DOC architecture and source naming diff gate
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          G="$GITHUB_WORKSPACE/.gov-private"
          if ! (cd "$P" && python3 -B .github/checks/architecture_gate.py \
              --manifest .github/checks/code_architecture.json \
              --gov-root "$G" \
              --base-sha "$BASE_SHA" --head-sha "$TARGET_SHA" \
              --git-root "$P") > "$RUNNER_TEMP/p07-m03-architecture.log" 2>&1; then
            python3 -B - "$RUNNER_TEMP/p07-m03-architecture.log" <<'PY'
          import pathlib,re,sys
          text=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8',errors='replace')
          match=re.search(r'PROJECT_ARCHITECTURE=BLOCKED:([A-Z][A-Z0-9_]*)',text)
          print('P07_M03_ARCHITECTURE_BLOCK_CLASS='+(
              match.group(1) if match else 'UNCLASSIFIED'))
          PY
            echo P07_M03_ARCHITECTURE_AND_NAMING_GATE=FAIL
            exit 37
          fi
          grep -q '^PROJECT_ARCHITECTURE=STRUCTURAL_PASS' "$RUNNER_TEMP/p07-m03-architecture.log"
          echo P07_M03_ARCHITECTURE_AND_NAMING_GATE=PASS
          echo P07_M03_UNIT_RUN_ONLY_NO_SERVER_OR_SQL_WRITES=PASS
      - name: Run old-22-site history, zero-write and SQL catalog negative suites
        if: always()
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          P="$GITHUB_WORKSPACE/.p07-private"
          run_case() {
            label="$1"; pattern="$2"; root="$3"
            log="$RUNNER_TEMP/p07-m03-$label.log"
            if ! (cd "$P" && python3 -B -m unittest discover -s "$root" -p "$pattern" -q) > "$log" 2>&1; then
              # Only hashed test IDs and fixed exception categories leave
              # the private workspace; NEVER emit raw source/tracebacks.
              python3 -B - "$log" "$label" <<'PY'
          import hashlib,pathlib,re,sys
          content=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8',errors='replace')
          names=re.findall(r'^(?:FAIL|ERROR): (test_[A-Za-z0-9_]+) \(',content,re.M)
          for name in sorted(set(names))[:12]:
              print('P07_M03_FAILURE_TEST_HASH='+hashlib.sha256(name.encode()).hexdigest()[:16])
          classes=re.findall(r'^([A-Za-z][A-Za-z0-9]*Error):',content,re.M)
          safe={'AssertionError','TypeError','ValueError','KeyError','PermissionError',
                'FileNotFoundError','ModuleNotFoundError','ImportError','RuntimeError',
                'AttributeError','NameError','OSError','SyntaxError'}
          print('P07_M03_FAILURE_KINDS='+','.join(sorted(set(classes).intersection(safe))))
          print('P07_M03_FAILURE_COUNT='+str(len(names)))
          PY
              echo "P07_M03_$label=FAIL"
              return 1
            fi
            python3 -B - "$log" "$label" <<'PY'
          import pathlib,re,sys
          output=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8',errors='replace')
          match=re.search(r'Ran ([0-9]+) tests?',output)
          if match is None or int(match.group(1)) < 1:
              print('P07_M03_UNIT_DISCOVERY_UNVERIFIED')
              raise SystemExit(37)
          print('P07_M03_'+sys.argv[2]+'_PASS='+match.group(1))
          PY
          }
          failed=0
          run_case SAFE_BATCH test_p07_m03_safe_batch.py tests || failed=1
          run_case SQL_PROBE test_p07_m03_cloudpanel_sql_probe.py tests || failed=1
          run_case RESUME_AUDIT test_p07_m03_resume_audit.py tests || failed=1
          run_case TERMINAL_UX test_p07_m03_safe_batch_terminal_ux.py tests || failed=1
          run_case PULL_CORE test_server_migration_pull.py tests || failed=1
          run_case ARCH_NEGATIVES test_architecture_gate.py .github/checks || failed=1
          if test "$failed" -ne 0; then
            echo P07_M03_SELECTED_UNIT_SUITES=FAIL
            exit 36
          fi
          echo P07_M03_ALL_SELECTED_UNIT_SUITES=PASS
      - name: Always wipe transient private and governance sources
        if: always()
        shell: bash
        run: |
          set +e
          rm -rf -- "$GITHUB_WORKSPACE/.p07-private" "$GITHUB_WORKSPACE/.gov-private"
          rm -f -- "$RUNNER_TEMP"/p07-m03-*.log "$RUNNER_TEMP"/p07-m03-*.json
          echo P07_M03_TRANSIENT_PRIVATE_WORKSPACE_CLEANUP=PASS
