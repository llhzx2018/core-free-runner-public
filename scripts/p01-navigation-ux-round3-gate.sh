#!/usr/bin/env bash
set -Eeuo pipefail
P01_ROOT="${P01_ROOT:?missing P01_ROOT}"
EXPECTED="83fa547319c8547cd7e5b1d38109c9b582960f15"
test "$(git -C "$P01_ROOT" rev-parse HEAD)" = "$EXPECTED"
test "$(tr -d '\r\n ' < "$P01_ROOT/VERSION")" = "2.47.15"

for f in   src/app/FunctionalWorkspace.php   src/app/FunctionalWorkspaceShell.php   src/app/ToolProductPage.php   src/app/ToolSceneDetail.php   src/app/SoftwareWorkspaceDetail.php   src/app/SubjectPageChrome.php
do
  php -l "$P01_ROOT/$f" >/dev/null
done
node --check "$P01_ROOT/src/assets/workspace.js"

tests=(
  navigation_owner_behavior_privacy_contract.php
  navigation_owner_views_round3_contract.php
  contextual_favorite_badge_contract.php
  navigation_favorite_count_context_contract.php
  navigation_search_context_contract.php
  start_popular_sort_control_contract.php
  start_favorite_sort_reset_contract.php
  favorite_add_context_contract.php
  derived_favorite_view_coherence_contract.php
  tool_shared_search_context_contract.php
  tool_scene_context_consistency_contract.php
  tool_software_sort_context_contract.php
  software_detail_context_contract.php
  subject_request_context_sanitization_contract.php
  public_global_nav_contract.php
  navigation_public_row_layout_contract.php
  navigation_context_persistence_contract.php
  resource_search_contract.php
)
for t in "${tests[@]}"; do
  echo "== $t =="
  php "$P01_ROOT/tests/unit/$t"
done

mkdir -p evidence/runner
cat > evidence/runner/P01_NAVIGATION_UX_ROUND3_GATE.txt <<EOF
P01_EXACT_SOURCE_SHA=$EXPECTED
VERSION=2.47.15
PHP_LINT=PASS
WORKSPACE_JS_SYNTAX=PASS
OWNER_BEHAVIOR_PUBLIC_PRIVACY=PASS
START_OWNER_FAVORITE_POPULAR_RECENT=PASS
RECENT_WINDOW_CONTEXT=PASS
FAVORITE_LIVE_BADGE=PASS
DERIVED_TOOL_SOFTWARE_OWNER_VIEWS=PASS
SEARCH_CONTEXT_REGRESSION=PASS
PUBLIC_NAV_REGRESSION=PASS
P01_NAVIGATION_UX_ROUND3_GATE=PASS
PRODUCTION=NOT_WRITTEN
EOF
cat evidence/runner/P01_NAVIGATION_UX_ROUND3_GATE.txt
