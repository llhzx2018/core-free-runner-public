#!/usr/bin/env bash
set -Eeuo pipefail
ARTIFACT_ID=9832727218
ARTIFACT_RUN=33593977785
FORMAL_SOURCE=0838e47ec49bb961131da81b0b314ebf77f1e126
RUNTIME_TREE=37f3be264892224e2f3041564844c2aebd471064
EVID=/tmp/p01-v2371-strict-fresh-evidence
ROOT=/tmp/p01-v2371-frozen
FRESH=/tmp/p01-v2371-strict-fresh-install
UPGRADE=/tmp/p01-v2371-strict-upgrade
rm -rf "$EVID" "$ROOT" "$FRESH" "$UPGRADE"; mkdir -p "$EVID" "$ROOT"

# Download exactly the frozen artifact from the PASS run; no builder is invoked here.
test "$(gh api repos/llhzx2018/core-free-runner-public/actions/runs/$ARTIFACT_RUN --jq .conclusion)" = success
META="$(gh api repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID)"
test "$(jq -r .workflow_run.id <<<"$META")" = "$ARTIFACT_RUN"
test "$(jq -r .expired <<<"$META")" = false
printf '%s\n' "$META" > "$EVID/artifact-api.json"
gh api repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID/zip > "$ROOT/artifact.zip"
unzip -q "$ROOT/artifact.zip" -d "$ROOT/unpacked"
FULL="$(find "$ROOT/unpacked" -type f -name 'VF-Start-V2.37.1-FULL.zip' -print -quit)"
test -n "$FULL"
ASSETS="$(dirname "$FULL")"

expected=$(cat <<'EOF'
P01-V2.37.1-FORMAL.json
P01-V2.37.1-RELEASE-NOTES.md
VF-Start-V2.37.1-FULL.zip
VF-Start-V2.37.1-FULL.zip.sha256
VF_Start_V2.37.1_UPDATE.zip
VF_Start_V2.37.1_UPDATE.zip.sha256
repair-v2.37.1.php
repair-v2.37.1.php.sha256
EOF
)
test "$(find "$ASSETS" -maxdepth 1 -type f -printf '%f\n' | sort)" = "$expected"
(cd "$ASSETS" && sha256sum -c VF-Start-V2.37.1-FULL.zip.sha256 && sha256sum -c VF_Start_V2.37.1_UPDATE.zip.sha256 && sha256sum -c repair-v2.37.1.php.sha256) | tee "$EVID/inner-sha-check.txt"
jq -e '.status=="FORMAL_ARTIFACT_PASS" and .version=="2.37.1" and .source_version=="2.37.0" and .schema=="2026082901" and .formal_source=="0838e47ec49bb961131da81b0b314ebf77f1e126" and .runtime_tree=="37f3be264892224e2f3041564844c2aebd471064" and .schema_change==false and .migration==null' "$ASSETS/P01-V2.37.1-FORMAL.json" >/dev/null
php -l "$ASSETS/repair-v2.37.1.php" >/dev/null
php "$ASSETS/repair-v2.37.1.php" --self-test | tee "$EVID/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null

