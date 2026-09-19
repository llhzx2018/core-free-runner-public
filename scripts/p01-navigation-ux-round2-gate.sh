#!/usr/bin/env bash
set -Eeuo pipefail

P01_ROOT="${P01_ROOT:?missing P01_ROOT}"
EXPECTED="913089f049f65e0ba365766df760ef69e31ced8f"
test "$(git -C "$P01_ROOT" rev-parse HEAD)" = "$EXPECTED"
test "$(tr -d '\r\n ' < "$P01_ROOT/VERSION")" = "2.47.14"

php -l "$P01_ROOT/src/app/ResourceSearch.php" >/dev/null
php -l "$P01_ROOT/src/app/FunctionalWorkspace.php" >/dev/null
php -l "$P01_ROOT/src/app/FunctionalWorkspaceShell.php" >/dev/null
node --check "$P01_ROOT/src/assets/workspace.js"

tests=(
  resource_search_contract.php
  navigation_context_persistence_contract.php
  navigation_search_authority_contract.php
  navigation_search_context_contract.php
  search_sort_stability_contract.php
  navigation_category_facet_recovery_contract.php
  navigation_public_row_layout_contract.php
  p01_filter_select_csp_navigation_contract.php
)
for t in "${tests[@]}"; do
  php "$P01_ROOT/tests/unit/$t"
done

mkdir -p evidence/runner
cat > evidence/runner/P01_NAVIGATION_UX_ROUND2_GATE.txt <<EOF
P01_EXACT_SOURCE_SHA=$EXPECTED
VERSION=2.47.14
PHP_LINT=PASS
WORKSPACE_JS_SYNTAX=PASS
MULTI_TERM_RESOURCE_SEARCH=PASS
CLEARABLE_SEARCH_FILTER_CONTEXT=PASS
PAGINATION_RESULTS_ANCHOR=PASS
EXACT_URL_SCROLL_RETURN=PASS
NAVIGATION_SEARCH_AUTHORITY=PASS
SEARCH_SORT_STABILITY=PASS
CATEGORY_FACET_RECOVERY=PASS
PUBLIC_ROW_LAYOUT_REGRESSION=PASS
P01_NAVIGATION_UX_ROUND2_GATE=PASS
PRODUCTION=NOT_WRITTEN
EOF
cat evidence/runner/P01_NAVIGATION_UX_ROUND2_GATE.txt
