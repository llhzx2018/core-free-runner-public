#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/tmp/p01-v2340-strict-fresh
ART=/tmp/p01-v2340-strict-fresh-evidence
PASS='P01V2340Fresh!2026'
PORT=18694
rm -rf "$ROOT" "$ART" && mkdir -p "$ART" && cp -a candidate/src "$ROOT"
php -d display_errors=1 -d log_errors=1 -S "127.0.0.1:${PORT}" -t "$ROOT" >"$ART/strict-fresh-server.log" 2>&1 & PID=$!
trap 'kill "$PID" >/dev/null 2>&1 || true' EXIT
for i in $(seq 1 60); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && break || true; sleep .25; done
COOKIE="$ART/strict-fresh.cookies"; PAGE="$ART/strict-fresh-setup.html"
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o "$PAGE"
CSRF=$(python3 - "$PAGE" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode "site_title=P01 V2.34 Strict Fresh" --data-urlencode "admin_password=$PASS" --data-urlencode "admin_password_confirm=$PASS" -o "$ART/strict-fresh-setup-post.html"
kill "$PID" >/dev/null 2>&1 || true; trap - EXIT
php "$ROOT/cli/verify.php" | tee "$ART/strict-fresh-verify.txt" | grep -Fx VERIFY_PASS=YES >/dev/null
php "$ROOT/cli/surface-verify.php" | tee "$ART/strict-fresh-surface.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES >/dev/null
test "$(cat "$ROOT/VERSION.txt")" = 2.34.0; grep -Fx "define('VF_VERSION', '2.34.0');" "$ROOT/app/bootstrap.php" >/dev/null
ROOT="$ROOT" php <<'PHP' | tee "$ART/strict-fresh-db.txt" | grep -Fx P01_V2340_STRICT_FRESH_DB=PASS >/dev/null
<?php
declare(strict_types=1);$root=getenv('ROOT');require $root.'/app/bootstrap.php';$db=vf_db();$h=(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn();$i=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn());$fk=$db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC);if($h!=='2026082901'||$i!=='ok'||count($fk)!==0)throw new RuntimeException('fresh database invalid');echo "P01_V2340_STRICT_FRESH_DB=PASS\n";
PHP
echo P01_V2340_STRICT_FRESH_INSTALL=PASS | tee "$ART/strict-fresh-verdict.txt"
