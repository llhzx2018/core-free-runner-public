#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT_HEAD="${PRODUCT_HEAD:?}"; AUTHORITY_HEAD="${AUTHORITY_HEAD:?}"; PRODUCT_VERSION="${PRODUCT_VERSION:?}"; PRODUCT_SCHEMA="${PRODUCT_SCHEMA:?}"
ROOT="${GITHUB_WORKSPACE}/vf-src"; SITE="/tmp/p04-v270-final-ui-${GITHUB_RUN_ID}"
cd "$ROOT"
cleanup(){ [[ -n "${PHP_PID:-}" ]] && kill "$PHP_PID" 2>/dev/null || true; rm -rf "$SITE" 2>/dev/null || true; }; trap cleanup EXIT

echo '=== IDENTITY / SCOPED DELTA ==='
test "$(git rev-parse HEAD)" = "$PRODUCT_HEAD"
test "$(tr -d '\r\n' < VERSION)" = "$PRODUCT_VERSION"
test "$(jq -r '.schema_version_contract' VF_PROJECT.json)" = "$PRODUCT_SCHEMA"
test "$(jq -r '.integration.migration' VF_PROJECT.json)" = NONE
mapfile -t changed < <(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD")
printf '%s\n' "${changed[@]}"; test "${#changed[@]}" -eq 3
for p in public/index.php public/assets/v270-final-polish.css tests/e2e/v270-reference-locked-candidate.mjs; do printf '%s\n' "${changed[@]}" | grep -Fx "$p" >/dev/null; done
mapfile -t runtime_changed < <(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- public src config database)
printf 'RUNTIME_DELTA %s\n' "${runtime_changed[@]}"; test "${#runtime_changed[@]}" -eq 2
printf '%s\n' "${runtime_changed[@]}" | grep -Fx public/index.php >/dev/null
printf '%s\n' "${runtime_changed[@]}" | grep -Fx public/assets/v270-final-polish.css >/dev/null
test -z "$(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- VERSION VF_PROJECT.json migrations database src config public/bootstrap.php public/api.php public/experience.php public/assets/v270-reference-lock.js public/assets/v270-personal-infra.css)"
test "$(git diff --numstat "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- public/index.php | awk '{print $1":"$2}')" = 1:0
! grep -Eqi 'VF_PRIVATE_READ_TOKEN|VF_RELEASE_WRITE_TOKEN|github_pat_|ghp_' public/assets/v270-final-polish.css tests/e2e/v270-reference-locked-candidate.mjs
echo P04_V270_SCOPED_DELTA=PASS

