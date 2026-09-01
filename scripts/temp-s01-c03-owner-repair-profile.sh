#!/usr/bin/env bash
set -Eeuo pipefail

: "${WP_PATH:?}"
: "${EVIDENCE_DIR:?}"

base_script="$GITHUB_WORKSPACE/runner/scripts/temp-s01-c02-owner-runtime-v2.sh"
marker_line="$(grep -n '^export WP_ADMIN_PASSWORD_FILE=' "$base_script" | head -n1 | cut -d: -f1)"
test -n "$marker_line"
test "$marker_line" -gt 1
head -n "$((marker_line - 1))" "$base_script" > /tmp/vf-s01-profile-setup.sh
bash /tmp/vf-s01-profile-setup.sh

node "$GITHUB_WORKSPACE/runner/scripts/temp-s01-c03-owner-repair-profile.js"
test -s "$EVIDENCE_DIR/owner-repair-profile.json"
jq -e '.mode=="RUNNER_ONLY_OWNER_REPAIR_PROFILE" and (.stages|length)==7 and .stages[-1].result.status=="PASS"' "$EVIDENCE_DIR/owner-repair-profile.json" >/dev/null

if [ -f "$WP_PATH/wp-content/debug.log" ]; then
  cp "$WP_PATH/wp-content/debug.log" "$EVIDENCE_DIR/wordpress-debug-profile.log"
fi

cat > "$EVIDENCE_DIR/S01_C03_OWNER_REPAIR_PROFILE.txt" <<EOF
S01_C03_OWNER_REPAIR_PROFILE=PASS
RUNTIME_MODE=RUNNER_ONLY
M3U8_GIT_WRITE=NO
OPS_GIT_WRITE=NO
THEME_GIT_WRITE=NO
RELEASE_WRITE=NO
TAG_WRITE=NO
CORE_UPDATES_WRITE=NO
PRODUCTION_WRITE=NO
EOF

rm -f /tmp/vf-s01-owner-admin.pass /tmp/vf-s01-profile-setup.sh
