from pathlib import Path

T=Path('template/.github/workflows/p01-v2360-candidate-readiness-20260901.yml').read_text().splitlines()

def run_block(lines,name):
    marker='      - name: '+name
    start=lines.index(marker); run=None
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
test "$(git -C candidate rev-parse HEAD^)" = "$HOTFIX"
test "$(git -C candidate rev-parse HEAD^^)" = "$MAIN"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
test "$(cat candidate/VERSION)" = "$VERSION"
test "$(cat candidate/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.37.3');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = "$SOURCE_VERSION"
jq -e '.production_version=="2.37.2" and .published_release.version=="2.37.2" and .production_release.version=="2.37.2" and .candidate_version=="2.37.3" and .schema_version=="2026082901" and .v2_37_3_release_candidate.schema_change==false and .v2_37_3_release_candidate.migration==null and .current_change.release_authorized_by_owner==true' candidate/VF_PROJECT.json >/dev/null
test "$(git -C candidate rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find candidate/src/assets -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C candidate diff --name-only "$SOURCE" -- src | sort | tee "$EVID/runtime-delta.txt"
actual="$(tr '\n' ' ' < "$EVID/runtime-delta.txt")"
expected='src/VERSION.txt src/app/ResourceCoverCache.php src/app/bootstrap.php src/assets/workspace.js '
test "$actual" = "$expected"
test "$(wc -l < "$EVID/runtime-delta.txt" | tr -d ' ')" = 4
test -z "$(git -C candidate diff --diff-filter=A --name-only "$SOURCE" -- src)"
test -z "$(git -C candidate diff --diff-filter=D --name-only "$SOURCE" -- src)"
grep -F "mview.iyf.tv" candidate/src/app/ResourceCoverCache.php >/dev/null
grep -F "https://www.iyf.tv" candidate/src/app/ResourceCoverCache.php >/dev/null
grep -F "'image/gif'=>'gif'" candidate/src/app/ResourceCoverCache.php >/dev/null
grep -F 'vf-cover-retry:v4:' candidate/src/assets/workspace.js >/dev/null
grep -F "\$extMap = ['image/webp'=>'webp','image/jpeg'=>'jpg','image/png'=>'png'];" candidate/src/app/ResourceAssetStore.php >/dev/null
printf 'P01_V2373_EXACT_SOURCE=PASS\nRUNTIME_DELTA_4=PASS\nAUTO_GIF=PASS\nMANUAL_UPLOAD_UNCHANGED=PASS\nSCHEMA_CHANGE=NO\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' | tee "$EVID/boundary.txt"
'''

build=run_block(T,'Build deterministic candidate artifacts')
for old,new in [
    ('/tmp/p01-v2360-build.py','/tmp/p01-v2373-build.py'),
    ('/tmp/p01-v2360-first','/tmp/p01-v2373-first'),
    ('P01_V2360','P01_V2373'),('p01-v2360','p01-v2373'),('V2.36.0','V2.37.3'),('v2.36.0','v2.37.3'),
    ('repair-v2.36.0.php','repair-v2.37.3.php'),
]: build=build.replace(old,new)
build=build.replace("required_added={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required_added.issubset(set(added)): raise SystemExit('required runtime additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('unexpected hotfix runtime add/remove boundary '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual V2.35.3 to V2.36.0 Atomic upgrade')
for old,new in [('p01-v2360','p01-v2373'),('P01_V2360','P01_V2373')]: atomic=atomic.replace(old,new)
atomic=atomic.replace('2.35.3','__SOURCE__').replace('2.36.0','2.37.3').replace('__SOURCE__','2.37.2')
atomic=atomic.replace('P01_V2353_TO_V2373_ATOMIC','P01_V2372_TO_V2373_ATOMIC')

fresh=run_block(T,'Strict fresh candidate runtime')
for old,new in [('p01-v2360','p01-v2373'),('P01_V2360','P01_V2373'),('2.36.0','2.37.3')]: fresh=fresh.replace(old,new)

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic),('04-fresh.sh',fresh)]:
    p=Path('/tmp/p01-v2373-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(0o755)
