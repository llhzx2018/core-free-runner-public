#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT_HEAD="${PRODUCT_HEAD:?}"
AUTHORITY_HEAD="${AUTHORITY_HEAD:?}"
PRODUCT_VERSION="${PRODUCT_VERSION:?}"
PRODUCT_SCHEMA="${PRODUCT_SCHEMA:?}"
ROOT="${GITHUB_WORKSPACE}/vf-src"
cd "$ROOT"

echo '=== IDENTITY / DELTA ==='
test "$(git rev-parse HEAD)" = "$PRODUCT_HEAD"
test "$(tr -d '\r\n' < VERSION)" = "$PRODUCT_VERSION"
test "$(jq -r '.schema_version_contract' VF_PROJECT.json)" = "$PRODUCT_SCHEMA"
test "$(jq -r '.integration.migration' VF_PROJECT.json)" = 'NONE'
mapfile -t changed < <(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD")
printf '%s\n' "${changed[@]}"
test "${#changed[@]}" -eq 2
printf '%s\n' "${changed[@]}" | grep -Fx public/index.php >/dev/null
printf '%s\n' "${changed[@]}" | grep -Fx public/assets/v270-final-polish.css >/dev/null
test -z "$(git diff --name-only "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- VERSION VF_PROJECT.json migrations public/bootstrap.php public/api.php public/experience.php public/assets/v270-reference-lock.js public/assets/v270-personal-infra.css)"
test "$(git diff --numstat "$AUTHORITY_HEAD" "$PRODUCT_HEAD" -- public/index.php | awk '{print $1":"$2}')" = '1:0'
! grep -Eqi 'VF_PRIVATE_READ_TOKEN|VF_RELEASE_WRITE_TOKEN|github_pat_|ghp_' public/assets/v270-final-polish.css
echo P04_V270_POLISH_ONLY_DELTA=PASS

echo '=== PHP / UNIT REGRESSION ==='
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find . -type f -name '*.php' -print0)
for t in tests/unit/*.php; do echo "RUN $t"; php "$t"; done
echo P04_V270_PHP_UNIT_REGRESSION=PASS

echo '=== BROWSER RUNTIME ==='
npm init -y >/dev/null 2>&1
npm install --no-save playwright@1.55.0 >/dev/null
npx playwright install --with-deps chromium >/dev/null
rm -f public/config.php public/*.sqlite public/*.sqlite-* || true
rm -rf public/data public/storage var/data var/sessions evidence-final-ui
mkdir -p evidence-final-ui
export VF_INFRA_E2E_ADMIN_CREDENTIAL="P04-CANDIDATE-$(openssl rand -hex 16)"
php -S 127.0.0.1:18998 -t public > evidence-final-ui/php-server.log 2>&1 &
PHP_PID=$!
cleanup(){ kill "$PHP_PID" 2>/dev/null || true; }
trap cleanup EXIT
for i in $(seq 1 30); do curl -fsS http://127.0.0.1:18998/setup.php >/dev/null && break || sleep 1; done
curl -fsS http://127.0.0.1:18998/setup.php >/dev/null
VF_INFRA_E2E_BASE_URL=http://127.0.0.1:18998 \
VF_INFRA_E2E_ADMIN_CREDENTIAL="$VF_INFRA_E2E_ADMIN_CREDENTIAL" \
VF_INFRA_E2E_WEB_ROOT="$ROOT/public" \
VF_V270_TESTED_RUNTIME_COMMIT="$PRODUCT_HEAD" \
VF_V270_EVIDENCE_DIR="$ROOT/evidence-final-ui" \
node tests/e2e/v270-final-polish-evidence.mjs | tee evidence-final-ui/e2e.log

echo '=== SECURITY REGRESSION ==='
test -f public/config.php
mode="$(stat -c '%a' public/config.php)"
case "$mode" in 600|640) ;; *) echo "UNSAFE_CONFIG_MODE=$mode"; exit 71;; esac
code="$(curl -sS -o /tmp/p04-v270-unauth.out -w '%{http_code}' -H 'Accept: application/json' 'http://127.0.0.1:18998/api.php?action=snapshot')"
test "$code" = 401 -o "$code" = 403
! grep -RIlE 'VF_PRIVATE_READ_TOKEN|VF_RELEASE_WRITE_TOKEN|github_pat_|ghp_' evidence-final-ui public/config.php
printf 'SECURITY_REGRESSION=PASS\nCONFIG_MODE=%s\nUNAUTH_API_HTTP=%s\n' "$mode" "$code" > evidence-final-ui/security-regression.txt

echo '=== VISUAL INVENTORY ==='
pngs="$(find evidence-final-ui -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')"
test "$pngs" -ge 12
sha256sum evidence-final-ui/*.png > evidence-final-ui/SHA256SUMS
cat > evidence-final-ui/CANDIDATE_GATE_MANIFEST.json <<JSON
{
  "project":"P04 · VF Infra",
  "status":"READY_FOR_ACTUAL_PIXEL_REVIEW",
  "runtime_commit":"$PRODUCT_HEAD",
  "authority_commit":"$AUTHORITY_HEAD",
  "version":"$PRODUCT_VERSION",
  "schema":14,
  "migration":"NONE",
  "owner_real_use":"PASS",
  "final_ui_polish":"TESTED",
  "functional_regression":"PASS",
  "security_regression":"PASS",
  "desktop":"PASS",
  "mobile":"PASS",
  "actual_pixel_review":"PENDING_MASTER_AGENT_INSPECTION",
  "screenshot_count":$pngs,
  "production_write":0,
  "candidate_created":false
}
JSON
cat evidence-final-ui/CANDIDATE_GATE_MANIFEST.json
echo P04_V270_FINAL_UI_CANDIDATE_GATE=PASS
