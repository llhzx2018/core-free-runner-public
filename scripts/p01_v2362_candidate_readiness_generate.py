from pathlib import Path

T=Path('template/.github/workflows/p01-v2360-candidate-readiness-20260901.yml').read_text().splitlines()
A=Path('auth/.github/workflows/p01-auth-entry-formal-gate-r2-20260901.yml').read_text().splitlines()

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
rm -rf "$OUT" "$EVID" "$UPGRADE" "$FRESH"; mkdir -p "$OUT" "$EVID"
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C candidate rev-parse HEAD:src)" = "$CANDIDATE_RUNTIME_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(git -C candidate merge-base "$SOURCE" HEAD)" = "$SOURCE"
test "$(cat candidate/VERSION)" = "$VERSION"
test "$(cat candidate/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.36.2');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = "$SOURCE_VERSION"
jq -e '.production_version=="2.36.0" and .candidate_version=="2.36.2" and .schema_version=="2026082901" and .v2_36_2_release_candidate.schema_change==false and .v2_36_2_release_candidate.migration==null and .v2_36_2_release_candidate.product_fix_merge=="cd87a40e8e7d445b36c77f670a8a2e1a50257c05" and .v2_36_2_release_candidate.product_pr==170 and .v2_36_2_release_candidate.authority_pr==171' candidate/VF_PROJECT.json >/dev/null
test "$(git -C candidate rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find candidate/src/assets -type f -name '*.js' -print0 | xargs -0 -n1 node --check
git -C candidate diff --name-only "$SOURCE"...HEAD -- src | sort | tee "$EVID/runtime-delta.txt"
actual="$(tr '\n' ' ' < "$EVID/runtime-delta.txt")"
expected='src/VERSION.txt src/app/FunctionalWorkspaceShell.php src/app/bootstrap.php src/assets/auth-controls.js src/assets/workspace-rebaseline.css src/index.php '
test "$actual" = "$expected"
test "$(wc -l < "$EVID/runtime-delta.txt" | tr -d ' ')" = 6
grep -F 'data-vf-auth-login' candidate/src/app/FunctionalWorkspaceShell.php >/dev/null
grep -F 'data-vf-auth-logout' candidate/src/app/FunctionalWorkspaceShell.php >/dev/null
grep -F 'mobileAccountLabel.textContent=auth?' candidate/src/index.php >/dev/null
for needle in '管理员视角' '公开视角' '查看公开版' '返回管理' public_view preview_return; do
  ! grep -R -F "$needle" candidate/src/app/FunctionalWorkspaceShell.php candidate/src/assets/auth-controls.js
done
printf 'P01_V2362_EXACT_SOURCE=PASS\nP01_V2362_RUNTIME_DELTA_6=PASS\nP01_V2362_SCHEMA_CHANGE=NO\nP01_V2362_MIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' | tee "$EVID/boundary.txt"
'''

build=run_block(T,'Build deterministic candidate artifacts')
for old,new in [
    ('/tmp/p01-v2360-build.py','/tmp/p01-v2362-build.py'),
    ('V2.36.0','V2.36.2'),('V2360','V2362'),('v2360','v2362'),
    ('repair-v2.36.0.php','repair-v2.36.2.php'),
]:
    build=build.replace(old,new)
build=build.replace("required_added={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required_added.issubset(set(added)): raise SystemExit('required runtime additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('patch must not add/remove runtime files: '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual V2.35.3 to V2.36.0 Atomic upgrade')
atomic=atomic.replace('v2360','v2362').replace('V2360','V2362')
atomic=atomic.replace('2.35.3','__P01_SOURCE_VERSION__').replace('2.36.0','2.36.2').replace('__P01_SOURCE_VERSION__','2.36.1')
atomic=atomic.replace('P01_V2353_TO_V2362_ATOMIC','P01_V2361_TO_V2362_ATOMIC')

fresh=run_block(T,'Strict fresh candidate runtime')
fresh=fresh.replace('v2360','v2362').replace('V2360','V2362').replace('2.36.0','2.36.2')

auth_seed=run_block(A,'Fresh Runtime and seed')
auth_browser=run_block(A,'Chromium visible login logout gate')
auth_seed=auth_seed.replace('/tmp/p01-auth-entry-formal-r2','/tmp/p01-v2362-auth').replace('p01-auth-entry-formal-r2','p01-v2362-auth')
auth_browser=auth_browser.replace('/tmp/p01-auth-entry-formal-r2','/tmp/p01-v2362-auth').replace('p01-auth-entry-formal-r2','p01-v2362-auth')
auth_browser=auth_browser.replace('$GITHUB_WORKSPACE/runner/scripts/p01-auth-entry-browser-gate.cjs','$GITHUB_WORKSPACE/auth/scripts/p01-auth-entry-browser-gate.cjs')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic),('04-fresh.sh',fresh),('05-auth-seed.sh',auth_seed),('06-auth-browser.sh',auth_browser)]:
    p=Path('/tmp/p01-v2362-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    p.chmod(0o755)
