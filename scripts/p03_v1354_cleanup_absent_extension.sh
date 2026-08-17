run_already_absent_case(){
  local mode="$1" port="$2" label="absent-$1" runtime="$GATE_ROOT/absent-$1" data="$GATE_ROOT/data-absent-$1" cookie="$GATE_ROOT/cookie-absent-$1"
  prepare_case "$label"
  case "$mode" in
    writer) rm -f "$runtime/$WRITER" ;;
    forensic) rm -f "$runtime/$FORENSIC" ;;
    both) rm -f "$runtime/$WRITER" "$runtime/$FORENSIC" ;;
    *) return 91 ;;
  esac
  start_fixture "$runtime" "$data" "$port"
  trap "stop_fixture $port" RETURN
  local csrf base baseline form_csrf
  csrf=$(setup_login "$port" "$data" "$cookie" "$runtime" | tail -n1)
  base="http://127.0.0.1:$port"
  baseline=$(db_state "$port")

  curl -fsS -b "$cookie" "$base/$CLEANUP" -o "$GATE_ROOT/$label-get.html"
  grep -q 'Preflight PASS' "$GATE_ROOT/$label-get.html"
  grep -q 'already absent / safe' "$GATE_ROOT/$label-get.html"
  form_csrf=$(python3 - "$GATE_ROOT/$label-get.html" <<'PY'
import re,sys
m=re.search(r'name="_csrf" value="([^"]+)"',open(sys.argv[1]).read()); assert m; print(m.group(1))
PY
)
  test "$form_csrf" = "$csrf"
  assert_db_state_unchanged "$port" "$baseline"

  curl -fsS -b "$cookie" -H "Origin: $base" \
    --data-urlencode "_csrf=$form_csrf" --data-urlencode 'action=cleanup' \
    "$base/$CLEANUP" -o "$GATE_ROOT/$label.json"

  python3 - "$GATE_ROOT/$label.json" "$mode" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); mode=sys.argv[2]
W='vf-forge-v1354-source-reconcile-1ec8566c6838.php'
F='vf-forge-v1354-source-forensic-3dc194b1768a.php'
assert j['ok'] is True and j['closure']=='TEMPORARY_TOOL_CLEANUP_PASS'
assert j['source_exact']=='PASS' and j['production_runtime_managed_files']==42
assert j['temporary_writer_remaining']==0 and j['temporary_forensic_probe_remaining']==0 and j['cleanup_tool_remaining']==0
assert j['product_runtime_write']==0 and j['memory_api_write']==0 and j['production_db_write']==0 and j['provider_write']==0
assert j['migration']=='NOT_EXECUTED' and j['m030']=='NOT_RERUN'
if mode=='writer':
    assert j['already_absent']==[W] and j['deleted']==[F]
elif mode=='forensic':
    assert j['already_absent']==[F] and j['deleted']==[W]
elif mode=='both':
    assert set(j['already_absent'])=={W,F} and len(j['already_absent'])==2 and j['deleted']==[]
else:
    raise AssertionError(mode)
PY

  test ! -e "$runtime/$WRITER" && test ! -L "$runtime/$WRITER"
  test ! -e "$runtime/$FORENSIC" && test ! -L "$runtime/$FORENSIC"
  test ! -e "$runtime/$CLEANUP" && test ! -L "$runtime/$CLEANUP"
  assert_db_state_unchanged "$port" "$baseline"
  echo "ALREADY_ABSENT_${mode^^}=PASS"
  stop_fixture "$port"; trap - RETURN
}
