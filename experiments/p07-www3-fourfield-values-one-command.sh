#!/usr/bin/env bash
# P07 www3: scoped, read-only four-column value occurrence comparison.
set -Eeuo pipefail
umask 077
if [[ "$(id -u)" != "0" ]]; then echo "BLOCKED=CP2_ROOT_REQUIRED"; exit 13; fi
for cmd in curl python3; do
  if ! command -v "$cmd" >/dev/null; then echo "BLOCKED=REQUIRED_TOOL_MISSING"; exit 13; fi
done
REF=193f91d184dc7f12acbd1868270bb9255b4bd1e8
BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/$REF/experiments"
DIR=$(mktemp -d /root/p07-four-values.XXXXXX)
cleanup() {
  case "$DIR" in
    /root/p07-four-values.*)
      for name in p07-www3-fourfield-value-difference.py \
        p07-www3-fourfield-values-worker.py \
        p07-www3-three-table-type-worker.py \
        p07-www3-restored-readback.py \
        p07-www3-isolated-restore.py; do
          rm -f -- "$DIR/$name"
      done
      rmdir -- "$DIR" 2>/dev/null || :
      ;;
  esac
}
trap cleanup EXIT
for name in p07-www3-fourfield-value-difference.py \
  p07-www3-fourfield-values-worker.py \
  p07-www3-three-table-type-worker.py \
  p07-www3-restored-readback.py \
  p07-www3-isolated-restore.py; do
  curl -fsSL --retry 2 --connect-timeout 15 "$BASE/$name" -o "$DIR/$name"
done
python3 -c '
import hashlib,sys
from pathlib import Path
expected={
"p07-www3-fourfield-value-difference.py":"572db9d7764561194202a45ce02c5e10272fe460",
"p07-www3-fourfield-values-worker.py":"3be0d443561a90b6e66de1470224c72c5552bab5",
"p07-www3-three-table-type-worker.py":"4cb12c1fcd7c7d03c6b5fe6c95ffc72e946671ac",
"p07-www3-restored-readback.py":"a1ac6e2c6771ca8f2e8a55bcd7064ccc1f9cf47f",
"p07-www3-isolated-restore.py":"1b3b9285853cc99e467f70d92c7d2b0222874018"}
for name,sha in expected.items():
 d=(Path(sys.argv[1])/name).read_bytes()
 h=hashlib.sha1(b"blob "+str(len(d)).encode()+bytes([0])+d).hexdigest()
 if h!=sha:
  print("SCRIPT_BUNDLE_INTEGRITY=FAIL")
  sys.exit(13)
print("SCRIPT_BUNDLE_INTEGRITY=PASS",flush=True)
' "$DIR"
echo "CHECK_SCOPE=THREE_TABLES_FOUR_FIELDS_ONLY"
PYTHONDONTWRITEBYTECODE=1 python3 -B "$DIR/p07-www3-fourfield-value-difference.py" \
  --compare-four-differing-field-values-read-only
