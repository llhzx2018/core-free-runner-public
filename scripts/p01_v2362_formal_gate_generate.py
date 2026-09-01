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
test "$(git -C formal rev-parse origin/main)" = "$MAIN_EXPECTED"
test "$(git -C formal rev-parse origin/develop)" = "$DEVELOP_EXPECTED"
test "$(git -C formal merge-base "$FORMAL" origin/develop)" = "$FORMAL"
test "$(git -C formal rev-parse origin/develop:src)" = "$FORMAL_RUNTIME_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
! git -C formal show-ref --verify --quiet refs/tags/v2.36.2
test "$(cat formal/VERSION)" = "$VERSION"
test "$(cat formal/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.36.2');" formal/src/app/bootstrap.php >/dev/null
jq -e '.v2_36_2_candidate_gate.state=="PASS" and .v2_36_2_candidate_gate.candidate_readiness_run==33478737169 and .v2_36_2_candidate_gate.artifact==9789120412 and .production_version=="2.36.0" and .candidate_version=="2.36.2" and .schema_version=="2026082901"' formal/VF_PROJECT.json >/dev/null
test "$(git -C formal rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find formal/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find formal/src/assets -type f -name '*.js' -print0 | xargs -0 -n1 node --check
git -C formal diff --name-status "$SOURCE"...HEAD -- src | tee "$EVID/runtime-delta.txt"
actual="$(git -C formal diff --name-only "$SOURCE"...HEAD -- src | sort | tr '\n' ' ')"
expected='src/VERSION.txt src/app/FunctionalWorkspaceShell.php src/app/bootstrap.php src/assets/auth-controls.js src/assets/workspace-rebaseline.css src/index.php '
test "$actual" = "$expected"
added="$(git -C formal diff --diff-filter=A --name-only "$SOURCE"...HEAD -- src | sed 's#^src/##' | sort | tr '\n' ' ')"
removed="$(git -C formal diff --diff-filter=D --name-only "$SOURCE"...HEAD -- src | sed 's#^src/##' | sort | tr '\n' ' ')"
test "$added" = 'assets/auth-controls.js '
test -z "$removed"
grep -F 'data-vf-auth-login' formal/src/app/FunctionalWorkspaceShell.php >/dev/null
grep -F 'data-vf-auth-logout' formal/src/app/FunctionalWorkspaceShell.php >/dev/null
grep -F 'mobileAccountLabel.textContent=auth?' formal/src/index.php >/dev/null
for needle in public_view preview_return vf_fw_public_preview_requested vf-global-view-state vf-view-state 管理员视角 公开视角 查看公开版 返回管理; do
  ! grep -R -F "$needle" formal/src/app/FunctionalWorkspaceShell.php formal/src/assets/auth-controls.js formal/src/index.php
done
printf 'P01_V2362_FORMAL_FENCE=PASS\nFORMAL=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nCANDIDATE_GATE=%s/PASS\nDEVELOP=%s\nOWNER_PRODUCTION_WRITE=NO\n' "$FORMAL" "$FORMAL_TREE" "$FORMAL_RUNTIME_TREE" "$SCHEMA" "$CANDIDATE_GATE" "$DEVELOP_EXPECTED" | tee "$EVID/fence.txt"
'''

build=run_block(T,'Build deterministic formal release artifacts')
for old,new in [
    ('/tmp/p01-v2360-formal-build.py','/tmp/p01-v2362-formal-build.py'),
    ('/tmp/p01-v2360-formal-first','/tmp/p01-v2362-formal-first'),
    ('P01_V2360','P01_V2362'),('p01-v2360','p01-v2362'),('V2.36.0','V2.36.2'),('v2.36.0','v2.36.2'),
    ('2.35.3','__SOURCE_VERSION__'),('2.36.0','2.36.2'),('__SOURCE_VERSION__','2.36.1'),
]:
    build=build.replace(old,new)
build=build.replace("required={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required.issubset(set(added)): raise SystemExit('formal additions missing '+json.dumps(added))", "if set(added)!={'assets/auth-controls.js'} or removed: raise SystemExit('formal runtime add/remove fence failed '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual formal V2.35.3 to V2.36.0 upgrade')
for old,new in [('p01-v2360','p01-v2362'),('P01_V2360','P01_V2362')]: atomic=atomic.replace(old,new)
atomic=atomic.replace('2.35.3','__SOURCE_VERSION__').replace('2.36.0','2.36.2').replace('__SOURCE_VERSION__','2.36.1')
atomic=atomic.replace('P01_V2353_TO_V2362','P01_V2361_TO_V2362')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic)]:
    p=Path('/tmp/p01-v2362-formal-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    p.chmod(0o755)
