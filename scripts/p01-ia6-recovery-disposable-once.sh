#!/usr/bin/env bash
set -Eeuo pipefail
# Public synthetic-only suite; never accepts Production paths or credentials.
test "$#" -eq 2
candidate="$(cd "$1" && pwd)"
baseline="$(cd "$2" && pwd)"
test -f "$candidate/tests/integration/p01_ia6_disaster_roundtrip_disposable.php"
test -f "$baseline/src/VERSION.txt"
test "$candidate" != "$baseline"

work="$(mktemp -d /tmp/p01-ia6-source-rollback-XXXXXXXX)"
disaster="$(mktemp -d /tmp/p01-ia6-disaster-parity-XXXXXXXX)"
interrupted="$(mktemp -d /tmp/p01-ia6-r11-XXXXXXXX)"
pids=()
cleanup() {
  for pid in $(jobs -pr); do kill "$pid" 2>/dev/null || :; done
  rm -rf "$work" "$disaster" "$interrupted"
}
trap cleanup EXIT

install_fixture() {
  local source="$1" root="$2" port="$3" title="$4"
  cp -a "$source/src/." "$root/"
  php -S "127.0.0.1:$port" -t "$root" >"$root/server.log" 2>&1 &
  local pid=$!
  pids+=("$pid")
  local base="http://127.0.0.1:$port" cookie="$root/cookie"
  local ok=''
  for i in $(seq 1 40); do
    if curl -fsS -c "$cookie" -b "$cookie" "$base/setup.php" -o "$root/setup.html" 2>/dev/null; then
      ok=1
      break
    fi
    sleep 0.2
  done
  test "$ok" = 1
  local csrf
  csrf="$(python3 - "$root/setup.html" <<'PY'
import pathlib,re,sys
text=pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',text)
assert m
print(m.group(1))
PY
)"
  curl -fsS -c "$cookie" -b "$cookie" -X POST "$base/setup.php" \
    --data-urlencode "setup_csrf=$csrf" \
    --data-urlencode "site_title=$title" \
    --data-urlencode "admin_password=P01SyntheticRecovery2026!" \
    --data-urlencode "admin_password_confirm=P01SyntheticRecovery2026!" \
    -o "$root/installed.html" >/dev/null
  kill "$pid" 2>/dev/null || :
  wait "$pid" 2>/dev/null || :
  test -f "$root/app/.runtime.php"
  (cd "$root" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
}

install_fixture "$candidate" "$disaster" 18963 "IA6 disposable disaster roundtrip"
VF_E2E_RUNTIME_ROOT="$disaster" VF_IA6_DISPOSABLE_ACK=IA6-DISASTER-DISPOSABLE-ONLY \
  php "$candidate/tests/integration/p01_ia6_disaster_roundtrip_disposable.php"
echo P01_IA6_DISASTER_ROUNDTRIP_EXACT_SOURCE=PASS

# Original protected routes: local synthetic installation, denial-only browser HTTP.
test "${P01_TEST_ORIGIN:-}" = http://127.0.0.1:18631
test -f "$candidate/tests/integration/p01_ia6_four_fallbacks_http_browser.mjs"
php -S 127.0.0.1:18631 -t "$disaster" >"$disaster/fallback-server.log" 2>&1 &
fallback_pid=$!
pids+=("$fallback_pid")
fallback_ready=0
for i in $(seq 1 40); do
  if curl -sS --max-time 2 -o /dev/null "$P01_TEST_ORIGIN/setup.php" 2>/dev/null; then
    fallback_ready=1
    break
  fi
  sleep 0.25
done
test "$fallback_ready" = 1
P01_TEST_PASSWORD=P01SyntheticRecovery2026! \
P01_TEST_ORIGIN=http://127.0.0.1:18631 \
node "$candidate/tests/integration/p01_ia6_four_fallbacks_http_browser.mjs"
echo P01_IA6_FOUR_FALLBACKS_BROWSER=PASS
kill "$fallback_pid" 2>/dev/null || :
wait "$fallback_pid" 2>/dev/null || :


install_fixture "$candidate" "$interrupted" 18964 "IA6 disposable interrupted restore"
VF_E2E_RUNTIME_ROOT="$interrupted" \
  php "$candidate/tests/integration/p01_ia6_interrupted_restore_disposable.php"
echo P01_IA6_INTERRUPTED_RESTORE_ROLLBACK_EXACT_SOURCE=PASS

install_fixture "$baseline" "$work" 18965 "IA6 synthetic existing installation"
cat >"$work/seed.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__.'/app/bootstrap.php';
$repo=new VfRepository(vf_db());
$cat=$repo->createCategory(['name'=>'Overlay Synthetic Private','description'=>'',
 'icon'=>'','is_private'=>1,'sort_order'=>0]);
$link=$repo->saveLink(null,['surface'=>'start','category_id'=>$cat,
 'title'=>'Private persistence marker','url'=>'https://example.org/ia6-source-rollback',
 'description'=>'must preserve','tags'=>['synthetic'],'is_private'=>1,'is_pending'=>0]);
if((int)($link['id']??0)<1)throw new RuntimeException('Missing synthetic sentinel');
PHP
php "$work/seed.php"
rm "$work/seed.php"
check_sentinel() {
  php -r 'require $argv[1]."/app/bootstrap.php";$s=vf_db()->prepare("SELECT is_private FROM links WHERE url=?");$s->execute(["https://example.org/ia6-source-rollback"]);if((int)$s->fetchColumn()!==1)exit(11);echo "P01_IA6_PRIVATE_SENTINEL_PRESERVED=PASS\n";' "$work"
}
check_sentinel
cp -a "$candidate/src/." "$work/"
(cd "$work" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
check_sentinel
for name in surface-manager.php data-safety.php update.php update-credential.php; do
  cmp -s "$candidate/src/$name" "$work/$name"
done
echo P01_IA6_EXISTING_INSTALL_SOURCE_OVERLAY=PASS
# A source restoration proof, NOT proof of Atomic installer rollback.
cp -a "$baseline/src/." "$work/"
(cd "$work" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
check_sentinel
for name in surface-manager.php data-safety.php update.php update-credential.php; do
  cmp -s "$baseline/src/$name" "$work/$name"
done
echo P01_IA6_SOURCE_RESTORATION_AND_OWNER_DATA=PASS
echo P01_IA6_ATOMIC_UPDATER_ROLLBACK=NOT_TESTED_BY_THIS_SUITE
