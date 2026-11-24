name: TEMP P07 M03 MariaDB118 native SQL import plus SQLite/static recovery
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-native-pull-restore-20261124.yml'
permissions:
  contents: read
jobs:
  isolated-atomic:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-native-pull-restore-20261124'
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
          python3 -B scripts/ephemeral_lane_spec.py validate --spec .github/ephemeral/p07-m03-native-pull-restore-20261124.json > "$RUNNER_TEMP/p07-lane-check.json"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered --spec .github/ephemeral/p07-m03-native-pull-restore-20261124.json --input .github/workflows/temp-p07-m03-native-pull-restore-20261124.yml > "$RUNNER_TEMP/p07-lane-audit.json"
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
      - name: Exact-source selection, history guard, and release147 safe-batch SQL guard tests
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
      - name: Real SQLite WAL and static asset snapshots with failure injections
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          cd "$GITHUB_WORKSPACE/.p07-private"
          python3 -B -m unittest -q \
            tests.test_p07_m03_d04_prepared_sqlite_online_snapshot \
            tests.test_p07_m03_d04_prepared_static_online_snapshot \
            tests.test_p07_m03_d04_prepared_online_refresh \
            > "$RUNNER_TEMP/p07-native-assets-test.log" 2>&1 || {
              grep -E '^(FAIL:|ERROR:|Ran [0-9]+ tests|FAILED)' "$RUNNER_TEMP/p07-native-assets-test.log" | cut -c1-320 | head -n 38 || true
              exit 42
            }
          grep -E '^(Ran [0-9]+ tests|OK)$' "$RUNNER_TEMP/p07-native-assets-test.log" || true
          echo P07_M03_SQLITE_WAL_REAL_PRIVATE_ONLINE_SNAPSHOT=PASS
          echo P07_M03_STATIC_SECOND_COPY_NO_OVERWRITE=PASS
          echo P07_M03_ORIGINAL_FAILED_22_SITE_TASK=NOT_RUN
          echo P07_M03_DUAL_CLOUDPANEL_FULL_PULL_E2E=NOT_RUN
          echo P07_M03_RELEASE_PUBLICATION=NOT_PERMITTED
      - name: Two real MariaDB 11.8 instances and native P07 target import adapter
        shell: bash
        run: |
          set -Eeuo pipefail
          set +x
          command -v docker >/dev/null
          docker info >/dev/null
          image='mariadb:11.8'
          docker pull -q "$image"
          id="$(docker image inspect "$image" --format '{{.Id}}')"
          test -n "$id"
          base="p07-native-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
          echo "$base" > "$RUNNER_TEMP/p07-native-container-base"
          for side in source target; do
            docker run -d --name "$base-$side" -e MARIADB_ROOT_PASSWORD=SYNTHETIC_ci_root_2026 "$id" >/dev/null
          done
          for side in source target; do
            ok=0
            for trial in $(seq 1 90); do
              if docker exec -e MYSQL_PWD=SYNTHETIC_ci_root_2026 "$base-$side" mariadb --user=root --batch --skip-column-names --execute 'SELECT 1' >/dev/null 2>&1; then ok=1; break; fi
              sleep 3
            done
            test "$ok" = 1
          done
          a="$(docker exec -e MYSQL_PWD=SYNTHETIC_ci_root_2026 "$base-source" mariadb --user=root --batch --skip-column-names --execute 'SELECT @@version, @@version_comment')"
          b="$(docker exec -e MYSQL_PWD=SYNTHETIC_ci_root_2026 "$base-target" mariadb --user=root --batch --skip-column-names --execute 'SELECT @@version, @@version_comment')"
          test "$a" = "$b"
          case "$a" in 11.8.*MariaDB*) ;; *) echo P07_INCORRECT_ENGINE; exit 38 ;; esac
          echo P07_M03_TWO_NATIVE_MARIADB118_SAME_ENGINE=PASS
          test ! -e /home/p07native
          sudo install -d -m 0700 -o "$(id -u)" -g "$(id -g)" /home/p07native/htdocs
          echo yes > "$RUNNER_TEMP/p07-native-home-created"
          cd "$GITHUB_WORKSPACE/.p07-private"
          export P07_MYSQL_NATIVE_CI=1 P07_NATIVE_DB_ENGINE=MARIADB_11.8 P07_NATIVE_DB_CONTAINER="$base"
          python3 -B -m unittest -v tests.test_p07_m03_d04_native_restore_drill > "$RUNNER_TEMP/p07-native-test.log" 2>&1 || {
            grep -E '^(test_|FAIL:|ERROR:|Ran [0-9]+ tests|FAILED|[A-Za-z_]*(Error|Blocked): [A-Z_]+)' "$RUNNER_TEMP/p07-native-test.log" | cut -c1-320 | head -n 38 || true
            exit 41
          }
          grep -E '^(Ran [0-9]+ tests|OK)$' "$RUNNER_TEMP/p07-native-test.log" || true
          echo P07_M03_REAL_P07_TARGET_CREATE_DATABASE_LOCAL=PASS
          echo P07_M03_NATIVE_FOREIGN_TARGET_REFUSED=PASS
          echo P07_M03_NATIVE_PARTIAL_IMPORT_MARKER_PREVENTS_REPLAY=PASS
      - name: Always erase native DBs, synthetic home and private source
        if: always()
        shell: bash
        run: |
          set +e
          if test -f "$RUNNER_TEMP/p07-native-container-base"; then
            base="$(cat "$RUNNER_TEMP/p07-native-container-base")"
            case "$base" in p07-native-*) docker rm -f "$base-source" "$base-target" >/dev/null 2>&1 ;; esac
          fi
          if test -f "$RUNNER_TEMP/p07-native-home-created"; then
            test -d /home/p07native && sudo rm -rf -- /home/p07native
          fi
          rm -f -- "$RUNNER_TEMP/p07-native-container-base" "$RUNNER_TEMP/p07-native-home-created"
          rm -f -- "$RUNNER_TEMP/p07-native-test.log" "$RUNNER_TEMP/p07-native-assets-test.log"
          rm -f -- "$RUNNER_TEMP/p07-batch-order-tests.log" "$RUNNER_TEMP/p07-lane-check.json" "$RUNNER_TEMP/p07-lane-audit.json"
          rm -rf -- "$GITHUB_WORKSPACE/.p07-private"
          test ! -e "$GITHUB_WORKSPACE/.p07-private"
          echo P07_NATIVE_TEST_PRIVATE_AND_SYNTHETIC_CLEANUP=PASS
