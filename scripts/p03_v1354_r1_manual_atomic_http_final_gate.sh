#!/usr/bin/env bash
set -Eeuo pipefail

: "${UPDATE_ASSET_ID:?}"
: "${UPDATE_BYTES:?}"
: "${UPDATE_SHA256:?}"
: "${ORIGINAL_UPDATE_ASSET_ID:?}"
: "${ORIGINAL_UPDATE_SHA256:?}"
: "${GATE_ROOT:?}"
: "${GH_TOKEN:?}"

BASE_GATE="harness/scripts/p03_v1354_dist_r1_local_gate.sh"
PATCHED_GATE="$RUNNER_TEMP/p03_v1354_r1_manual_http_patched_gate.sh"
cp "$BASE_GATE" "$PATCHED_GATE"
python3 harness/scripts/p03_v1354_r1_manual_http_patch.py "$PATCHED_GATE"
chmod +x "$PATCHED_GATE"
bash -n "$PATCHED_GATE"
bash "$PATCHED_GATE"

echo 'MANUAL_ATOMIC_HTTP_FINAL_GATE=PASS'
echo 'AUTOMATIC_DISTRIBUTION=UNSUPPORTED_FOR_CORRECTIVE_REVISION_ON_V1.35.3'
echo 'MANUAL_CORRECTIVE_DISTRIBUTION=SUPPORTED_VERIFIED'
echo 'PRODUCTION_WRITE=0'
