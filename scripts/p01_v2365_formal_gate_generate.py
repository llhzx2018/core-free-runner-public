from pathlib import Path

T=Path('template/.github/workflows/p01-v2360-formal-artifact-gate-20260901.yml').read_text().splitlines()

def run_block(lines,name):
    marker='      - name: '+name
    start=lines.index(marker); run=None
    for j in range(start+1,len(lines)):
        if j>start+1 and lines[j].startswith('      - '): break
        if lines[j].strip()=='run: |': run=j+1; break
    if run is None: raise SystemExit('missing run '+name)
    out=[]
    for j in range(run,len(lines)):
        if lines[j].startswith('      - '): break
        out.append(lines[j][10:] if lines[j].startswith('          ') else lines[j])
    return '\n'.join(out)+'\n'

exact=r'''set -Eeuo pipefail
rm -rf "$OUT" "$EVID" "$UPGRADE"; mkdir -p "$OUT" "$EVID"
test "$(git -C formal rev-parse HEAD)" = "$FORMAL"
test "$(git -C formal rev-parse HEAD^{tree})" = "$FORMAL_TREE"
test "$(git -C formal rev-parse HEAD:src)" = "$FORMAL_RUNTIME_TREE"
test "$(git -C formal rev-parse HEAD^)" = "$CANDIDATE"
test "$(git -C formal rev-parse origin/main)" = "$MAIN_EXPECTED"
test "$(git -C formal rev-parse origin/develop)" = "$DEVELOP_EXPECTED"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
! git -C formal show-ref --verify --quiet refs/tags/v2.36.5
test "$(cat formal/VERSION)" = "$VERSION"
test "$(cat formal/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.36.5');" formal/src/app/bootstrap.php >/dev/null
python3 - <<'PY'
import json
D=json.load(open('formal/VF_PROJECT.json')); c=D['v2_36_5_release_candidate']
assert D['production_version']=='2.36.4' and D['candidate_version']=='2.36.5' and D['schema_version']=='2026082901'
assert c['candidate_source']=='57d99978340a45cd7673c6d0943137e6437aae51'
assert c['candidate_tree']=='4517a92885e5fe4db42ba5b23bdcfbc712940be2'
assert c['candidate_runtime_tree']=='a7f472ec1f449ada1152d271f2723c52e7b58144'
assert c['candidate_readiness_gate']==33547215072 and c['candidate_readiness_artifact']==9815966257
assert c['candidate_readiness_artifact_digest']=='sha256:a0544bd418a03e4feeb95b1aea635b7a4bad4e0ae3ae969ef2c8ce075f49a5e3'
assert c['unknown_runtime_bytes']==0 and c['schema_change'] is False and c['migration'] is None
assert D['current_change']['release_authorized_by_owner'] is True
PY
test "$(git -C formal rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find formal/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find formal/src/assets -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C formal diff --name-only "$SOURCE" HEAD -- src | sort | tee "$EVID/runtime-delta.txt"
actual="$(tr '\n' ' ' < "$EVID/runtime-delta.txt")"
expected='src/VERSION.txt src/app/FunctionalWorkspace.php src/app/ResourceCoverCache.php src/app/bootstrap.php src/assets/resource-media.css src/assets/update-core.js src/assets/workspace-rebaseline.css '
test "$actual" = "$expected"
test -z "$(git -C formal diff --diff-filter=A --name-only "$SOURCE" HEAD -- src)"
test -z "$(git -C formal diff --diff-filter=D --name-only "$SOURCE" HEAD -- src)"
test "$(git -C formal rev-parse HEAD:src/assets/update-core.js)" = f18284aefac9d02294be9667631d3ffdbb7de6d9
test "$(git -C formal rev-parse HEAD:src/app/ResourceCoverCache.php)" = 629a3a8b964fcfd3c75728d2ca66070a900c7e1b
test "$(git -C formal rev-parse HEAD:src/app/FunctionalWorkspace.php)" = 54df2b995db32d6de2b9e593e04037a1bf4eb610
test "$(git -C formal rev-parse HEAD:src/assets/resource-media.css)" = ec8ca1a7e2ab4a829f939bb2442ea9af8297b873
test "$(git -C formal rev-parse HEAD:src/assets/workspace-rebaseline.css)" = 2eeb8b057d96bb04222f14d2cb02fa48089a882e
printf 'P01_V2365_FORMAL_FENCE=PASS\nFORMAL=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nCANDIDATE_GATE=%s/PASS\nOWNER_PRODUCTION_WRITE=NO\n' "$FORMAL" "$FORMAL_TREE" "$FORMAL_RUNTIME_TREE" "$SCHEMA" "$CANDIDATE_GATE" | tee "$EVID/fence.txt"
'''

build=run_block(T,'Build deterministic formal release artifacts')
for old,new in [
    ('/tmp/p01-v2360-formal-build.py','/tmp/p01-v2365-formal-build.py'),
    ('/tmp/p01-v2360-formal-first','/tmp/p01-v2365-formal-first'),
    ('P01_V2360','P01_V2365'),('p01-v2360','p01-v2365'),('V2.36.0','V2.36.5'),('v2.36.0','v2.36.5'),
    ('2.35.3','__SOURCE_VERSION__'),('2.36.0','2.36.5'),('__SOURCE_VERSION__','2.36.4'),
]: build=build.replace(old,new)
build=build.replace("required={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required.issubset(set(added)): raise SystemExit('formal additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('formal runtime add/remove fence failed '+json.dumps({'added':added,'removed':removed}))")
build=build.replace('FORMAL_ARTIFACT_GATE_PASS_PENDING_RUNTIME','FORMAL_ARTIFACT_GATE_PASS')

atomic=run_block(T,'Actual formal V2.35.3 to V2.36.0 upgrade')
for old,new in [('p01-v2360','p01-v2365'),('P01_V2360','P01_V2365')]: atomic=atomic.replace(old,new)
atomic=atomic.replace('2.35.3','__SOURCE_VERSION__').replace('2.36.0','2.36.5').replace('__SOURCE_VERSION__','2.36.4')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic)]:
    p=Path('/tmp/p01-v2365-formal-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(0o755)
