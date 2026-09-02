#!/usr/bin/env bash
set -Eeuo pipefail
ARTIFACT_ID=9835093365
ARTIFACT_RUN=33600796537
FORMAL_SOURCE=cec95e310771feb6813a51c7ee3340884295ee38
RUNTIME_TREE=e56459ebadc120c749cc5336821d762001db5218
ARTIFACT_SHA=1ea846d2d30b6be3daf46f9cc0cfb9185d5fd6d22bd63569547a8d203c67be1d
ROOT=/tmp/p01-v2373-frozen
EVID=/tmp/p01-v2373-strict-fresh-evidence
FRESH=/tmp/p01-v2373-strict-fresh-install
UPGRADE=/tmp/p01-v2373-strict-upgrade
rm -rf "$ROOT" "$EVID" "$FRESH" "$UPGRADE" candidate
mkdir -p "$ROOT" "$EVID"

test "$(gh api repos/llhzx2018/core-free-runner-public/actions/runs/$ARTIFACT_RUN --jq .conclusion)" = success
META="$(gh api repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID)"
test "$(jq -r .workflow_run.id <<<"$META")" = "$ARTIFACT_RUN"
test "$(jq -r .expired <<<"$META")" = false
test "$(jq -r .digest <<<"$META")" = "sha256:$ARTIFACT_SHA"
printf '%s\n' "$META" > "$EVID/artifact-api.json"
gh api repos/llhzx2018/core-free-runner-public/actions/artifacts/$ARTIFACT_ID/zip > "$ROOT/artifact.zip"
test "$(sha256sum "$ROOT/artifact.zip" | awk '{print $1}')" = "$ARTIFACT_SHA"
unzip -q "$ROOT/artifact.zip" -d "$ROOT/unpacked"
FULL="$(find "$ROOT/unpacked" -type f -name 'VF-Start-V2.37.3-FULL.zip' -print -quit)"
test -n "$FULL"
ASSETS="$(dirname "$FULL")"
expected=$(cat <<'EOF'
P01-V2.37.3-FORMAL.json
P01-V2.37.3-RELEASE-NOTES.md
VF-Start-V2.37.3-FULL.zip
VF-Start-V2.37.3-FULL.zip.sha256
VF_Start_V2.37.3_UPDATE.zip
VF_Start_V2.37.3_UPDATE.zip.sha256
repair-v2.37.3.php
repair-v2.37.3.php.sha256
EOF
)
test "$(find "$ASSETS" -maxdepth 1 -type f -printf '%f\n' | sort)" = "$expected"
(cd "$ASSETS" && sha256sum -c VF-Start-V2.37.3-FULL.zip.sha256 && sha256sum -c VF_Start_V2.37.3_UPDATE.zip.sha256 && sha256sum -c repair-v2.37.3.php.sha256) | tee "$EVID/inner-sha.txt"
jq -e '.status=="FORMAL_ARTIFACT_PASS" and .version=="2.37.3" and .source_version=="2.37.2" and .schema=="2026082901" and .formal_source=="cec95e310771feb6813a51c7ee3340884295ee38" and .runtime_tree=="e56459ebadc120c749cc5336821d762001db5218" and .schema_change==false and .migration==null' "$ASSETS/P01-V2.37.3-FORMAL.json" >/dev/null
php -l "$ASSETS/repair-v2.37.3.php" >/dev/null
php "$ASSETS/repair-v2.37.3.php" --self-test | tee "$EVID/repair-self-test.json" | jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' >/dev/null

