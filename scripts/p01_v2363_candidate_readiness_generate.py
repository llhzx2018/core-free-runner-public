from pathlib import Path

T=Path('template/.github/workflows/p01-v2360-candidate-readiness-20260901.yml').read_text().splitlines()

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
grep -Fx "define('VF_VERSION', '2.36.3');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = "$SOURCE_VERSION"
jq -e '.production_version=="2.36.2" and .candidate_version=="2.36.3" and .schema_version=="2026082901" and .v2_36_3_release_candidate.schema_change==false and .v2_36_3_release_candidate.migration==null and .v2_36_3_release_candidate.one_frontend_product_pr==179 and .v2_36_3_release_candidate.sticky_product_pr==176 and .production_release.production_closure=="BLOCKED / KNOWN P0 DUAL-SHELL DEFECT"' candidate/VF_PROJECT.json >/dev/null
test "$(git -C candidate rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find candidate/src/assets -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C candidate diff --name-only "$SOURCE"...HEAD -- src | sort | tee "$EVID/runtime-delta.txt"
actual="$(tr '\n' ' ' < "$EVID/runtime-delta.txt")"
expected='src/VERSION.txt src/app/FunctionalWorkspace.php src/app/bootstrap.php src/assets/workspace-domain-nav.css src/index.php src/start.php src/surface.php '
test "$actual" = "$expected"
test "$(wc -l < "$EVID/runtime-delta.txt" | tr -d ' ')" = 7
grep -F "require_once __DIR__ . '/app/FunctionalWorkspace.php';" candidate/src/index.php >/dev/null
grep -F "require __DIR__ . '/index.php';" candidate/src/start.php >/dev/null
grep -F 'vf-functional-workspace' candidate/src/app/FunctionalWorkspace.php >/dev/null
grep -F 'vf_security_headers(true);' candidate/src/index.php >/dev/null
grep -F 'vf_security_headers(true);' candidate/src/surface.php >/dev/null
grep -F 'background:var(--ws-bg)' candidate/src/assets/workspace-domain-nav.css >/dev/null
! grep -F 'var(--ws-topbar) + 8px' candidate/src/assets/workspace-domain-nav.css >/dev/null
! grep -F 'frontend-legacy.css' candidate/src/index.php >/dev/null
for needle in '管理员视角' '公开视角' '查看公开版' '返回管理' public_view preview_return; do
  ! grep -R -F "$needle" candidate/src/index.php candidate/src/start.php candidate/src/surface.php candidate/src/app/FunctionalWorkspace.php
done
printf 'P01_V2363_EXACT_SOURCE=PASS\nP01_V2363_RUNTIME_DELTA_7=PASS\nP01_V2363_SCHEMA_CHANGE=NO\nP01_V2363_MIGRATION=NONE\nONE_FRONTEND_STATIC=PASS\nSTICKY_STATIC=PASS\nOWNER_PRODUCTION_WRITE=NO\n' | tee "$EVID/boundary.txt"
'''

build=run_block(T,'Build deterministic candidate artifacts')
for old,new in [
    ('/tmp/p01-v2360-build.py','/tmp/p01-v2363-build.py'),
    ('V2.36.0','V2.36.3'),('V2360','V2363'),('v2360','v2363'),
    ('repair-v2.36.0.php','repair-v2.36.3.php'),
]:
    build=build.replace(old,new)
build=build.replace("required_added={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required_added.issubset(set(added)): raise SystemExit('required runtime additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('unexpected patch runtime add/remove boundary: '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual V2.35.3 to V2.36.0 Atomic upgrade')
atomic=atomic.replace('v2360','v2363').replace('V2360','V2363')
atomic=atomic.replace('2.35.3','__P01_SOURCE_VERSION__').replace('2.36.0','2.36.3').replace('__P01_SOURCE_VERSION__','2.36.2')
atomic=atomic.replace('P01_V2353_TO_V2363_ATOMIC','P01_V2362_TO_V2363_ATOMIC')

fresh=run_block(T,'Strict fresh candidate runtime')
fresh=fresh.replace('v2360','v2363').replace('V2360','V2363').replace('2.36.0','2.36.3')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic),('04-fresh.sh',fresh)]:
    p=Path('/tmp/p01-v2363-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text)
    p.chmod(0o755)