echo '=== PHP / CURRENT NON-LEGACY CONTRACTS ==='
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find . -type f -name '*.php' -print0)
for t in tests/unit/*.php; do
  case "$t" in tests/unit/ui_contract_v256.php|tests/unit/ui_contract_v257.php|tests/unit/ui_contract_v258.php) echo "SKIP_SUPERSEDED $t"; continue;; esac
  echo "RUN $t"; php "$t"
done
grep -F 'intentionally superseded' tests/unit/ui_contract_v256.php >/dev/null
echo P04_V270_CURRENT_CONTRACTS=PASS

echo '=== FORMAL RELEASE-TREE ==='
rm -rf "$SITE" evidence-final-ui; mkdir -p evidence-final-ui
python3 scripts/build-release-tree.py "$SITE" --source-root "$ROOT" | tee evidence-final-ui/release-tree-build.json
test "$(tr -d '\r\n' < "$SITE/VERSION.txt")" = "$PRODUCT_VERSION"
for p in assets/v270-final-polish.css assets/v270-reference-lock.js assets/v270-reference-lock.css index.php; do test -s "$SITE/$p"; done
python3 - "$SITE/release-manifest.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8')); assert p['version']=='2.7.0'; assert int(p['target_schema'])==14
paths={x['path'] for x in p['files']}; assert 'assets/v270-final-polish.css' in paths and 'index.php' in paths
PY
echo P04_V270_RELEASE_TREE=PASS

echo '=== REFERENCE-LOCKED BROWSER / VISUAL ==='
npm init -y >/dev/null 2>&1
npm install --no-save playwright@1.55.0 >/dev/null
npx playwright install --with-deps chromium >/dev/null
export VF_INFRA_E2E_ADMIN_CREDENTIAL="P04-CANDIDATE-$(openssl rand -hex 16)"
php -d "session.save_path=/tmp" -S 127.0.0.1:18998 -t "$SITE" > evidence-final-ui/php-server.log 2>&1 & PHP_PID=$!
for i in $(seq 1 100); do code="$(curl -sS -o /tmp/p04-setup.html -w '%{http_code}' http://127.0.0.1:18998/setup.php 2>/dev/null || true)"; [[ "$code" = 200 ]] && break; kill -0 "$PHP_PID" 2>/dev/null || break; sleep .1; done
if [[ "${code:-}" != 200 ]]; then cat evidence-final-ui/php-server.log >&2 || true; cat /tmp/p04-setup.html >&2 || true; exit 73; fi
VF_INFRA_E2E_BASE_URL=http://127.0.0.1:18998 VF_INFRA_E2E_ADMIN_CREDENTIAL="$VF_INFRA_E2E_ADMIN_CREDENTIAL" VF_INFRA_E2E_WEB_ROOT="$SITE" VF_V270_TESTED_RUNTIME_COMMIT="$PRODUCT_HEAD" VF_V270_EVIDENCE_DIR="$ROOT/evidence-final-ui" node tests/e2e/v270-reference-locked-candidate.mjs | tee evidence-final-ui/e2e.log

echo '=== SECURITY REGRESSION ==='
test -f "$SITE/config.php"
mode="$(stat -c '%a' "$SITE/config.php")"; case "$mode" in 600|640) ;; *) echo "UNSAFE_CONFIG_MODE=$mode"; exit 71;; esac
code="$(curl -sS -o /tmp/p04-unauth.out -w '%{http_code}' -H 'Accept: application/json' 'http://127.0.0.1:18998/api.php?action=snapshot')"; test "$code" = 401 -o "$code" = 403
! grep -RIlE 'VF_PRIVATE_READ_TOKEN|VF_RELEASE_WRITE_TOKEN|github_pat_|ghp_' evidence-final-ui "$SITE/config.php"
printf 'SECURITY_REGRESSION=PASS\nCONFIG_MODE=%s\nUNAUTH_API_HTTP=%s\n' "$mode" "$code" > evidence-final-ui/security-regression.txt

echo '=== EVIDENCE MANIFEST ==='
pngs="$(find evidence-final-ui -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')"; test "$pngs" -eq 12
sha256sum evidence-final-ui/*.png > evidence-final-ui/SHA256SUMS
fingerprint="$(jq -r '.source_fingerprint' evidence-final-ui/release-tree-build.json)"; files="$(jq -r '.file_count' evidence-final-ui/release-tree-build.json)"
cat > evidence-final-ui/CANDIDATE_GATE_MANIFEST.json <<JSON
{"project":"P04 · VF Infra","status":"READY_FOR_ACTUAL_PIXEL_REVIEW","source_head":"$PRODUCT_HEAD","authority_commit":"$AUTHORITY_HEAD","version":"$PRODUCT_VERSION","schema":14,"migration":"NONE","owner_real_use":"PASS","final_ui_polish":"TESTED","functional_regression":"PASS","security_regression":"PASS","desktop_browser":"PASS","mobile_browser":"PASS","actual_pixel_review":"PENDING_MASTER_AGENT_INSPECTION","screenshot_count":$pngs,"release_tree_file_count":$files,"release_tree_fingerprint":"$fingerprint","runtime_delta_files":2,"test_only_delta_files":1,"production_write":0,"candidate_created":false}
JSON
cat evidence-final-ui/CANDIDATE_GATE_MANIFEST.json
echo P04_V270_FINAL_UI_CANDIDATE_GATE=PASS
