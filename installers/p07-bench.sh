#!/usr/bin/env bash
set -euo pipefail

# P07 Enhanced Bench stable launcher.
# User-facing command stays stable; the pinned source below only changes after a field + CI gate.
PINNED_REF="90d34694a6bdfadf46311919a3067644fa5f146d"
PINNED_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/${PINNED_REF}/experiments/p07-bench.sh"
EXPECTED_VERSION='0.9.0'

TMP="$(mktemp -t p07-bench-stable.XXXXXX)"
cleanup(){ rm -f "$TMP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if command -v curl >/dev/null 2>&1; then
  curl -fsSL --connect-timeout 8 --max-time 60 "$PINNED_URL" -o "$TMP"
elif command -v wget >/dev/null 2>&1; then
  wget -q --https-only --timeout=60 -O "$TMP" "$PINNED_URL"
else
  printf 'P07 Bench: curl or wget is required.\n' >&2
  exit 127
fi

grep -Fq "VERSION=\"${EXPECTED_VERSION}\"" "$TMP" || {
  printf 'P07 Bench: pinned version verification failed.\n' >&2
  exit 1
}

bash -n "$TMP"
exec bash "$TMP" "$@"
