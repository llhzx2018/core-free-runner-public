name: TEMP P07 M03 resume audit exact candidate Percona84 real DB stage
on:
  pull_request:
    branches: [main]
    paths:
      - '.github/workflows/temp-p07-m03-percona84-sql-20261124.yml'
permissions:
  contents: read
jobs:
  isolated-atomic:
    if: >-
      github.repository == 'llhzx2018/core-free-runner-public' &&
      github.event.pull_request.user.login == 'llhzx2018' &&
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.head_ref == 'test/p07-m03-percona84-native-20261124'
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
          python3 -B scripts/ephemeral_lane_spec.py validate --spec .github/ephemeral/p07-m03-percona84-sql-20261124.json > "$RUNNER_TEMP/p07-lane-check.json"
          python3 -B scripts/ephemeral_lane_spec.py audit-rendered --spec .github/ephemeral/p07-m03-percona84-sql-20261124.json --input .github/workflows/temp-p07-m03-percona84-sql-20261124.yml > "$RUNNER_TEMP/p07-lane-audit.json"
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
      - name: Two genuine Percona Server 8.4 instances, partial 15 and complete 22 schema import
        shell: bash
        env:
          P07_FIXTURE_PASSWORD: 'p07-only-synthetic-password-20261124'
        run: |
          set -Eeuo pipefail
          set +x
          command -v docker >/dev/null
          docker info >/dev/null
          image='percona/percona-server:8.4.11-12'
          docker pull -q "$image"
          image_id="$(docker image inspect "$image" --format '{{.Id}}')"
          test -n "$image_id"
          src="p07-source-$GITHUB_RUN_ID"
          dst="p07-target-$GITHUB_RUN_ID"
          echo "$src" > "$RUNNER_TEMP/p07-src-container"
          echo "$dst" > "$RUNNER_TEMP/p07-dst-container"
          docker run -d --name "$src" -e "MYSQL_ROOT_PASSWORD=$P07_FIXTURE_PASSWORD" "$image_id" >/dev/null
          docker run -d --name "$dst" -e "MYSQL_ROOT_PASSWORD=$P07_FIXTURE_PASSWORD" "$image_id" >/dev/null
          for name in "$src" "$dst"; do
            ok=0
            for trial in $(seq 1 90); do
              if docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$name" mysql --user=root --batch --skip-column-names --execute 'SELECT 1' >/dev/null 2>&1; then ok=1; break; fi
              sleep 3
            done
            test "$ok" = 1
          done
          a="$(docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$src" mysql --user=root --batch --skip-column-names --execute 'SELECT @@version, @@version_comment')"
          b="$(docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root --batch --skip-column-names --execute 'SELECT @@version, @@version_comment')"
          test "$a" = "$b"
          case "$a" in 8.4.*Percona*) ;; *) echo P07_NOT_SAME_PERCONA84; exit 38 ;; esac
          echo P07_M03_REAL_SAME_ENGINE_TWO_PERCONA84_INSTANCES=PASS
          T="$(mktemp -d "$RUNNER_TEMP/p07-percona84.XXXXXXXX")"
          echo "$T" > "$RUNNER_TEMP/p07-sql-dir"
          python3 -B - "$T/seed.sql" <<'PY'
          from pathlib import Path
          import sys
          with Path(sys.argv[1]).open('w',encoding='utf8') as f:
              for i in range(1,23):
                  name=f'vfsite{i:02d}'
                  f.write(f'CREATE DATABASE {name} CHARACTER SET utf8mb4;\nUSE {name};\n')
                  f.write('CREATE TABLE records(id INT PRIMARY KEY, title VARCHAR(180), payload VARBINARY(120), amount DECIMAL(10,2));\n')
                  f.write(f"INSERT INTO records VALUES (1,'测试{i:02d}✅',X'00ff',12.50),(2,'hello-{i:02d}',X'0001',0.00),(3,'emoji😀',X'0a0d',999.99);\n")
          PY
          docker exec -i -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$src" mysql --user=root --default-character-set=utf8mb4 < "$T/seed.sql"
          all_dbs=""
          partial_dbs=""
          for i in $(seq -w 1 22); do all_dbs="$all_dbs vfsite$i"; done
          for i in $(seq -w 1 15); do partial_dbs="$partial_dbs vfsite$i"; done
          docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$src" mysqldump --user=root --single-transaction --set-gtid-purged=OFF --hex-blob --databases $all_dbs > "$T/snapshot22.sql"
          test -s "$T/snapshot22.sql"
          sha256sum "$T/snapshot22.sql" > "$T/immutable-source.sha"
          docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$src" mysqldump --user=root --single-transaction --set-gtid-purged=OFF --hex-blob --databases $partial_dbs > "$T/partial15.sql"
          docker exec -i -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root < "$T/partial15.sql"
          if printf 'THIS IS NOT SQL;\n' | docker exec -i -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root >/dev/null 2>&1; then
            echo P07_INVALID_SQL_UNEXPECTED_PASS; exit 43
          fi
          export P07_SRC="$src" P07_DST="$dst" P07_DB_PASSWORD="$P07_FIXTURE_PASSWORD"
          python3 -B - "$GITHUB_WORKSPACE/.p07-private/lib" partial <<'PY'
          import sys,os,subprocess
          sys.path.insert(0,sys.argv[1])
          import migration_safe_batch_guard as guard
          stage=sys.argv[2]
          def mysql(host,sql):
              result=subprocess.run(['docker','exec','-e','MYSQL_PWD='+os.environ['P07_DB_PASSWORD'],os.environ[host],'mysql','--user=root','--batch','--skip-column-names','--execute',sql],capture_output=True,text=True,check=True)
              return result.stdout
          def plan():
              sites=[dict(domain=f'fixture{i:02d}.example.test',site_user=f'vfuser{i:02d}',mysql_databases=[f'vfsite{i:02d}'],runtime={'type':'PHP'},site_root=f'/home/vfuser{i:02d}/htdocs/fixture{i:02d}.example.test',document_root=f'/home/vfuser{i:02d}/htdocs/fixture{i:02d}.example.test/public') for i in range(1,23)]
              existing=frozenset(mysql('P07_DST','SHOW DATABASES').splitlines())
              return guard.classify(sites,[],[],source_identity='isolated-source',target_identity='isolated-target',source_ip='192.0.2.7',occupied_users=frozenset(),registered_databases=frozenset(),live_sql_databases=existing,historical_footprints=frozenset())
          p=plan()
          assert p['source_site_count']==22 and p['safe_site_count']==7 and p['excluded_site_count']==15
          assert all('TARGET_DATABASE_EXISTS' in row['reasons'] for row in p['excluded_sites'])
          assert not p['target_writes'] and not p['cutover_allowed']
          print('P07_M03_REAL_DB_PARTIAL_15_OF_22_NOT_FULL_COMPLETE=PASS')
          PY
          for db in $partial_dbs; do
            docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root --execute "DROP DATABASE $db"
          done
          docker exec -i -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root < "$T/snapshot22.sql"
          (cd "$T" && sha256sum -c immutable-source.sha >/dev/null)
          echo P07_M03_REAL_DB_SOURCE_SNAPSHOT_STILL_UNMODIFIED=PASS
      - name: Real 22 of 22 DDL, row data parity and target-side rollback
        shell: bash
        env:
          P07_FIXTURE_PASSWORD: 'p07-only-synthetic-password-20261124'
        run: |
          set -Eeuo pipefail
          set +x
          src="$(cat "$RUNNER_TEMP/p07-src-container")"
          dst="$(cat "$RUNNER_TEMP/p07-dst-container")"
          T="$(cat "$RUNNER_TEMP/p07-sql-dir")"
          export P07_SRC="$src" P07_DST="$dst" P07_DB_PASSWORD="$P07_FIXTURE_PASSWORD"
          python3 -B - "$GITHUB_WORKSPACE/.p07-private/lib" <<'PY'
          import sys,os,subprocess
          sys.path.insert(0,sys.argv[1])
          import migration_safe_batch_guard as guard
          def sql(which,query):
              out=subprocess.run(['docker','exec','-e','MYSQL_PWD='+os.environ['P07_DB_PASSWORD'],os.environ[which],'mysql','--user=root','--batch','--skip-column-names','--default-character-set=utf8mb4','--execute',query],capture_output=True,text=True,check=True)
              return out.stdout
          source_names=set(sql('P07_SRC','SHOW DATABASES').splitlines())
          target_names=set(sql('P07_DST','SHOW DATABASES').splitlines())
          for i in range(1,23):
              name=f'vfsite{i:02d}'
              assert name in source_names and name in target_names
              statement=f'SELECT id,HEX(title),HEX(payload),amount FROM {name}.records ORDER BY id'
              a,b=sql('P07_SRC',statement),sql('P07_DST',statement)
              assert a==b and len(a.strip().splitlines())==3, f'DATA_PARITY_FAILED_{name}'
              create=f'SHOW CREATE TABLE {name}.records'
              assert sql('P07_SRC',create)==sql('P07_DST',create), f'SCHEMA_PARITY_FAILED_{name}'
          sites=[dict(domain=f'fixture{i:02d}.example.test',site_user=f'vfuser{i:02d}',mysql_databases=[f'vfsite{i:02d}'],runtime={'type':'PHP'},site_root=f'/home/vfuser{i:02d}/htdocs/fixture{i:02d}.example.test',document_root=f'/home/vfuser{i:02d}/htdocs/fixture{i:02d}.example.test/public') for i in range(1,23)]
          p=guard.classify(sites,[],[],source_identity='isolated-source',target_identity='isolated-target',source_ip='192.0.2.7',occupied_users=frozenset(),registered_databases=frozenset(),live_sql_databases=frozenset(target_names),historical_footprints=frozenset())
          assert p['safe_site_count']==0 and p['excluded_site_count']==22
          assert all('TARGET_DATABASE_EXISTS' in r['reasons'] for r in p['excluded_sites'])
          print('P07_M03_REAL_PERCONA84_22_OF22_SCHEMA_AND_ROWS=PASS')
          print('P07_M03_REAL_PERCONA84_REPEAT_TARGET_IMPORT_BLOCKED_BY_GUARD=PASS')
          PY
          docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$src" mysqldump --user=root --single-transaction --set-gtid-purged=OFF --hex-blob --databases vfsite07 > "$T/site07-original.sql"
          docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root --execute "UPDATE vfsite07.records SET title='tampered' WHERE id=1"
          a="$(docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$src" mysql --user=root --batch --skip-column-names --execute 'SELECT HEX(title) FROM vfsite07.records WHERE id=1')"
          b="$(docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root --batch --skip-column-names --execute 'SELECT HEX(title) FROM vfsite07.records WHERE id=1')"
          test "$a" != "$b"
          docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root --execute 'DROP DATABASE vfsite07'
          docker exec -i -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root < "$T/site07-original.sql"
          b="$(docker exec -e "MYSQL_PWD=$P07_FIXTURE_PASSWORD" "$dst" mysql --user=root --batch --skip-column-names --execute 'SELECT HEX(title) FROM vfsite07.records WHERE id=1')"
          test "$a" = "$b"
          echo P07_M03_REAL_PERCONA84_TARGET_DRIFT_DETECT_AND_RESTORE=PASS
          echo P07_M03_FULL_CLOUDPANEL_2_VPS_E2E=NOT_RUN
          echo P07_M03_OWNER_22_SITE_MIGRATION=NOT_RUN
          echo P07_M03_FORMAL_RELEASE=NOT_PUBLISHED
      - name: Always erase native SQL containers, private source and fixture data
        if: always()
        shell: bash
        run: |
          set +e
          for pointer in p07-src-container p07-dst-container; do
            if [[ -f "$RUNNER_TEMP/$pointer" ]]; then
              name="$(cat "$RUNNER_TEMP/$pointer")"
              case "$name" in p07-source-*|p07-target-*) docker rm -f "$name" >/dev/null 2>&1 ;; esac
            fi
          done
          if [[ -f "$RUNNER_TEMP/p07-sql-dir" ]]; then
            tmp="$(cat "$RUNNER_TEMP/p07-sql-dir")"
            case "$tmp" in "$RUNNER_TEMP"/p07-percona84.*) rm -rf "$tmp" ;; esac
          fi
          rm -f "$RUNNER_TEMP/p07-src-container" "$RUNNER_TEMP/p07-dst-container" "$RUNNER_TEMP/p07-sql-dir"
          rm -rf -- "$GITHUB_WORKSPACE/.p07-private"
          if test -s "$RUNNER_TEMP/p07-atomic-current-path"; then
            t="$(cat "$RUNNER_TEMP/p07-atomic-current-path")"
            case "$t" in "$RUNNER_TEMP"/p07-atomic.*) rm -rf -- "$t";; esac
          fi
          rm -f -- "$RUNNER_TEMP/p07-atomic-current-path"
          rm -f -- "$RUNNER_TEMP/p07-batch-order-tests.log" "$RUNNER_TEMP/p07-lane-check.json" "$RUNNER_TEMP/p07-lane-audit.json"
          echo EPHEMERAL_PRIVATE_CLEANUP=COMPLETE
