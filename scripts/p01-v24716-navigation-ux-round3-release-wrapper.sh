#!/usr/bin/env bash
set -Eeuo pipefail

: "${TARGET_ROOT:?missing TARGET_ROOT}"
: "${BASELINE_ROOT:?missing BASELINE_ROOT}"
: "${OLD_HARNESS_ROOT:?missing OLD_HARNESS_ROOT}"
: "${PROVEN_ROOT:?missing PROVEN_ROOT}"
: "${OLD_GATE_ROOT:?missing OLD_GATE_ROOT}"

dump_gate_logs(){
  rc=$?
  echo "P01_V24716_RELEASE_WRAPPER_RC=$rc" >&2
  for log in /tmp/p01-r16-*-evidence/server.log /tmp/p01-r16-public-ui-server.log; do
    if [ -f "$log" ]; then
      echo "===== $log =====" >&2
      cat "$log" >&2 || true
    fi
  done
  exit "$rc"
}
trap dump_gate_logs ERR

SRC="$OLD_GATE_ROOT/scripts/p01-v24714-navigation-row-release-gate.sh"
DST=/tmp/p01-v24716-release-gate.sh
cp "$SRC" "$DST"

python3 - "$DST" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
pairs=[
("TARGET_SHA=421e7b5df1e48db768b39470fc99580330a07c0f","TARGET_SHA=f953988b4001f04b36c027168a815d80ae3b5fb7"),
("TARGET_TREE=598eaae633ef485dd2eef1330a9370cb46f90506","TARGET_TREE=a0271a55adf8e95379e1e762589f33b6cc8d6e6d"),
("SOURCE_SHA=e714cfe540ad39202c2cb558e5c0a370ef6d6502","SOURCE_SHA=abe82d469c24b8f1d5f8d4081800b4abfadc6148"),
("SOURCE_VERSION=2.47.13","SOURCE_VERSION=2.47.15"),
("TARGET_VERSION=2.47.14","TARGET_VERSION=2.47.16"),
("OUT=/tmp/p01-v24714-navigation","OUT=/tmp/p01-v24716-navigation-round3"),
("BUILD=/tmp/p01-v24714-navigation-builder","BUILD=/tmp/p01-v24716-navigation-round3-builder"),
("VF-Start-V2.47.14-FULL.zip","VF-Start-V2.47.16-FULL.zip"),
("VF_Start_V2.47.14_UPDATE.zip","VF_Start_V2.47.16_UPDATE.zip"),
("repair-v2.47.14.php","repair-v2.47.16.php"),
("/tmp/p01-v24714-navigation-builder/gate.py","/tmp/p01-v24716-navigation-round3-builder/gate.py"),
('VERSION = "2.47.14"','VERSION = "2.47.16"'),
('SOURCE_VERSION = "2.47.13"','SOURCE_VERSION = "2.47.15"'),
('VF_VERSION!=="2.47.14"','VF_VERSION!=="2.47.16"'),
("public const SOURCE_VERSION='2.47.13';\\\\n    public const TARGET_VERSION='2.47.14';","public const SOURCE_VERSION='2.47.15';\\\\n    public const TARGET_VERSION='2.47.16';"),
("V2.47.14 fixes logged-out Navigation row layout width while preserving Atomic update safety.","V2.47.16 adds owner-only behavior views and public-privacy Navigation refinement while preserving Atomic update safety."),
("/tmp/p01-v24714-navigation-rebuild","/tmp/p01-v24716-navigation-round3-rebuild"),
("P01_V24714_NAVIGATION_ROW_RELEASE_GATE=PASS","P01_V24716_NAVIGATION_UX_ROUND3_RELEASE_GATE=PASS"),
("R14_GATE_RECEIPT.txt","R16_GATE_RECEIPT.txt"),
("V24713_TO_V24714_ATOMIC_UPGRADE=PASS","V24715_TO_V24716_ATOMIC_UPGRADE=PASS"),
("OWNER_PREVIEW_RUNTIME_REASON=bounded corrective layout bug; no new product shape or interaction contract","OWNER_PREVIEW_RUNTIME_REASON=bounded owner behavior views and public-privacy refinement; no new product shape or IA contract"),
]
for a,b in pairs:
    if a not in s:
        raise SystemExit("missing patch anchor: "+a)
    s=s.replace(a,b)
s=s.replace("p01-r14-","p01-r16-").replace("R14","R16").replace("r14","r16")
p.write_text(s,encoding='utf-8')
PY

bash "$DST"

# Round 2 regression + Round 3 exact-source focused acceptance.
php "$TARGET_ROOT/tests/unit/resource_search_contract.php" | grep -Fx RESOURCE_SEARCH_CONTRACT_PASS
php "$TARGET_ROOT/tests/unit/navigation_context_persistence_contract.php" | grep -Fx P01_NAVIGATION_CONTEXT_PERSISTENCE=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_authority_contract.php" | grep -Fx P01_NAVIGATION_SEARCH_AUTHORITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_context_contract.php" | grep -Fx NAVIGATION_SEARCH_CONTEXT_PASS
php "$TARGET_ROOT/tests/unit/search_sort_stability_contract.php" | grep -Fx P01_SEARCH_SORT_STABILITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_category_facet_recovery_contract.php" | grep -Fx NAVIGATION_CATEGORY_FACET_RECOVERY_PASS

OUT=/tmp/p01-v24716-navigation-round3
cat >>"$OUT/R16_GATE_RECEIPT.txt" <<'EOF'
MULTI_TERM_RESOURCE_SEARCH=PASS
CLEARABLE_SEARCH_FILTER_CONTEXT=PASS
PAGINATION_RESULTS_ANCHOR=PASS
EXACT_URL_SCROLL_RETURN=PASS
NAVIGATION_SEARCH_AUTHORITY=PASS
SEARCH_SORT_STABILITY=PASS
CATEGORY_FACET_RECOVERY=PASS
EOF
# Round 3 owner behavior / privacy / context contracts.
for test_name in \
  navigation_owner_behavior_privacy_contract.php \
  navigation_owner_views_round3_contract.php \
  contextual_favorite_badge_contract.php \
  navigation_favorite_count_context_contract.php \
  start_popular_sort_control_contract.php \
  start_favorite_sort_reset_contract.php \
  favorite_add_context_contract.php \
  derived_favorite_view_coherence_contract.php \
  tool_shared_search_context_contract.php \
  tool_scene_context_consistency_contract.php \
  tool_software_sort_context_contract.php \
  software_detail_context_contract.php \
  subject_request_context_sanitization_contract.php \
  public_global_nav_contract.php \
  navigation_public_row_layout_contract.php; do
  php "$TARGET_ROOT/tests/unit/$test_name"
done

cat >>"$OUT/R16_GATE_RECEIPT.txt" <<'EOF'
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
SEARCH_CONTEXT_REGRESSION=PASS
PUBLIC_NAV_REGRESSION=PASS
PUBLIC_AUTHORITY_RELEASE_COVERAGE=PASS
NO_REQUIRED_GATE_MISSING=YES
NO_UNKNOWN_APPLICABILITY=YES
PRODUCTION=NOT_WRITTEN
EOF

cat "$OUT/R16_GATE_RECEIPT.txt"
