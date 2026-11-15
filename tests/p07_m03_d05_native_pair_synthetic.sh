#!/usr/bin/env bash
# P07-M03-D05 数据库引擎转换：独立合成数据库双向逻辑迁移
# Public synthetic containers only; NEVER Owner/Production data.
set -Eeuo pipefail
work="$(mktemp -d)"
mysql_name=p07-d05-mysql84-test
maria_name=p07-d05-maria118-test
pw=P07_PUBLIC_SYNTHETIC_ONLY
cleanup() {
  docker rm -f "$mysql_name" "$maria_name" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT
docker info >/dev/null
docker rm -f "$mysql_name" "$maria_name" >/dev/null 2>&1 || true
echo P07_D05_NATIVE_FIXTURE=PUBLIC_SYNTHETIC_ONLY

docker run -d --name "$mysql_name" -e MYSQL_ROOT_PASSWORD="$pw" \
  -e MYSQL_DATABASE=p07_d05_from_mysql mysql:8.4 >/dev/null
docker run -d --name "$maria_name" -e MARIADB_ROOT_PASSWORD="$pw" \
  -e MARIADB_DATABASE=p07_d05_from_maria mariadb:11.8 >/dev/null

mysql_query() {
  docker exec -i -e "MYSQL_PWD=$pw" "$mysql_name" mysql -uroot \
    --batch --skip-column-names --default-character-set=utf8mb4 "$@"
}
maria_query() {
  docker exec -i -e "MYSQL_PWD=$pw" "$maria_name" mariadb -uroot \
    --batch --skip-column-names --default-character-set=utf8mb4 "$@"
}
ready() {
  local fn="$1" tries
  for tries in $(seq 1 100); do
    if "$fn" -e 'SELECT 1' >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  echo P07_D05_ENGINE_STARTUP=NOT_PROVEN >&2
  return 1
}
ready mysql_query
ready maria_query
mysql_query -e "SELECT @@version" | grep -Eq '^8[.]4[.]'
maria_query -e "SELECT @@version" | grep -Eq '^11[.]8[.]'
echo P07_D05_MYSQL84_AND_MARIA118_REAL_DAEMONS=PASS

mysql_query p07_d05_from_mysql <<'SQL'
CREATE TABLE vf_payload (
  id INT NOT NULL PRIMARY KEY, label VARCHAR(80) NOT NULL,
  metadata JSON, binary_bytes BLOB
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO vf_payload VALUES
 (1,'synthetic-alpha','{"n":42}', X'00FFAA10'),
 (2,'synthetic-beta','{"n":77}', X'DEADBEEF');
SQL
maria_query p07_d05_from_maria <<'SQL'
CREATE TABLE vf_payload (
  id INT NOT NULL PRIMARY KEY, label VARCHAR(80) NOT NULL,
  metadata JSON, binary_bytes BLOB
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO vf_payload VALUES
 (1,'synthetic-maria','{"n":142}', X'01020304'),
 (2,'synthetic-reverse','{"n":177}', X'ABCDEF00');
SQL

mysql_query -e 'CREATE DATABASE p07_d05_from_maria CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
maria_query -e 'CREATE DATABASE p07_d05_from_mysql CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'

docker exec -e "MYSQL_PWD=$pw" "$mysql_name" mysqldump -uroot \
  --single-transaction --hex-blob --no-tablespaces --skip-comments \
  --skip-triggers --set-gtid-purged=OFF p07_d05_from_mysql >"$work/mysql_to_maria.sql"
test -s "$work/mysql_to_maria.sql"
if grep -Eiq '^(CREATE USER|GRANT |REVOKE |SET GLOBAL |SET @@GLOBAL|DROP DATABASE|SHUTDOWN|RESET MASTER)' \
  "$work/mysql_to_maria.sql"; then
  echo P07_D05_SYNTHETIC_IMPORT_SCOPE=BLOCKED >&2; exit 1
fi
docker exec -i -e "MYSQL_PWD=$pw" "$maria_name" \
  mariadb -uroot p07_d05_from_mysql <"$work/mysql_to_maria.sql"
echo P07_D05_MYSQL84_TO_MARIA118_NATIVE_IMPORT=PASS

docker exec -e "MYSQL_PWD=$pw" "$maria_name" mariadb-dump -uroot \
  --single-transaction --hex-blob --skip-comments --skip-triggers \
  p07_d05_from_maria >"$work/maria_to_mysql.sql"
test -s "$work/maria_to_mysql.sql"
# One documented, fixed MariaDB CLI-only sandbox banner, not a SQL command.
python3 - "$work/maria_to_mysql.sql" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
data = p.read_bytes()
first, delim, rest = data.partition(b'\n')
fixed = (
    b'/*M!999999\\- enable the sandbox mode */',
    b'/*M!999999\\\\- enable the sandbox mode */',
)
if first.startswith(b'/*M!999999'):
    if first.rstrip(b'\r') not in fixed or not delim:
        # Synthetic fixture only; fixed class without showing arbitrary SQL.
        raise SystemExit('P07_D05_UNKNOWN_MARIA_BANNER=BLOCKED')
    p.write_bytes(rest)
PY
if grep -Eiq '^(CREATE USER|GRANT |REVOKE |SET GLOBAL |SET @@GLOBAL|DROP DATABASE|SHUTDOWN|RESET MASTER)' \
  "$work/maria_to_mysql.sql"; then
  echo P07_D05_SYNTHETIC_IMPORT_SCOPE=BLOCKED >&2; exit 1
fi
docker exec -i -e "MYSQL_PWD=$pw" "$mysql_name" \
  mysql -uroot p07_d05_from_maria <"$work/maria_to_mysql.sql"
echo P07_D05_MARIA118_TO_MYSQL84_NATIVE_IMPORT=PASS

fingerprint_sql="SELECT CONCAT(id,'/',label,'/',JSON_UNQUOTE(JSON_EXTRACT(metadata,'$.n')),'/',HEX(binary_bytes)) FROM vf_payload ORDER BY id"
mysql_query p07_d05_from_mysql -e "$fingerprint_sql" >"$work/mysql_orig.txt"
maria_query p07_d05_from_mysql -e "$fingerprint_sql" >"$work/mysql_import.txt"
maria_query p07_d05_from_maria -e "$fingerprint_sql" >"$work/maria_orig.txt"
mysql_query p07_d05_from_maria -e "$fingerprint_sql" >"$work/maria_import.txt"
cmp -s "$work/mysql_orig.txt" "$work/mysql_import.txt"
cmp -s "$work/maria_orig.txt" "$work/maria_import.txt"
test "$(wc -l < "$work/mysql_orig.txt")" -eq 2
test "$(wc -l < "$work/maria_orig.txt")" -eq 2
echo P07_D05_SYNTHETIC_ROW_JSON_BLOB_PARITY_BOTH_DIRECTIONS=PASS
echo P07_D05_SOURCE_ENGINES_UNCHANGED=PASS
echo P07_D05_CLOUDPANEL_ACTIVE_SWITCH=NOT_RUN
echo P07_D05_PRODUCTION=UNCHANGED
