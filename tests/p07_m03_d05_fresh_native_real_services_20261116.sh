#!/usr/bin/env bash
# P07-M03-D05 数据库引擎转换: two native database services, read-only
# fresh-target proof. Synthetic containers ONLY; no owner/production endpoint.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
PROD="$PWD/.p07-private-final-d05"
test -f "$PROD/lib/db_engine_conversion_fresh_target.py"
tmp="$(mktemp -d)"
chmod 700 "$tmp"
clean() {
  set +e
  docker rm -f p07-d05-fresh-src p07-d05-fresh-dst >/dev/null 2>&1
  rm -rf "$tmp"
}
trap clean EXIT
if ! command -v mysql >/dev/null && ! command -v mariadb >/dev/null; then
  sudo apt-get update -qq >/dev/null
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq default-mysql-client >/dev/null
fi
test -n "$(command -v mysql || command -v mariadb)"
srcpass='P07_TEST_FRESH_SOURCE_ONLY_2026'
dstpass='P07_TEST_FRESH_TARGET_ONLY_2026'
docker run -d --name p07-d05-fresh-src \
 --label org.kewaro.p07.d05=synthetic-readonly \
 -e "MARIADB_ROOT_PASSWORD=$srcpass" \
 -p 127.0.0.1:33071:3306 mariadb:11.8 >/dev/null
ready=0
for n in $(seq 1 95); do
  if docker exec -e "MYSQL_PWD=$srcpass" p07-d05-fresh-src \
    mariadb -uroot -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
test "$ready" -eq 1
docker exec -i -e "MYSQL_PWD=$srcpass" p07-d05-fresh-src mariadb -uroot <<'SQL'
CREATE DATABASE oldfixture;
CREATE TABLE oldfixture.payload (id INT NOT NULL PRIMARY KEY, text_value VARCHAR(80));
INSERT INTO oldfixture.payload VALUES (1,'synthetic-maria-only'),(2,'keep-source');
SQL
cat > "$tmp/src.cnf" <<EOF
[client]
user=root
password=$srcpass
protocol=tcp
host=127.0.0.1
port=33071
EOF
chmod 600 "$tmp/src.cnf"
export PYTHONPATH="$PROD/lib"

for target in community percona; do
  docker rm -f p07-d05-fresh-dst >/dev/null 2>&1 || true
  if test "$target" = community; then
    image='mysql:8.4'
    expected='MYSQL_8.4'
  else
    image='percona/percona-server:8.4.11-12'
    expected='MYSQL_8.4_PERCONA'
  fi
  docker run -d --name p07-d05-fresh-dst \
    --label org.kewaro.p07.d05=synthetic-readonly \
    -e "MYSQL_ROOT_PASSWORD=$dstpass" -e MYSQL_ROOT_HOST=% \
    -p 127.0.0.1:33072:3306 "$image" >/dev/null
  ready=0
  for n in $(seq 1 100); do
    if docker exec -e "MYSQL_PWD=$dstpass" p07-d05-fresh-dst \
      mysql -uroot -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
  done
  test "$ready" -eq 1
  docker exec -e "MYSQL_PWD=$dstpass" p07-d05-fresh-dst \
    mysql -uroot -e 'CREATE DATABASE freshnewdb;'
  cat > "$tmp/dst.cnf" <<EOF
[client]
user=root
password=$dstpass
protocol=tcp
host=127.0.0.1
port=33072
EOF
  chmod 600 "$tmp/dst.cnf"

  python3 -B - "$tmp/src.cnf" "$tmp/dst.cnf" "$expected" <<'PY'
import sys
from pathlib import Path
from db_engine_conversion_fresh_target import inspect_fresh_native_target
a,b=Path(sys.argv[1]),Path(sys.argv[2])
r=inspect_fresh_native_target(a,b,"freshnewdb")
assert r["status"]=="FRESH_TARGET_READONLY_CANDIDATE"
assert r["source_engine"]=="MARIADB_11.8"
assert r["target_engine"]==sys.argv[3]
assert r["target_visible_inventory"]["visible_databases"]==1
assert not r["conversion_execution_enabled"]
assert not r["source_full_visibility_proven"]
assert not r["source_restorable_snapshot_proven"]
assert not r["target_database_ownership_proven"]
print("P07_D05_FRESH_REAL_NATIVE_"+sys.argv[3]+"_EMPTY_TARGET_READONLY=PASS")
PY

  docker exec -e "MYSQL_PWD=$dstpass" p07-d05-fresh-dst \
    mysql -uroot freshnewdb \
    -e 'CREATE TABLE existing_table(id INT PRIMARY KEY);'
  python3 -B - "$tmp/src.cnf" "$tmp/dst.cnf" <<'PY'
import sys
from pathlib import Path
from db_engine_conversion_fresh_target import inspect_fresh_native_target
from db_engine_conversion_discovery import EndpointInspectionBlocked
try:
    inspect_fresh_native_target(Path(sys.argv[1]),Path(sys.argv[2]),"freshnewdb")
except EndpointInspectionBlocked as exc:
    assert str(exc)=="D05_FRESH_TARGET_NOT_EMPTY",str(exc)
    print("P07_D05_FRESH_REAL_NATIVE_EXISTING_DATA_BLOCKED=PASS")
else:
    raise SystemExit("FRESH_TARGET_WITH_EXISTING_OBJECTS_WAS_ACCEPTED")
PY

  # The real Maria source must still contain its original two rows.
  test "$(docker exec -e "MYSQL_PWD=$srcpass" p07-d05-fresh-src \
     mariadb -uroot oldfixture --batch --skip-column-names \
     -e 'SELECT COUNT(*) FROM payload')" = 2
  echo P07_D05_FRESH_REAL_MARIA_SOURCE_PRESERVED=PASS
done
echo P07_D05_FRESH_TWO_NATIVE_TARGET_FAMILIES_AND_NEGATIVES=PASS
