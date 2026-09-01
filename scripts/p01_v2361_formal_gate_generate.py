from pathlib import Path

T=Path('template/.github/workflows/p01-v2360-formal-artifact-gate-20260901.yml').read_text().splitlines()

def run_block(lines,name):
    marker='      - name: '+name
    start=lines.index(marker)
    run=None
    for j in range(start+1,len(lines)):
        if j>start+1 and lines[j].startswith('      - '): break
        if lines[j].strip()=='run: |': run=j+1; break
    if run is None: raise SystemExit('missing run '+name)
    body=[]
    for j in range(run,len(lines)):
        if lines[j].startswith('      - '): break
        line=lines[j]
        body.append(line[10:] if line.startswith('          ') else line)
    return '\n'.join(body)+'\n'

exact=r'''set -Eeuo pipefail
rm -rf "$OUT" "$EVID" "$UPGRADE"; mkdir -p "$OUT" "$EVID"
test "$(git -C formal rev-parse HEAD)" = "$FORMAL"
test "$(git -C formal rev-parse HEAD^{tree})" = "$FORMAL_TREE"
test "$(git -C formal rev-parse HEAD:src)" = "$FORMAL_RUNTIME_TREE"
test "$(git -C formal rev-parse origin/develop)" = "$FORMAL"
test "$(git -C formal rev-parse origin/main)" = "$MAIN_EXPECTED"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
! git -C formal show-ref --verify --quiet refs/tags/v2.36.1
test "$(cat formal/VERSION)" = "$VERSION"
test "$(cat formal/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.36.1');" formal/src/app/bootstrap.php >/dev/null
jq -e '.candidate_state=="PASS" and .v2_36_1_candidate_gate.run==33472637909 and .v2_36_1_candidate_gate.result=="PASS" and .v2_36_1_candidate_gate.artifact==9787058642 and .production_version=="2.36.0" and .candidate_version=="2.36.1" and .schema_version=="2026082901"' formal/VF_PROJECT.json >/dev/null
test "$(git -C formal rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find formal/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find formal/src/assets -type f -name '*.js' -print0 | xargs -0 -n1 node --check
git -C formal diff --name-status "$SOURCE"...HEAD -- src | tee "$EVID/runtime-delta.txt"
actual="$(git -C formal diff --name-only "$SOURCE"...HEAD -- src | sort | tr '\n' ' ')"
expected='src/VERSION.txt src/api.php src/app/FunctionalWorkspace.php src/app/FunctionalWorkspaceCore.php src/app/FunctionalWorkspaceShell.php src/app/bootstrap.php src/assets/frontend.css src/assets/workspace-domain-nav.css src/index.php src/start.php '
test "$actual" = "$expected"
test -z "$(git -C formal diff --diff-filter=A --name-only "$SOURCE"...HEAD -- src)"
test -z "$(git -C formal diff --diff-filter=D --name-only "$SOURCE"...HEAD -- src)"
for needle in public_view preview_return vf_fw_public_preview_requested vf-global-view-state vf-view-state 管理员视角 公开视角 查看公开版 返回管理; do
  ! git -C formal grep -n -F "$needle" -- src/api.php src/app/FunctionalWorkspace.php src/app/FunctionalWorkspaceCore.php src/app/FunctionalWorkspaceShell.php src/assets/frontend.css src/assets/workspace-domain-nav.css src/index.php src/start.php
done
printf 'P01_V2361_FORMAL_FENCE=PASS\nFORMAL=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nCANDIDATE_GATE=%s/PASS\nOWNER_PRODUCTION_WRITE=NO\n' "$FORMAL" "$FORMAL_TREE" "$FORMAL_RUNTIME_TREE" "$SCHEMA" "$CANDIDATE_GATE" | tee "$EVID/fence.txt"
'''

build=run_block(T,'Build deterministic formal release artifacts')
for old,new in [
    ('/tmp/p01-v2360-formal-build.py','/tmp/p01-v2361-formal-build.py'),
    ('/tmp/p01-v2360-formal-first','/tmp/p01-v2361-formal-first'),
    ('P01_V2360','P01_V2361'),('p01-v2360','p01-v2361'),('V2.36.0','V2.36.1'),('v2.36.0','v2.36.1'),
    ('2.35.3','__SOURCE_VERSION__'),('2.36.0','2.36.1'),('__SOURCE_VERSION__','2.36.0'),
]:
    build=build.replace(old,new)
build=build.replace("required={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required.issubset(set(added)): raise SystemExit('formal additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('patch formal artifacts must not add/remove runtime files: '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual formal V2.35.3 to V2.36.0 upgrade')
for old,new in [('p01-v2360','p01-v2361'),('P01_V2360','P01_V2361')]: atomic=atomic.replace(old,new)
atomic=atomic.replace('2.35.3','__SOURCE_VERSION__').replace('2.36.0','2.36.1').replace('__SOURCE_VERSION__','2.36.0')
atomic=atomic.replace('P01_V2353_TO_V2361','P01_V2360_TO_V2361')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic)]:
    p=Path('/tmp/p01-v2361-formal-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    p.chmod(0o755)