mkdir -p "$FRESH"
unzip -q "$FULL" -d "$FRESH"
test "$(cat "$FRESH/VERSION.txt")" = 2.37.3
grep -Fx "define('VF_VERSION', '2.37.3');" "$FRESH/app/bootstrap.php" >/dev/null
find "$FRESH" -type f -name '*.php' -print0 | xargs -0 -n1 php -l > "$EVID/fresh-php-lint.txt"
find "$FRESH/assets" -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check
php -S 127.0.0.1:18541 -t "$FRESH" >"$EVID/fresh-server.log" 2>&1 & FPID=$!
trap 'kill $FPID 2>/dev/null || true' EXIT
COOKIE="$EVID/fresh.cookies"
for i in $(seq 1 80); do curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18541/setup.php -o "$EVID/fresh-setup.html" && break; sleep .25; done
CSRF=$(python3 - "$EVID/fresh-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18541/setup.php --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=V2373 Fresh' --data-urlencode 'admin_password=V2373Fresh!2026' --data-urlencode 'admin_password_confirm=V2373Fresh!2026' -o "$EVID/fresh-setup-post.html"
kill "$FPID"; trap - EXIT
FRESH="$FRESH" php <<'PHP' | tee "$EVID/fresh-db.txt"
<?php require getenv('FRESH').'/app/bootstrap.php'; $d=vf_db(); if(strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(1); if($d->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))exit(2); echo "P01_V2373_FRESH_DB=PASS\n";
PHP
php "$FRESH/cli/verify.php" | tee "$EVID/fresh-verify.txt" | grep -Fx VERIFY_PASS=YES

cp -a production/src "$UPGRADE"
php -S 127.0.0.1:18542 -t "$UPGRADE" >"$EVID/upgrade-server.log" 2>&1 & UPID=$!
trap 'kill $UPID 2>/dev/null || true' EXIT
COOKIE2="$EVID/upgrade.cookies"
for i in $(seq 1 80); do curl -fsS -c "$COOKIE2" -b "$COOKIE2" http://127.0.0.1:18542/setup.php -o "$EVID/upgrade-setup.html" && break; sleep .25; done
CSRF2=$(python3 - "$EVID/upgrade-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE2" -b "$COOKIE2" -X POST http://127.0.0.1:18542/setup.php --data-urlencode "setup_csrf=$CSRF2" --data-urlencode 'site_title=V2373 Upgrade' --data-urlencode 'admin_password=V2373Upgrade!2026' --data-urlencode 'admin_password_confirm=V2373Upgrade!2026' -o "$EVID/upgrade-setup-post.html"
UPGRADE="$UPGRADE" php <<'PHP' | tee "$EVID/seed.txt"
<?php require getenv('UPGRADE').'/app/bootstrap.php'; $r=new VfRepository(vf_db()); $c=$r->createCategory(['name'=>'V2373 Preserve','description'=>'','is_private'=>false]); for($i=1;$i<=40;$i++)$r->saveLink(null,['category_id'=>$c,'title'=>'Preserve '.$i,'url'=>'https://example.com/v2373-'.$i,'description'=>'hotfix','tags'=>'v2373','is_private'=>$i%5===0,'is_favorite'=>$i<=4],'manual'); echo "P01_V2373_SEED_40=PASS\n";
PHP
kill "$UPID"; trap - EXIT
php "$ASSETS/repair-v2.37.3.php" --verify-source="$UPGRADE" | tee "$EVID/verify-source.json" | jq -e '.ok==true' >/dev/null
php "$ASSETS/repair-v2.37.3.php" --run="$UPGRADE" | tee "$EVID/atomic-run.json" | jq -e '.ok==true and .already_current==false and .schema=="2026082901"' >/dev/null
test "$(cat "$UPGRADE/VERSION.txt")" = 2.37.3
UPGRADE="$UPGRADE" php <<'PHP' | tee "$EVID/preservation.txt"
<?php require getenv('UPGRADE').'/app/bootstrap.php'; $d=vf_db(); if((int)$d->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn()!==40)exit(1); if((int)$d->query("SELECT COUNT(*) FROM links WHERE is_favorite=1 AND lifecycle_state='active'")->fetchColumn()!==4)exit(2); if(strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn())!=='ok')exit(3); echo "P01_V2373_DATA_PRESERVATION=PASS\n";
PHP
php "$ASSETS/repair-v2.37.3.php" --run="$UPGRADE" | tee "$EVID/idempotent.json" | jq -e '.ok==true and .already_current==true' >/dev/null

mkdir -p candidate
cp -a "$FRESH" candidate/src
EVID="$EVID" bash runner/scripts/p01_v2373_candidate_iyf_e2e.sh
python3 - "$EVID/iyf-e2e.jsonl" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1],encoding='utf-8') if x.strip().startswith('{')]
assert len(rows)==3 and all(x['result'].get('success') is True for x in rows), rows
assert any(x['record']['mime']=='image/gif' for x in rows), rows
print('P01_V2373_FROZEN_IYF_E2E=3/3 PASS')
PY
grep -F 'vf-cover-retry:v4:' "$FRESH/assets/workspace.js" >/dev/null
grep -F "'image/gif'=>'gif'" "$FRESH/app/ResourceCoverCache.php" >/dev/null
sha256sum "$ASSETS"/* | sort > "$EVID/frozen-assets-sha256.txt"
printf 'P01_V2373_STRICT_FRESH=PASS\nFORMAL_ARTIFACT_RUN=%s\nFORMAL_ARTIFACT_ID=%s\nFORMAL_SOURCE=%s\nRUNTIME_TREE=%s\nFRESH_INSTALL=PASS\nATOMIC_2372_TO_2373=PASS\nDATA_PRESERVATION=PASS\nIYF_FIRST_ATTEMPT=3/3\nIYF_RESOURCE_COVER_SERVE=3/3\nFROZEN_BYTES_ONLY=YES\nREBUILD=NO\nOWNER_PRODUCTION_WRITE=NO\n' "$ARTIFACT_RUN" "$ARTIFACT_ID" "$FORMAL_SOURCE" "$RUNTIME_TREE" | tee "$EVID/verdict.txt"
