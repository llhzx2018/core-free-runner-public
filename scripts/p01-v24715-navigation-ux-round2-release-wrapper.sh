#!/usr/bin/env bash
set -Eeuo pipefail

: "${TARGET_ROOT:?missing TARGET_ROOT}"
: "${BASELINE_ROOT:?missing BASELINE_ROOT}"
: "${OLD_HARNESS_ROOT:?missing OLD_HARNESS_ROOT}"
: "${PROVEN_ROOT:?missing PROVEN_ROOT}"
: "${OLD_GATE_ROOT:?missing OLD_GATE_ROOT}"

SRC="$OLD_GATE_ROOT/scripts/p01-v24714-navigation-row-release-gate.sh"
DST=/tmp/p01-v24715-release-gate.sh
cp "$SRC" "$DST"

python3 - "$DST" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
pairs=[
("TARGET_SHA=421e7b5df1e48db768b39470fc99580330a07c0f","TARGET_SHA=abe82d469c24b8f1d5f8d4081800b4abfadc6148"),
("TARGET_TREE=598eaae633ef485dd2eef1330a9370cb46f90506","TARGET_TREE=6428100224e12ce89463dfecb12bebd42a9df8f6"),
("SOURCE_SHA=e714cfe540ad39202c2cb558e5c0a370ef6d6502","SOURCE_SHA=421e7b5df1e48db768b39470fc99580330a07c0f"),
("SOURCE_VERSION=2.47.13","SOURCE_VERSION=2.47.14"),
("TARGET_VERSION=2.47.14","TARGET_VERSION=2.47.15"),
("OUT=/tmp/p01-v24714-navigation","OUT=/tmp/p01-v24715-navigation-round2"),
("BUILD=/tmp/p01-v24714-navigation-builder","BUILD=/tmp/p01-v24715-navigation-round2-builder"),
("VF-Start-V2.47.14-FULL.zip","VF-Start-V2.47.15-FULL.zip"),
("VF_Start_V2.47.14_UPDATE.zip","VF_Start_V2.47.15_UPDATE.zip"),
("repair-v2.47.14.php","repair-v2.47.15.php"),
("/tmp/p01-v24714-navigation-builder/gate.py","/tmp/p01-v24715-navigation-round2-builder/gate.py"),
('VERSION = "2.47.14"','VERSION = "2.47.15"'),
('SOURCE_VERSION = "2.47.13"','SOURCE_VERSION = "2.47.14"'),
("public const SOURCE_VERSION='2.47.13';\\\\n    public const TARGET_VERSION='2.47.14';","public const SOURCE_VERSION='2.47.14';\\\\n    public const TARGET_VERSION='2.47.15';"),
("V2.47.14 fixes logged-out Navigation row layout width while preserving Atomic update safety.","V2.47.15 improves Navigation search and context persistence while preserving Atomic update safety."),
("/tmp/p01-v24714-navigation-rebuild","/tmp/p01-v24715-navigation-round2-rebuild"),
("P01_V24714_NAVIGATION_ROW_RELEASE_GATE=PASS","P01_V24715_NAVIGATION_UX_ROUND2_RELEASE_GATE=PASS"),
("R14_GATE_RECEIPT.txt","R15_GATE_RECEIPT.txt"),
("V24713_TO_V24714_ATOMIC_UPGRADE=PASS","V24714_TO_V24715_ATOMIC_UPGRADE=PASS"),
("OWNER_PREVIEW_RUNTIME_REASON=bounded corrective layout bug; no new product shape or interaction contract","OWNER_PREVIEW_RUNTIME_REASON=bounded Navigation usability refinement; no new product shape or IA contract"),
]
for a,b in pairs:
    if a not in s:
        raise SystemExit("missing patch anchor: "+a)
    s=s.replace(a,b)
s=s.replace("p01-r14-","p01-r15-").replace("R14","R15").replace("r14","r15")
p.write_text(s,encoding='utf-8')
PY

bash "$DST"

# Round 2 exact-source focused acceptance.
php "$TARGET_ROOT/tests/unit/resource_search_contract.php" | grep -Fx RESOURCE_SEARCH_CONTRACT_PASS
php "$TARGET_ROOT/tests/unit/navigation_context_persistence_contract.php" | grep -Fx P01_NAVIGATION_CONTEXT_PERSISTENCE=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_authority_contract.php" | grep -Fx P01_NAVIGATION_SEARCH_AUTHORITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_search_context_contract.php" | grep -Fx NAVIGATION_SEARCH_CONTEXT_PASS
php "$TARGET_ROOT/tests/unit/search_sort_stability_contract.php" | grep -Fx P01_SEARCH_SORT_STABILITY_CONTRACT=PASS
php "$TARGET_ROOT/tests/unit/navigation_category_facet_recovery_contract.php" | grep -Fx NAVIGATION_CATEGORY_FACET_RECOVERY_PASS

OUT=/tmp/p01-v24715-navigation-round2
cat >>"$OUT/R15_GATE_RECEIPT.txt" <<'EOF'
MULTI_TERM_RESOURCE_SEARCH=PASS
CLEARABLE_SEARCH_FILTER_CONTEXT=PASS
PAGINATION_RESULTS_ANCHOR=PASS
EXACT_URL_SCROLL_RETURN=PASS
NAVIGATION_SEARCH_AUTHORITY=PASS
SEARCH_SORT_STABILITY=PASS
CATEGORY_FACET_RECOVERY=PASS
EOF
cat "$OUT/R15_GATE_RECEIPT.txt"
