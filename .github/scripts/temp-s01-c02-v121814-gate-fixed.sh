#!/usr/bin/env bash
set -Eeuo pipefail
src="$(dirname "$0")/temp-s01-c02-v121814-gate.sh"
tmp=/tmp/temp-s01-c02-v121814-gate-fixed.sh
sed 's/PK\\x03\\x04default-source/PK\\x03\\x04default-source-long-enough/g' "$src" > "$tmp"
chmod +x "$tmp"
exec bash "$tmp"
