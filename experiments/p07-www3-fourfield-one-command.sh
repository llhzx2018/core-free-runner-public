#!/usr/bin/env bash
# P07 www3: exact-blob, root-only, read-only 3-table/4-field diagnosis.
# No import, database write, old-server freeze, DNS or cutover operation.
set -Eeuo pipefail
umask 077
if [[ "$(id -u)" != "0" ]]; then
  echo "BLOCKED=CP2_ROOT_REQUIRED"
  exit 13
fi
if ! command -v curl >/dev/null || ! command -v python3 >/dev/null; then
  echo "BLOCKED=REQUIRED_LOCAL_TOOLS_MISSING"
  exit 13
fi
REF=a128236a201439b183ba054c71e2f48e5334858a
BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/$REF/experiments"
DIR=$(mktemp -d /root/p07-www3-fourfield.XXXXXX)
cleanup() {
  case "$DIR" in
    /root/p07-www3-fourfield.*)
      for name in \
        p07-www3-three-table-field-diagnosis.py \
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
for name in \
  p07-www3-three-table-field-diagnosis.py \
  p07-www3-three-table-type-worker.py \
  p07-www3-restored-readback.py \
  p07-www3-isolated-restore.py; do
  curl -fsSL --retry 2 --connect-timeout 15 "$BASE/$name" -o "$DIR/$name"
done
python3 -c '
import hashlib
from pathlib import Path
import sys
expected = {
  "p07-www3-three-table-field-diagnosis.py":"ea931b318a11a1785f24cbfda1c4811bba36880b",
  "p07-www3-three-table-type-worker.py":"4cb12c1fcd7c7d03c6b5fe6c95ffc72e946671ac",
  "p07-www3-restored-readback.py":"a1ac6e2c6771ca8f2e8a55bcd7064ccc1f9cf47f",
  "p07-www3-isolated-restore.py":"1b3b9285853cc99e467f70d92c7d2b0222874018",
}
root=Path(sys.argv[1])
for name,digest in expected.items():
  data=(root/name).read_bytes()
  actual=hashlib.sha1(b"blob "+str(len(data)).encode()+bytes([0])+data).hexdigest()
  if actual!=digest:
    print("SCRIPT_BUNDLE_INTEGRITY=FAIL")
    sys.exit(13)
print("SCRIPT_BUNDLE_INTEGRITY=PASS",flush=True)
' "$DIR"
echo "CHECK_SCOPE=ONLY_TABLE_ORDINALS_39_60_69"
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  "$DIR/p07-www3-three-table-field-diagnosis.py" \
  --diagnose-three-table-field-types-read-only
