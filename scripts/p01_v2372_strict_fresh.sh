#!/usr/bin/env bash
set -Eeuo pipefail
ARTIFACT_ID=9833750309
ARTIFACT_RUN=33597034240
FORMAL_SOURCE=1f5a16796511620760a45cb81b3c8019b91e505b
RUNTIME_TREE=70b627513327aee0a37fae245b0f4042ad69b5a4
EVID=/tmp/p01-v2372-strict-fresh-evidence
ROOT=/tmp/p01-v2372-frozen
FRESH=/tmp/p01-v2372-strict-fresh-install
UPGRADE=/tmp/p01-v2372-strict-upgrade
rm -rf "$EVID" "$ROOT" "$FRESH" "$UPGRADE"; mkdir -p "$EVID" "$ROOT"

test "$(gh api repos/llhzx2018/core-free-runner-public/actions/runs/$ARTIFACT_RUN --jq .conclusion)" = success
META="$(gh api repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID)"
test "$(jq -r .workflow_run.id <<<"$META")" = "$ARTIFACT_RUN"
test "$(jq -r .expired <<<"$META")" = false
test "$(jq -r .digest <<<"$META")" = 'sha256:648b10eea296360dd600cf38d8eaf3c5fc4eb2d14a8936be0e03fce28366da9b'
printf '%s\n' "$META" > "$EVID/artifact-api.json"
gh api repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID/zip > "$ROOT/artifact.zip"
unzip -q "$ROOT/artifact.zip" -d "$ROOT/unpacked"
FULL="$(find "$ROOT/unpacked" -type f -name 'VF-Start-V2.37.2-FULL.zip' -print -quit)"
test -n "$FULL"; ASSETS="$(dirname "$FULL")"
expected=$(cat <<'EOF'
P01-V2.37.2-FORMAL.json
P01-V2.37.2-RELEASE-NOTES.md
VF-Start-V2.37.2-FULL.zip
VF-Start-V2.37.2-FULL.zip.sha256
VF_Start_V2.37.2_UPDATE.zip
VF_Start_V2.37.2_UPDATE.zip.sha256
repair-v2.37.2.php
repair-v2.37.2.php.sha256
EOF
)
test "$(find "$ASSETS" -maxdepth 1 -type f -printf '%f\n' | sort)" = "$expected"
(cd "$ASSETS" && sha256sum -c VF-Start-V2.37.2-FULL.zip.sha256 && sha256sum -c VF_Start_V2.37.2_UPDATE.zip.sha256 && sha256sum -c repair-v2.37.2.php.sha256) | tee "$EVID/inner-sha-check.txt"
jq -e '.status=="FORMAL_ARTIFACT_PASS" and .version=="2.37.2" and .source_version=="2.37.1" and .schema=="2026082901" and .formal_source=="1f5a16796511620760a45cb81b3c8019b91e505b" and .runtime_tree=="70b627513327aee0a37fae245b0f4042ad69b5a4" and .schema_change==false and .migration==null' "$ASSETS/P01-V2.37.2-FORMAL.json" >/dev/null
php -l "$ASSETS/repair-v2.37.2.php" >/dev/null
php "$ASSETS/repair-v2.37.2.php" --self-test | tee "$EVID/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null

