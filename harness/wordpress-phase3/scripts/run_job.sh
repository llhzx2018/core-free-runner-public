#!/usr/bin/env bash
set -Eeuo pipefail

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${1:?job manifest required}"
python3 "$HARNESS_ROOT/scripts/validate_job.py" "$MANIFEST"

read_json() {
  python3 - "$MANIFEST" "$1" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding='utf-8'))
for part in sys.argv[2].split('.'):
    value = value[part]
print(value)
PY
}

export PROJECT_ID="$(read_json project_id)"
export COMPONENT_ID="$(read_json component_id)"
export RUN_ID="$(read_json run_id)"
SOURCE_MODE="$(read_json source.mode)"

if [[ "$SOURCE_MODE" == "local_directory" ]]; then
  SOURCE_BASE="${GITHUB_WORKSPACE:-$(pwd)}"
  SOURCE_PATH="$(read_json source.path)"
  EXPECTED_SHA="$(read_json source.exact_sha)"
  SOURCE_ROOT="$(realpath -m "$SOURCE_BASE/$SOURCE_PATH")"
  case "$SOURCE_ROOT" in
    "$SOURCE_BASE"/*) ;;
    *) echo 'SOURCE_IDENTITY_FAIL: source escaped workspace' >&2; exit 3 ;;
  esac
  [[ -d "$SOURCE_ROOT/.git" ]] || { echo 'SOURCE_IDENTITY_FAIL: Git checkout missing' >&2; exit 3; }
  ACTUAL_SHA="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
  [[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || {
    echo "SOURCE_IDENTITY_FAIL expected=$EXPECTED_SHA actual=$ACTUAL_SHA" >&2
    exit 3
  }
  echo "SOURCE_IDENTITY_PASS sha=$ACTUAL_SHA"
else
  echo 'SOURCE_IDENTITY=N/A'
fi

export EVIDENCE_DIR="${EVIDENCE_DIR:-${RUNNER_TEMP:-$HARNESS_ROOT/.runtime}/evidence/$RUN_ID}"
export COMPOSE_FILE="$HARNESS_ROOT/docker-compose.yml"
SAFE_NAME="$(printf '%s' "vf_${RUN_ID}_${GITHUB_RUN_ID:-local}_${GITHUB_RUN_ATTEMPT:-1}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9_-' '_')"
export COMPOSE_PROJECT_NAME="${SAFE_NAME:0:58}"
if [[ "${GITHUB_RUN_ID:-}" =~ ^[0-9]+$ ]]; then
  export VF_HTTP_PORT="$((18000 + (GITHUB_RUN_ID % 20000)))"
else
  export VF_HTTP_PORT="${VF_HTTP_PORT:-18080}"
fi

bash "$HARNESS_ROOT/scripts/runner_smoke.sh"
echo "PHASE3_ENVIRONMENT_PASS run=$RUN_ID evidence=$EVIDENCE_DIR"

