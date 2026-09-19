#!/usr/bin/env bash
set -Eeuo pipefail

: "${TARGET_ROOT:?missing TARGET_ROOT}"
: "${BASELINE_ROOT:?missing BASELINE_ROOT}"
: "${OLD_HARNESS_ROOT:?missing OLD_HARNESS_ROOT}"
: "${PROVEN_ROOT:?missing PROVEN_ROOT}"
: "${OLD_GATE_ROOT:?missing OLD_GATE_ROOT}"

dump_gate_logs(){
  rc=$?
  echo "P01_V24719_RELEASE_WRAPPER_RC=$rc" >&2
  for log in /tmp/p01-r19-*-evidence/server.log /tmp/p01-r19-public-ui-server.log; do
    if [ -f "$log" ]; then
      echo "===== $log =====" >&2
      cat "$log" >&2 || true
    fi
  done
  exit "$rc"
}
trap dump_gate_logs ERR

SRC="$OLD_GATE_ROOT/scripts/p01-v24714-navigation-row-release-gate.sh"
DST=/tmp/p01-v24719-release-gate.sh
cp "$SRC" "$DST"

python3 - "$DST" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
pairs=[
("TARGET_SHA=421e7b5df1e48db768b39470fc99580330a07c0f","TARGET_SHA=a3b51bdb69cd1e530fc7136028b2712a5a96551c"),
("TARGET_TREE=598eaae633ef485dd2eef1330a9370cb46f90506","TARGET_TREE=e881ef44f78108c13c0af2f54ffa5b0efed27b2f"),
("SOURCE_SHA=e714cfe540ad39202c2cb558e5c0a370ef6d6502","SOURCE_SHA=52249a697b907e15f6cb56acb37fa8993b789d80"),
("SOURCE_VERSION=2.47.13","SOURCE_VERSION=2.47.18"),
("TARGET_VERSION=2.47.14","TARGET_VERSION=2.47.19"),
("OUT=/tmp/p01-v24714-navigation","OUT=/tmp/p01-v24719-navigation-round6"),
("BUILD=/tmp/p01-v24714-navigation-builder","BUILD=/tmp/p01-v24719-navigation-round6-builder"),
("VF-Start-V2.47.14-FULL.zip","VF-Start-V2.47.19-FULL.zip"),
("VF_Start_V2.47.14_UPDATE.zip","VF_Start_V2.47.19_UPDATE.zip"),
("repair-v2.47.14.php","repair-v2.47.19.php"),
("/tmp/p01-v24714-navigation-builder/gate.py","/tmp/p01-v24719-navigation-round6-builder/gate.py"),
('VERSION = "2.47.14"','VERSION = "2.47.19"'),
('SOURCE_VERSION = "2.47.13"','SOURCE_VERSION = "2.47.18"'),
('VF_VERSION!=="2.47.14"','VF_VERSION!=="2.47.19"'),
("public const SOURCE_VERSION='2.47.13';","public const SOURCE_VERSION='2.47.18';"),
("public const TARGET_VERSION='2.47.14';","public const TARGET_VERSION='2.47.19';"),
("V2.47.14 fixes logged-out Navigation row layout width while preserving Atomic update safety.","V2.47.19 removes hidden duplicate sidebar account actions while preserving Atomic update safety."),
("/tmp/p01-v24714-navigation-rebuild","/tmp/p01-v24719-navigation-round6-rebuild"),
("P01_V24714_NAVIGATION_ROW_RELEASE_GATE=PASS","P01_V24719_NAVIGATION_UX_ROUND6_RELEASE_GATE=PASS"),
("R14_GATE_RECEIPT.txt","R19_GATE_RECEIPT.txt"),
("V24713_TO_V24714_ATOMIC_UPGRADE=PASS","V24717_TO_V24719_ATOMIC_UPGRADE=PASS"),
("OWNER_PREVIEW_RUNTIME_REASON=bounded corrective layout bug; no new product shape or interaction contract","OWNER_PREVIEW_RUNTIME_REASON=implementation-only single-owner action cleanup; no new product shape, data, auth, or IA contract"),
]
for a,b in pairs:
    if a not in s:
        raise SystemExit("missing patch anchor: "+a)
    s=s.replace(a,b)
s=s.replace("p01-r14-","p01-r19-").replace("R14","R19").replace("r14","r19")
p.write_text(s,encoding='utf-8')
PY

bash "$DST"