mkdir -p "$FRESH"; unzip -q "$FULL" -d "$FRESH"
test "$(cat "$FRESH/VERSION.txt")" = 2.37.2
grep -Fx "define('VF_VERSION', '2.37.2');" "$FRESH/app/bootstrap.php" >/dev/null
find "$FRESH" -type f -name '*.php' -print0 | xargs -0 -n1 php -l > "$EVID/fresh-php-lint.txt"
find "$FRESH/assets" -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check
php -S 127.0.0.1:18481 -t "$FRESH" >"$EVID/fresh-server.log" 2>&1 & FPID=$!
trap 'kill $FPID 2>/dev/null || true' EXIT
COOKIE="$EVID/fresh.cookies"
for i in $(seq 1 80); do curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18481/setup.php -o "$EVID/fresh-setup.html" && break; sleep .25; done
CSRF=$(python3 - "$EVID/fresh-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18481/setup.php --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=V2372 Fresh' --data-urlencode 'admin_password=V2372Fresh!2026' --data-urlencode 'admin_password_confirm=V2372Fresh!2026' -o "$EVID/fresh-setup-post.html"
kill "$FPID"; trap - EXIT
FRESH="$FRESH" php <<'PHP' | tee "$EVID/fresh-db.txt"
<?php require getenv('FRESH').'/app/bootstrap.php'; $d=vf_db(); if(strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(1); if($d->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))exit(2); echo "P01_V2372_FRESH_DB=PASS\n";
PHP
php "$FRESH/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES
php "$FRESH/cli/surface-verify.php" | tee "$EVID/fresh-surface.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES

cp -a production/src "$UPGRADE"
php -S 127.0.0.1:18482 -t "$UPGRADE" >"$EVID/upgrade-server.log" 2>&1 & UPID=$!
trap 'kill $UPID 2>/dev/null || true' EXIT
COOKIE2="$EVID/upgrade.cookies"
for i in $(seq 1 80); do curl -fsS -c "$COOKIE2" -b "$COOKIE2" http://127.0.0.1:18482/setup.php -o "$EVID/upgrade-setup.html" && break; sleep .25; done
CSRF2=$(python3 - "$EVID/upgrade-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE2" -b "$COOKIE2" -X POST http://127.0.0.1:18482/setup.php --data-urlencode "setup_csrf=$CSRF2" --data-urlencode 'site_title=V2372 Upgrade' --data-urlencode 'admin_password=V2372Upgrade!2026' --data-urlencode 'admin_password_confirm=V2372Upgrade!2026' -o "$EVID/upgrade-setup-post.html"
UPGRADE="$UPGRADE" php <<'PHP' | tee "$EVID/seed.txt"
<?php require getenv('UPGRADE').'/app/bootstrap.php'; $r=new VfRepository(vf_db()); $c=$r->createCategory(['name'=>'V2372 Preserve','description'=>'','is_private'=>false]); for($i=1;$i<=40;$i++)$r->saveLink(null,['category_id'=>$c,'title'=>'Preserve '.$i,'url'=>'https://example.com/v2372-'.$i,'description'=>'hotfix','tags'=>'v2372','is_private'=>$i%5===0,'is_favorite'=>$i<=4],'manual'); echo "P01_V2372_SEED_40=PASS\n";
PHP
kill "$UPID"; trap - EXIT
php "$ASSETS/repair-v2.37.2.php" --verify-source="$UPGRADE" | tee "$EVID/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$ASSETS/repair-v2.37.2.php" --run="$UPGRADE" | tee "$EVID/atomic-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
test "$(cat "$UPGRADE/VERSION.txt")" = 2.37.2
grep -Fx "define('VF_VERSION', '2.37.2');" "$UPGRADE/app/bootstrap.php" >/dev/null
UPGRADE="$UPGRADE" php <<'PHP' | tee "$EVID/preservation.txt"
<?php require getenv('UPGRADE').'/app/bootstrap.php'; $d=vf_db(); if((int)$d->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn()!==40)exit(1); if((int)$d->query("SELECT COUNT(*) FROM links WHERE is_favorite=1 AND lifecycle_state='active'")->fetchColumn()!==4)exit(2); if(strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(3); if($d->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))exit(4); echo "P01_V2372_DATA_PRESERVATION=PASS\n";
PHP
php "$UPGRADE/cli/verify.php" | tee "$EVID/upgrade-verify.txt" | grep -Fx VERIFY_PASS=YES
php "$UPGRADE/cli/surface-verify.php" | tee "$EVID/upgrade-surface.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES
php "$ASSETS/repair-v2.37.2.php" --run="$UPGRADE" | tee "$EVID/idempotent.json" | jq -e '.ok==true and .already_current==true' >/dev/null

# IYF regression against the runtime bytes actually installed from frozen FULL.
TOKEN='27Qr2mVwuzJ'; M="https://mview.iyf.tv/play/${TOKEN}"; W="https://www.iyf.tv/play/${TOKEN}"
grep -F 'mview.iyf.tv' "$FRESH/app/ResourceCoverCache.php" >/dev/null
grep -F 'vf-cover-retry:v3:' "$FRESH/assets/workspace.js" >/dev/null
curl -fsSL --max-time 20 -A 'VF-Start/2.37.2 CoverCache' "$M" -o /tmp/v2372-iyf-m.html
curl -fsSL --max-time 20 -A 'VF-Start/2.37.2 CoverCache' "$W" -o /tmp/v2372-iyf-w.html
test "$(grep -oi 'og:image' /tmp/v2372-iyf-m.html | wc -l)" = 0
test "$(grep -oi 'og:image' /tmp/v2372-iyf-w.html | wc -l)" -ge 1
php -r "require '$FRESH/app/ResourceCoverCache.php'; \$c=VfResourceCoverCache::extractCoverCandidates(file_get_contents('/tmp/v2372-iyf-w.html'),'$W'); if(!isset(\$c[0])||!str_contains(\$c[0],'static.iyf.tv')){var_export(\$c);exit(31);} echo \$c[0],PHP_EOL;" | tee "$EVID/iyf-first.txt"
POSTER="$(tail -n1 "$EVID/iyf-first.txt")"
curl -fsSL --max-time 20 -A 'VF-Start/2.37.2 CoverCache' "$POSTER" -o /tmp/v2372-iyf-poster.bin
file --mime-type -b /tmp/v2372-iyf-poster.bin | grep -Eq '^image/(jpeg|png|webp|gif)$'

sha256sum "$ASSETS"/* | sort > "$EVID/frozen-assets-sha256.txt"
printf 'P01_V2372_STRICT_FRESH=PASS\nFORMAL_ARTIFACT_RUN=%s\nFORMAL_ARTIFACT_ID=%s\nFORMAL_SOURCE=%s\nRUNTIME_TREE=%s\nFRESH_INSTALL=PASS\nATOMIC_2371_TO_2372=PASS\nDATA_PRESERVATION=PASS\nIYF_REAL_COVER=PASS\nREBUILD=NO\nOWNER_PRODUCTION_WRITE=NO\n' "$ARTIFACT_RUN" "$ARTIFACT_ID" "$FORMAL_SOURCE" "$RUNTIME_TREE" | tee "$EVID/verdict.txt"
