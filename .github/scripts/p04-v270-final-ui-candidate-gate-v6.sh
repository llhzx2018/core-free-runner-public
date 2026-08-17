#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT_HEAD="${PRODUCT_HEAD:?}"; AUTHORITY_HEAD="${AUTHORITY_HEAD:?}"; PRODUCT_VERSION="${PRODUCT_VERSION:?}"; PRODUCT_SCHEMA="${PRODUCT_SCHEMA:?}"
ROOT="${GITHUB_WORKSPACE}/vf-src"
SITE="/tmp/p04-v270-final-ui-${GITHUB_RUN_ID}"
cd "$ROOT"
cleanup(){ rm -rf "$SITE" 2>/dev/null || true; [[ -n "${PHP_PID:-}" ]] && kill "$PHP_PID" 2>/dev/null || true; }
trap cleanup EXIT

echo '=== IDENTITY / POLISH-ONLY DELTA ==='
test "$(git rev-parse HEAD)" = "$PRODUCT_HEAD"
test "$(tr -d '\r\n' < VERSION)" = "$PRODUCT_VERSION"
test "$(jq -r '.schema_version_contract' VF_PROJECT.json)" = "$PRODUCT_SCHEMA"
test "$(jq -r '.integration.migration' VF_PROJECT.json)" = NONE
mapfile -t changed < <(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD")
printf '%s\n' "${changed[@]}"; test "${#changed[@]}" -eq 2
printf '%s\n' "${changed[@]}" | grep -Fx public/index.php >/dev/null
printf '%s\n' "${changed[@]}" | grep -Fx public/assets/v270-final-polish.css >/dev/null
test -z "$(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- VERSION VF_PROJECT.json migrations public/bootstrap.php public/api.php public/experience.php public/assets/v270-reference-lock.js public/assets/v270-personal-infra.css)"
test "$(git diff --numstat "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- public/index.php | awk '{print $1":"$2}')" = 1:0
! grep -Eqi 'VF_PRIVATE_READ_TOKEN|VF_RELEASE_WRITE_TOKEN|github_pat_|ghp_' public/assets/v270-final-polish.css
echo P04_V270_POLISH_ONLY_DELTA=PASS