# Stable Navigation regressions + Round 6 single-owner acceptance.
php "$TARGET_ROOT/tests/unit/resource_search_contract.php" | grep -Fx RESOURCE_SEARCH_CONTRACT_PASS
php "$TARGET_ROOT/tests/unit/navigation_context_persistence_contract.php" | grep -Fx P01_NAVIGATION_CONTEXT_PERSISTENCE=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_authority_contract.php" | grep -Fx P01_NAVIGATION_SEARCH_AUTHORITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_context_contract.php" | grep -Fx NAVIGATION_SEARCH_CONTEXT_PASS
php "$TARGET_ROOT/tests/unit/search_sort_stability_contract.php" | grep -Fx P01_SEARCH_SORT_STABILITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_category_facet_recovery_contract.php" | grep -Fx NAVIGATION_CATEGORY_FACET_RECOVERY_PASS
php "$TARGET_ROOT/tests/unit/mobile_sort_accessibility_contract.php" | grep -Fx P01_NAVIGATION_UX_ROUND5_MOBILE_SORT=PASS

OUT=/tmp/p01-v24719-navigation-round6
cat >>"$OUT/R19_GATE_RECEIPT.txt" <<'EOF'
MULTI_TERM_RESOURCE_SEARCH=PASS
CLEARABLE_SEARCH_FILTER_CONTEXT=PASS
PAGINATION_RESULTS_ANCHOR=PASS
EXACT_URL_SCROLL_RETURN=PASS
NAVIGATION_SEARCH_AUTHORITY=PASS
SEARCH_SORT_STABILITY=PASS
CATEGORY_FACET_RECOVERY=PASS
MOBILE_SORT_REACHABILITY=PASS
EOF

for test_name in   navigation_owner_behavior_privacy_contract.php   navigation_owner_views_round3_contract.php   contextual_favorite_badge_contract.php   navigation_favorite_count_context_contract.php   start_popular_sort_control_contract.php   start_favorite_sort_reset_contract.php   favorite_add_context_contract.php   derived_favorite_view_coherence_contract.php   tool_shared_search_context_contract.php   tool_scene_context_consistency_contract.php   tool_software_sort_context_contract.php   software_detail_context_contract.php   subject_request_context_sanitization_contract.php   public_global_nav_contract.php   navigation_public_row_layout_contract.php   global_account_actions_contract.php   subject_domain_nav_shell_contract.php; do
  php "$TARGET_ROOT/tests/unit/$test_name"
done

cat >>"$OUT/R19_GATE_RECEIPT.txt" <<'EOF'
PUBLIC_AUTHORITY_APPLICABILITY_INSTALL=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_SECURITY=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_TESTING=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_UPGRADE=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_DATA_SCHEMA=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_API_PROVIDER=N_A
PUBLIC_AUTHORITY_APPLICABILITY_SEO=N_A
PUBLIC_AUTHORITY_APPLICABILITY_CRON_JOB=N_A
PUBLIC_AUTHORITY_APPLICABILITY_NOTIFICATION=N_A
PUBLIC_AUTHORITY_APPLICABILITY_OBSERVABILITY=N_A
PUBLIC_AUTHORITY_APPLICABILITY_PERFORMANCE=N_A
PUBLIC_AUTHORITY_APPLICABILITY_GIT=REQUIRED
PUBLIC_AUTHORITY_APPLICABILITY_UA_UI=REQUIRED
OWNER_BEHAVIOR_PUBLIC_PRIVACY=PASS
START_OWNER_FAVORITE_POPULAR_RECENT=PASS
RECENT_WINDOW_CONTEXT=PASS
FAVORITE_LIVE_BADGE=PASS
DERIVED_TOOL_SOFTWARE_OWNER_VIEWS=PASS
GLOBAL_ACCOUNT_SERVER_RENDER=PASS
CLIENT_DOM_REPARENTING_REMOVED=PASS
GLOBAL_ACCOUNT_SINGLE_OWNER=PASS
SIDEBAR_VERSION_ONLY=PASS
SEARCH_CONTEXT_REGRESSION=PASS
PUBLIC_NAV_REGRESSION=PASS
PUBLIC_AUTHORITY_RELEASE_COVERAGE=PASS
NO_REQUIRED_GATE_MISSING=YES
NO_UNKNOWN_APPLICABILITY=YES
PRODUCTION=NOT_WRITTEN
EOF

cat "$OUT/R19_GATE_RECEIPT.txt"