# Strict Fresh Install from frozen FULL bytes.
mkdir -p "$FRESH"; unzip -q "$FULL" -d "$FRESH"
test "$(cat "$FRESH/VERSION.txt")" = 2.37.1
grep -Fx "define('VF_VERSION', '2.37.1');" "$FRESH/app/bootstrap.php" >/dev/null
find "$FRESH" -type f -name '*.php' -print0 | xargs -0 -n1 php -l > "$EVID/fresh-php-lint.txt"
find "$FRESH/assets" -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check
php -S 127.0.0.1:18471 -t "$FRESH" >"$EVID/fresh-server.log" 2>&1 & FPID=$!
trap 'kill $FPID 2>/dev/null || true' EXIT
COOKIE="$EVID/fresh.cookies"
for i in $(seq 1 80); do curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18471/setup.php -o "$EVID/fresh-setup.html" && break; sleep .25; done
CSRF=$(python3 - "$EVID/fresh-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18471/setup.php --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=V2371 Fresh' --data-urlencode 'admin_password=V2371Fresh!2026' --data-urlencode 'admin_password_confirm=V2371Fresh!2026' -o "$EVID/fresh-setup-post.html"
kill "$FPID"; trap - EXIT
FRESH="$FRESH" php <<'PHP' | tee "$EVID/fresh-db.txt"
<?php require getenv('FRESH').'/app/bootstrap.php'; $d=vf_db(); if(strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(1); if($d->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))exit(2); echo "P01_V2371_FRESH_DB=PASS\n";
PHP
php "$FRESH/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES
php "$FRESH/cli/surface-verify.php" | tee "$EVID/fresh-surface.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES

# Actual V2.37.0 -> V2.37.1 Atomic from frozen repair bytes, with user data preservation.
cp -a production/src "$UPGRADE"
php -S 127.0.0.1:18472 -t "$UPGRADE" >"$EVID/upgrade-server.log" 2>&1 & UPID=$!
trap 'kill $UPID 2>/dev/null || true' EXIT
COOKIE2="$EVID/upgrade.cookies"
for i in $(seq 1 80); do curl -fsS -c "$COOKIE2" -b "$COOKIE2" http://127.0.0.1:18472/setup.php -o "$EVID/upgrade-setup.html" && break; sleep .25; done
CSRF2=$(python3 - "$EVID/upgrade-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE2" -b "$COOKIE2" -X POST http://127.0.0.1:18472/setup.php --data-urlencode "setup_csrf=$CSRF2" --data-urlencode 'site_title=V2371 Upgrade' --data-urlencode 'admin_password=V2371Upgrade!2026' --data-urlencode 'admin_password_confirm=V2371Upgrade!2026' -o "$EVID/upgrade-setup-post.html"
UPGRADE="$UPGRADE" php <<'PHP' | tee "$EVID/seed.txt"
<?php require getenv('UPGRADE').'/app/bootstrap.php'; $r=new VfRepository(vf_db()); $c=$r->createCategory(['name'=>'V2371 Preserve','description'=>'','is_private'=>false]); for($i=1;$i<=40;$i++)$r->saveLink(null,['category_id'=>$c,'title'=>'Preserve '.$i,'url'=>'https://example.com/v2371-'.$i,'description'=>'hotfix','tags'=>'v2371','is_private'=>$i%5===0,'is_favorite'=>$i<=4],'manual'); echo "P01_V2371_SEED_40=PASS\n";
PHP
kill "$UPID"; trap - EXIT
php "$ASSETS/repair-v2.37.1.php" --verify-source="$UPGRADE" | tee "$EVID/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$ASSETS/repair-v2.37.1.php" --run="$UPGRADE" | tee "$EVID/atomic-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
test "$(cat "$UPGRADE/VERSION.txt")" = 2.37.1
grep -Fx "define('VF_VERSION', '2.37.1');" "$UPGRADE/app/bootstrap.php" >/dev/null
UPGRADE="$UPGRADE" php <<'PHP' | tee "$EVID/preservation.txt"
<?php require getenv('UPGRADE').'/app/bootstrap.php'; $d=vf_db(); if((int)$d->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn()!==40)exit(1); if((int)$d->query("SELECT COUNT(*) FROM links WHERE is_favorite=1 AND lifecycle_state='active'")->fetchColumn()!==4)exit(2); if(strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(3); if($d->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))exit(4); echo "P01_V2371_DATA_PRESERVATION=PASS\n";
PHP
php "$UPGRADE/cli/verify.php" | tee "$EVID/upgrade-verify.txt" | grep -Fx VERIFY_PASS=YES
php "$UPGRADE/cli/surface-verify.php" | tee "$EVID/upgrade-surface.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES
php "$ASSETS/repair-v2.37.1.php" --run="$UPGRADE" | tee "$EVID/idempotent.json" | jq -e '.ok==true and .already_current==true' >/dev/null

# Hotfix regression on the bytes actually installed from FULL.
PAGE='https://xiaoheimi.cc/index.php/vod/detail/id/220543.html'
curl -fsSL --max-time 20 -A 'VF-Start/2.37.1 CoverCache' "$PAGE" -o /tmp/v2371-strict-xhm.html
php -r "require '$FRESH/app/ResourceCoverCache.php'; \$c=VfResourceCoverCache::extractCoverCandidates(file_get_contents('/tmp/v2371-strict-xhm.html'),'$PAGE'); if(!isset(\$c[0])||!str_contains(\$c[0],'/upload/vod/')){var_export(\$c);exit(31);} echo \$c[0],PHP_EOL;" | tee "$EVID/xiaoheimi-first.txt"
POSTER="$(tail -n1 "$EVID/xiaoheimi-first.txt")"
curl -fsSL --max-time 20 -A 'VF-Start/2.37.1 CoverCache' "$POSTER" -o /tmp/v2371-strict-poster.bin
file --mime-type -b /tmp/v2371-strict-poster.bin | grep -Eq '^image/(jpeg|png|webp)$'

sha256sum "$ASSETS"/* | sort > "$EVID/frozen-assets-sha256.txt"
printf 'P01_V2371_STRICT_FRESH=PASS\nFORMAL_ARTIFACT_RUN=%s\nFORMAL_ARTIFACT_ID=%s\nFORMAL_SOURCE=%s\nRUNTIME_TREE=%s\nFRESH_INSTALL=PASS\nATOMIC_2370_TO_2371=PASS\nDATA_PRESERVATION=PASS\nREAL_COVER=PASS\nREBUILD=NO\nOWNER_PRODUCTION_WRITE=NO\n' "$ARTIFACT_RUN" "$ARTIFACT_ID" "$FORMAL_SOURCE" "$RUNTIME_TREE" | tee "$EVID/verdict.txt"
