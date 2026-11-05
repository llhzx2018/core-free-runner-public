#!/usr/bin/env bash
set -Eeuo pipefail
test "$#" -eq 1
candidate="$(cd "$1" && pwd)"
test "${P01_TEST_ORIGIN:-}" = 'http://127.0.0.1:18631'
test -f "$candidate/src/assets/frontstage-resource-advanced.js"
test -f "$candidate/src/assets/frontstage-inventory-bulk.js"
work="$(mktemp -d /tmp/p01-ia6-native-resource-XXXXXXXX)"
pid=''
cleanup(){ if test -n "$pid"; then kill "$pid" 2>/dev/null || :; wait "$pid" 2>/dev/null || :; fi; rm -rf "$work"; }
trap cleanup EXIT
cp -a "$candidate/src/." "$work/"
php -S 127.0.0.1:18631 -t "$work" >"$work/server.log" 2>&1 &
pid="$!"
ok=0
for i in $(seq 1 50); do
 if curl -fsS -c "$work/cookie" -b "$work/cookie" "$P01_TEST_ORIGIN/setup.php" -o "$work/setup.html" 2>/dev/null; then ok=1;break;fi
 sleep 0.2
done
test "$ok" = 1
csrf="$(python3 - "$work/setup.html" <<'PY'
import pathlib,re,sys
s=pathlib.Path(sys.argv[1]).read_text()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)"
curl -fsS -c "$work/cookie" -b "$work/cookie" -X POST "$P01_TEST_ORIGIN/setup.php" \
  --data-urlencode "setup_csrf=$csrf" \
  --data-urlencode 'site_title=P01 Synthetic Native Resources' \
  --data-urlencode 'admin_password=P01SyntheticRecovery2026!' \
  --data-urlencode 'admin_password_confirm=P01SyntheticRecovery2026!' \
  -o "$work/installed.html"
test -f "$work/app/.runtime.php"
cat >"$work/seed.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__.'/app/bootstrap.php';
$r=new VfRepository(vf_db());
$category=$r->createCategory(['name'=>'IA6 synthetic grouping','description'=>'','icon'=>'','is_private'=>0,'sort_order'=>0]);
$a=$r->saveLink(null,[
 'surface'=>'start','category_id'=>$category,'title'=>'IA6 Native Advanced Synthetic',
 'url'=>'https://example.org/ia6-advanced-synthetic','description'=>'synthetic',
 'tags'=>[],'is_private'=>1,'is_pending'=>0
],'admin');
$b=$r->saveLink(null,[
 'surface'=>'start','category_id'=>$category,'title'=>'IA6 Native Bulk Synthetic',
 'url'=>'https://example.org/ia6-bulk-synthetic','description'=>'synthetic',
 'tags'=>[],'is_private'=>0,'is_pending'=>0
],'admin');
if((int)$a['id']<=0||(int)$b['id']<=0)throw new RuntimeException('Synthetic fixture missing ids');
file_put_contents(__DIR__.'/synthetic-ids.json',json_encode(['advanced'=>(int)$a['id'],'bulk'=>(int)$b['id']]));
PHP
php "$work/seed.php"
rm "$work/seed.php"
(cd "$work" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
P01_TEST_PASSWORD='P01SyntheticRecovery2026!' \
  node scripts/p01-ia6-resource-native-browser-once.cjs "$candidate" "$work/synthetic-ids.json"
(cd "$work" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
echo P01_IA6_NATIVE_RESOURCE_AFTER_WRITE_INTEGRITY=PASS
