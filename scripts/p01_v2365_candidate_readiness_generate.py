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
test "$(git -C candidate rev-parse HEAD^)" = "$MAIN"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = "$VERSION"
test "$(cat candidate/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.36.5');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = "$SOURCE_VERSION"
jq -e '.production_version=="2.36.4" and .candidate_version=="2.36.5" and .schema_version=="2026082901" and .v2_36_5_release_candidate.schema_change==false and .v2_36_5_release_candidate.migration==null and .v2_36_5_release_candidate.release_authorized_by_owner==null and .current_change.release_authorized_by_owner==true and .published_release.version=="2.36.4" and .production_release.version=="2.36.4" and .v2_36_5_release_candidate.unknown_runtime_bytes==0' candidate/VF_PROJECT.json >/dev/null
test "$(git -C candidate rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find candidate/src/assets -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C candidate diff --name-only "$SOURCE" -- src | sort | tee "$EVID/runtime-delta.txt"
actual="$(tr '\n' ' ' < "$EVID/runtime-delta.txt")"
expected='src/VERSION.txt src/app/FunctionalWorkspace.php src/app/ResourceCoverCache.php src/app/bootstrap.php src/assets/resource-media.css src/assets/update-core.js src/assets/workspace-rebaseline.css '
test "$actual" = "$expected"
test "$(wc -l < "$EVID/runtime-delta.txt" | tr -d ' ')" = 7
# exact verified post-V2.36.4 product blobs
test "$(git -C candidate rev-parse HEAD:src/assets/update-core.js)" = f18284aefac9d02294be9667631d3ffdbb7de6d9
test "$(git -C candidate rev-parse HEAD:src/app/ResourceCoverCache.php)" = 629a3a8b964fcfd3c75728d2ca66070a900c7e1b
test "$(git -C candidate rev-parse HEAD:src/app/FunctionalWorkspace.php)" = 54df2b995db32d6de2b9e593e04037a1bf4eb610
test "$(git -C candidate rev-parse HEAD:src/assets/resource-media.css)" = ec8ca1a7e2ab4a829f939bb2442ea9af8297b873
test "$(git -C candidate rev-parse HEAD:src/assets/workspace-rebaseline.css)" = 2eeb8b057d96bb04222f14d2cb02fa48089a882e
grep -F 'confirmRuntimeThenReload(toVersion)' candidate/src/assets/update-core.js >/dev/null
grep -F "'apple-podcasts' => 2 * 1024 * 1024" candidate/src/app/ResourceCoverCache.php >/dev/null
grep -F "vf_asset_url('assets/resource-actions.css')" candidate/src/app/FunctionalWorkspace.php >/dev/null
! grep -F '@import url("resource-actions.css")' candidate/src/assets/resource-media.css >/dev/null
grep -F '.vf-functional-head>div{min-width:0}' candidate/src/assets/workspace-rebaseline.css >/dev/null
printf 'P01_V2365_EXACT_SOURCE=PASS\nP01_V2365_RUNTIME_DELTA_7=PASS\nVERIFIED_PRODUCT_BLOBS=5/5\nP01_V2365_SCHEMA_CHANGE=NO\nP01_V2365_MIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' | tee "$EVID/boundary.txt"
'''

build=run_block(T,'Build deterministic candidate artifacts')
for old,new in [('/tmp/p01-v2360-build.py','/tmp/p01-v2365-build.py'),('V2.36.0','V2.36.5'),('V2360','V2365'),('v2360','v2365'),('repair-v2.36.0.php','repair-v2.36.5.php')]: build=build.replace(old,new)
build=build.replace("required_added={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required_added.issubset(set(added)): raise SystemExit('required runtime additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('unexpected patch runtime add/remove boundary: '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual V2.35.3 to V2.36.0 Atomic upgrade')
atomic=atomic.replace('v2360','v2365').replace('V2360','V2365')
atomic=atomic.replace('2.35.3','__SOURCE__').replace('2.36.0','2.36.5').replace('__SOURCE__','2.36.4')
atomic=atomic.replace('P01_V2353_TO_V2365_ATOMIC','P01_V2364_TO_V2365_ATOMIC')

fresh=run_block(T,'Strict fresh candidate runtime')
fresh=fresh.replace('v2360','v2365').replace('V2360','V2365').replace('2.36.0','2.36.5')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic),('04-fresh.sh',fresh)]:
    p=Path('/tmp/p01-v2365-generated')/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(0o755)