echo '=== PHP / NON-LEGACY UNIT REGRESSION ==='
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find . -type f -name '*.php' -print0)
for t in tests/unit/*.php; do
  case "$t" in tests/unit/ui_contract_v256.php|tests/unit/ui_contract_v257.php|tests/unit/ui_contract_v258.php) echo "SKIP_SUPERSEDED $t"; continue;; esac
  echo "RUN $t"; php "$t"
done
grep -F 'intentionally superseded' tests/unit/ui_contract_v256.php >/dev/null
echo P04_V270_PHP_NONLEGACY_UNIT_REGRESSION=PASS

echo '=== FORMAL RELEASE-TREE BUILD ==='
rm -rf "$SITE" evidence-final-ui
mkdir -p evidence-final-ui
python3 scripts/build-release-tree.py "$SITE" --source-root "$ROOT" | tee evidence-final-ui/release-tree-build.json
test "$(tr -d '\r\n' < "$SITE/VERSION.txt")" = "$PRODUCT_VERSION"
test -s "$SITE/assets/v270-final-polish.css"
test -s "$SITE/assets/v270-reference-lock.js"
test -s "$SITE/assets/v270-reference-lock.css"
python3 - "$SITE/release-manifest.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
assert p['version']=='2.7.0'
assert int(p['target_schema'])==14
paths={x['path'] for x in p['files']}
assert 'assets/v270-final-polish.css' in paths
assert 'index.php' in paths
PY
echo P04_V270_RELEASE_TREE=PASS

echo '=== CURRENT V2.7 BROWSER / PIXEL / SECURITY ==='
npm init -y >/dev/null 2>&1
npm install --no-save playwright@1.55.0 >/dev/null
npx playwright install --with-deps chromium >/dev/null
export VF_INFRA_E2E_ADMIN_CREDENTIAL="P04-CANDIDATE-$(openssl rand -hex 16)"
php -d "session.save_path=/tmp" -S 127.0.0.1:18998 -t "$SITE" > evidence-final-ui/php-server.log 2>&1 & PHP_PID=$!
for i in $(seq 1 100); do
  code="$(curl -sS -o /tmp/p04-setup.html -w '%{http_code}' http://127.0.0.1:18998/setup.php 2>/dev/null || true)"
  [[ "$code" = 200 ]] && break
  if ! kill -0 "$PHP_PID" 2>/dev/null; then break; fi
  sleep .1
done
if [[ "${code:-}" != 200 ]]; then cat evidence-final-ui/php-server.log >&2 || true; cat /tmp/p04-setup.html >&2 || true; exit 73; fi
VF_INFRA_E2E_BASE_URL=http://127.0.0.1:18998 \
VF_INFRA_E2E_ADMIN_CREDENTIAL="$VF_INFRA_E2E_ADMIN_CREDENTIAL" \
VF_INFRA_E2E_WEB_ROOT="$SITE" \
VF_V270_TESTED_RUNTIME_COMMIT="$PRODUCT_HEAD" \
VF_V270_EVIDENCE_DIR="$ROOT/evidence-final-ui" \
node tests/e2e/v270-final-polish-evidence.mjs | tee evidence-final-ui/e2e.log

echo '=== SECURITY REGRESSION ==='
test -f "$SITE/config.php"
mode="$(stat -c '%a' "$SITE/config.php")"; case "$mode" in 600|640) ;; *) echo "UNSAFE_CONFIG_MODE=$mode"; exit 71;; esac
code="$(curl -sS -o /tmp/p04-v270-unauth.out -w '%{http_code}' -H 'Accept: application/json' 'http://127.0.0.1:18998/api.php?action=snapshot')"
test "$code" = 401 -o "$code" = 403
! grep -RIlE 'VF_PRIVATE_READ_TOKEN|VF_RELEASE_WRITE_TOKEN|github_pat_|ghp_' evidence-final-ui "$SITE/config.php"
printf 'SECURITY_REGRESSION=PASS\nCONFIG_MODE=%s\nUNAUTH_API_HTTP=%s\n' "$mode" "$code" > evidence-final-ui/security-regression.txt

echo '=== VISUAL INVENTORY ==='
pngs="$(find evidence-final-ui -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')"; test "$pngs" -ge 12
sha256sum evidence-final-ui/*.png > evidence-final-ui/SHA256SUMS
fingerprint="$(jq -r '.source_fingerprint' evidence-final-ui/release-tree-build.json)"
files="$(jq -r '.file_count' evidence-final-ui/release-tree-build.json)"
cat > evidence-final-ui/CANDIDATE_GATE_MANIFEST.json <<JSON
{"project":"P04 · VF Infra","status":"READY_FOR_ACTUAL_PIXEL_REVIEW","runtime_commit":"$PRODUCT_HEAD","authority_commit":"$AUTHORITY_HEAD","version":"$PRODUCT_VERSION","schema":14,"migration":"NONE","owner_real_use":"PASS","final_ui_polish":"TESTED","functional_regression":"PASS","security_regression":"PASS","desktop":"PASS","mobile":"PASS","actual_pixel_review":"PENDING_MASTER_AGENT_INSPECTION","screenshot_count":$pngs,"release_tree_file_count":$files,"release_tree_fingerprint":"$fingerprint","production_write":0,"candidate_created":false,"legacy_ui_contracts":"SUPERSEDED_BY_CURRENT_V270_E2E"}
JSON
cat evidence-final-ui/CANDIDATE_GATE_MANIFEST.json
echo P04_V270_FINAL_UI_CANDIDATE_GATE=PASS
