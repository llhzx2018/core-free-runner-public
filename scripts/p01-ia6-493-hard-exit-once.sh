#!/usr/bin/env bash
set -Eeuo pipefail
# Hard-exit / journal recovery on disposable /tmp install only.
test "$#" -eq 0
test "$SOURCE" = '2.47.492'
test "$VERSION" = '2.47.493'
test -f "$REL/VF-Start-V$SOURCE-FULL.zip"
test -f "$ART/VF_Start_V${VERSION}_UPDATE.zip"
ROOT="$(mktemp -d /tmp/p01-ia6-hard-exit-XXXXXXXX)"
pid=''
cleanup(){
 if test -n "$pid"; then kill "$pid" >/dev/null 2>&1 || :; wait "$pid" 2>/dev/null || :; fi
 rm -rf "$ROOT"
}
trap cleanup EXIT
unzip -q "$REL/VF-Start-V$SOURCE-FULL.zip" -d "$ROOT/site"
unzip -q "$ART/VF_Start_V${VERSION}_UPDATE.zip" -d "$ROOT/repair"
REPAIR="$ROOT/repair/repair-v$VERSION.php"
test -f "$REPAIR"
test -f "$ROOT/site/setup.php"
php -S 127.0.0.1:18544 -t "$ROOT/site" >"$ROOT/server.log" 2>&1 &
pid="$!"
ready=0
for i in $(seq 1 50); do
 if curl -fsS -c "$ROOT/cookie" -b "$ROOT/cookie" http://127.0.0.1:18544/setup.php -o "$ROOT/setup.html" 2>/dev/null; then ready=1;break;fi
 sleep 0.2
done
test "$ready" = 1
csrf="$(python3 - "$ROOT/setup.html" <<'PY'
import pathlib,re,sys
data=pathlib.Path(sys.argv[1]).read_text()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',data)
assert m
print(m.group(1))
PY
)"
curl -fsS -c "$ROOT/cookie" -b "$ROOT/cookie" -X POST http://127.0.0.1:18544/setup.php \
 --data-urlencode "setup_csrf=$csrf" \
 --data-urlencode 'site_title=P01 Synthetic Atomic Hard Exit' \
 --data-urlencode 'admin_password=P01HardExitSynthetic2026!' \
 --data-urlencode 'admin_password_confirm=P01HardExitSynthetic2026!' \
 -o "$ROOT/installed.html"
test -f "$ROOT/site/app/.runtime.php"
kill "$pid" >/dev/null 2>&1 || :
wait "$pid" >/dev/null 2>&1 || :
pid=''
cat >"$ROOT/site/seed.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__.'/app/bootstrap.php';
$r=new VfRepository(vf_db());
$cat=$r->createCategory(['name'=>'IA6 crash recovery private category',
 'description'=>'','icon'=>'','is_private'=>1,'sort_order'=>0]);
$rec=$r->saveLink(null,['surface'=>'start','category_id'=>$cat,
 'title'=>'IA6 hard exit private sentinel',
 'url'=>'https://example.org/ia6-atomic-hard-exit',
 'description'=>'must persist through hard process death',
 'tags'=>['synthetic'],'is_private'=>1,'is_pending'=>0],'admin');
if((int)$rec['id']<1)throw new RuntimeException('Synthetic crash sentinel missing');
PHP
php "$ROOT/site/seed.php"
rm "$ROOT/site/seed.php"
(cd "$ROOT/site" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
cp "$REPAIR" "$ROOT/site/repair-v$VERSION.php"
php "$ROOT/site/repair-v$VERSION.php" --verify-source="$ROOT/site" |
 grep -Fq '"ok":true'
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$ROOT/site/repair-v$VERSION.php" \
 --run="$ROOT/site" >"$ROOT/hard-out" 2>"$ROOT/hard-err"
rc="$?"
set -e
test "$rc" -eq 97
test "$(tr -d '\r\n ' < "$ROOT/site/VERSION.txt")" = "$VERSION"
echo P01_IA6_493_HARD_EXIT_INJECTED=PASS
php "$ROOT/site/repair-v$VERSION.php" --run="$ROOT/site" >"$ROOT/resume-result.json"
grep -Fq '"ok":true' "$ROOT/resume-result.json"
grep -Fq '"interrupted_recovered":true' "$ROOT/resume-result.json"
test "$(tr -d '\r\n ' < "$ROOT/site/VERSION.txt")" = "$VERSION"
(cd "$ROOT/site" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
php -r 'require $argv[1]."/app/bootstrap.php";
$q=vf_db()->prepare("SELECT is_private,description FROM links WHERE url=?");
$q->execute(["https://example.org/ia6-atomic-hard-exit"]);
$a=$q->fetch(PDO::FETCH_ASSOC);
if(!is_array($a)||(int)$a["is_private"]!==1||
   $a["description"]!=="must persist through hard process death") exit(17);
echo "P01_IA6_493_PRIVATE_HARD_EXIT_SENTINEL=PASS\n";' "$ROOT/site"
echo P01_IA6_493_HARD_EXIT_RECOVER_RETRY=PASS
