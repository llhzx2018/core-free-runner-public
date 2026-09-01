from pathlib import Path

T=Path('template/.github/workflows/p01-v2360-candidate-readiness-20260901.yml').read_text().splitlines()
A=Path('auth/.github/workflows/p01-single-system-auth-formal-gate-r2-20260901.yml').read_text().splitlines()

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
grep -Fx "define('VF_VERSION', '2.36.1');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = "$SOURCE_VERSION"
jq -e '.production_version=="2.36.0" and .candidate_version=="2.36.1" and .schema_version=="2026082901" and .v2_36_1_release_candidate.schema_change==false and .v2_36_1_release_candidate.migration==null and .v2_36_1_release_candidate.product_fix_merge=="2b60b27c1e5cb53f841e9e7f0c8e521bacba1030"' candidate/VF_PROJECT.json >/dev/null
test "$(git -C candidate rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find candidate/src/assets -type f -name '*.js' -print0 | xargs -0 -n1 node --check
git -C candidate diff --name-only "$SOURCE"...HEAD -- src | sort | tee "$EVID/runtime-delta.txt"
actual="$(tr '\n' ' ' < "$EVID/runtime-delta.txt")"
expected='src/VERSION.txt src/api.php src/app/FunctionalWorkspace.php src/app/FunctionalWorkspaceCore.php src/app/FunctionalWorkspaceShell.php src/app/bootstrap.php src/assets/frontend.css src/assets/workspace-domain-nav.css src/index.php src/start.php '
test "$actual" = "$expected"
for needle in public_view preview_return vf_fw_public_preview_requested vf-global-view-state vf-view-state 管理员视角 公开视角 查看公开版 返回管理; do
  ! git -C candidate grep -n -F "$needle" -- src/api.php src/app/FunctionalWorkspace.php src/app/FunctionalWorkspaceCore.php src/app/FunctionalWorkspaceShell.php src/assets/frontend.css src/assets/workspace-domain-nav.css src/index.php src/start.php
done
printf 'P01_V2361_EXACT_SOURCE=PASS\nP01_V2361_RUNTIME_DELTA_10=PASS\nP01_V2361_SCHEMA_CHANGE=NO\nP01_V2361_MIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' | tee "$EVID/boundary.txt"
'''

build=run_block(T,'Build deterministic candidate artifacts')
for old,new in [
    ('/tmp/p01-v2360-build.py','/tmp/p01-v2361-build.py'),
    ('V2.36.0','V2.36.1'),('V2360','V2361'),('v2360','v2361'),
    ('repair-v2.36.0.php','repair-v2.36.1.php'),
]:
    build=build.replace(old,new)
build=build.replace("required_added={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required_added.issubset(set(added)): raise SystemExit('required runtime additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('patch must not add/remove runtime files: '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual V2.35.3 to V2.36.0 Atomic upgrade')
atomic=atomic.replace('v2360','v2361').replace('V2360','V2361')
atomic=atomic.replace('2.35.3','__P01_SOURCE_VERSION__').replace('2.36.0','2.36.1').replace('__P01_SOURCE_VERSION__','2.36.0')
atomic=atomic.replace('P01_V2353_TO_V2361_ATOMIC','P01_V2360_TO_V2361_ATOMIC')
atomic=atomic.replace('test -f "$UPGRADE/app/ResourceCoverCache.php"; test -f "$UPGRADE/app/ResourceMetadata.php"; test -f "$UPGRADE/resource-cover-refresh.php"\n','')

fresh=run_block(T,'Strict fresh candidate runtime')
fresh=fresh.replace('v2360','v2361').replace('V2360','V2361').replace('2.36.0','2.36.1')

auth_seed=run_block(A,'Fresh Runtime and seed')
auth_browser=run_block(A,'Chromium auth-state gate')
auth_seed=auth_seed.replace('/tmp/p01-single-system-auth-r2','/tmp/p01-v2361-auth').replace('p01-single-system-auth-r2','p01-v2361-auth')
auth_browser=auth_browser.replace('/tmp/p01-single-system-auth-r2','/tmp/p01-v2361-auth').replace('p01-single-system-auth-r2','p01-v2361-auth')
auth_browser=auth_browser.replace("A(t.includes('资源管理')&&t.includes('系统设置'),`admin management labels missing ${route}`);","if(width===1440)A(t.includes('资源管理')&&t.includes('系统设置'),`admin management labels missing ${route}`);")
auth_browser=auth_browser.replace("A(await visibleCount(p,'a[href=\"links-admin.php\"]')>0,`admin resource management missing ${route}`);A(await visibleCount(p,'a[href=\"settings.php\"]')>0,`admin settings missing ${route}`);","A(await p.locator('a[href=\"links-admin.php\"]').count()>0,`admin resource management DOM missing ${route}`);A(await p.locator('a[href=\"settings.php\"]').count()>0,`admin settings DOM missing ${route}`);if(width===1440){A(await visibleCount(p,'a[href=\"links-admin.php\"]')>0,`admin resource management not visible ${route}`);A(await visibleCount(p,'a[href=\"settings.php\"]')>0,`admin settings not visible ${route}`);}")
auth_browser=auth_browser.replace("A(t.includes('资源管理')&&t.includes('系统设置'),`old query hides management ${route}`);","A(await p.locator('a[href=\"links-admin.php\"]').count()>0&&await p.locator('a[href=\"settings.php\"]').count()>0,`old query hides management ${route}`);if(width===1440)A(t.includes('资源管理')&&t.includes('系统设置'),`old query hides visible management ${route}`);")

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic),('04-fresh.sh',fresh),('05-auth-seed.sh',auth_seed),('06-auth-browser.sh',auth_browser)]:
    p=Path('/tmp/p01-v2361-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    p.chmod(0o755)
