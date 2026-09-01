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
grep -Fx "define('VF_VERSION', '2.37.0');" candidate/src/app/bootstrap.php >/dev/null
test "$(cat production/VERSION)" = "$SOURCE_VERSION"
jq -e '.production_version=="2.36.5" and .candidate_version=="2.37.0" and .schema_version=="2026082901" and .v2_37_0_release_candidate.schema_change==false and .v2_37_0_release_candidate.migration==null and .current_change.release_authorized_by_owner==true and .published_release.version=="2.36.5" and .production_release.version=="2.36.5" and .v2_37_0_release_candidate.unknown_runtime_bytes==0' candidate/VF_PROJECT.json >/dev/null
test "$(git -C candidate rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find candidate/src/assets candidate/src/browser-extension -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C candidate diff --name-only "$SOURCE" -- src | sort | tee "$EVID/runtime-delta.txt"
cat >"$EVID/runtime-expected.txt" <<'EOF'
src/VERSION.txt
src/app/AdminShell.php
src/app/FunctionalHome.php
src/app/FunctionalWorkspace.php
src/app/FunctionalWorkspaceShell.php
src/app/Repository.php
src/app/SurfaceRepository.php
src/app/bootstrap.php
src/assets/admin-pages.css
src/assets/links-admin.js
src/assets/resource-actions.css
src/assets/surface-workspace.css
src/assets/transfer.js
src/assets/workspace-create-bundle.js
src/assets/workspace-home.css
src/assets/workspace-rebaseline.css
src/assets/workspace-rebaseline.js
src/browser-extension/README.md
src/browser-extension/background.js
src/browser-extension/manifest.json
src/browser-extension/options.html
src/browser-extension/popup.js
src/browser-helper.php
src/duplicates.php
src/health.php
src/links-admin.php
src/quick-save.php
src/surface-manager.php
src/transfer.php
src/workspace-create.php
EOF
diff -u "$EVID/runtime-expected.txt" "$EVID/runtime-delta.txt"
test "$(wc -l < "$EVID/runtime-delta.txt" | tr -d ' ')" = 30
# Preserve all V2.36.5 production fixes while adding Wave 1-13.
grep -F 'confirmRuntimeThenReload(toVersion)' candidate/src/assets/update-core.js >/dev/null
grep -F "'youtube' => \$candidates === [] ? 3 * 1024 * 1024 : 524288" candidate/src/app/ResourceCoverCache.php >/dev/null
grep -F "'apple-podcasts' => 2 * 1024 * 1024" candidate/src/app/ResourceCoverCache.php >/dev/null
grep -F "vf_asset_url('assets/resource-actions.css')" candidate/src/app/FunctionalWorkspace.php >/dev/null
! grep -F '@import url("resource-actions.css")' candidate/src/assets/resource-media.css >/dev/null
grep -F '.vf-functional-head>div{min-width:0}' candidate/src/assets/workspace-rebaseline.css >/dev/null
# Wave 1-13 main user-journey contracts.
grep -F '搜索我的互联网' candidate/src/app/FunctionalWorkspace.php >/dev/null
grep -F 'data-prefill-url' candidate/src/app/FunctionalWorkspace.php >/dev/null
grep -F 'savePendingCapture' candidate/src/quick-save.php >/dev/null
grep -F "is_pending']??0)===1" candidate/src/surface-manager.php >/dev/null
grep -F 'categorySuggestions' candidate/src/surface-manager.php >/dev/null
grep -F '撤销' candidate/src/assets/links-admin.js >/dev/null
grep -F '导入浏览器书签' candidate/src/transfer.php >/dev/null
grep -F 'recentAssets' candidate/src/app/FunctionalHome.php >/dev/null
printf 'P01_V2370_EXACT_SOURCE=PASS\nP01_V2370_RUNTIME_DELTA_30=PASS\nP01_V2365_FIX_PRESERVATION=PASS\nP01_WAVE_1_13_CONTRACT=PASS\nP01_V2370_SCHEMA_CHANGE=NO\nP01_V2370_MIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' | tee "$EVID/boundary.txt"
'''

build=run_block(T,'Build deterministic candidate artifacts')
for old,new in [('/tmp/p01-v2360-build.py','/tmp/p01-v2370-build.py'),('V2.36.0','V2.37.0'),('V2360','V2370'),('v2360','v2370'),('repair-v2.36.0.php','repair-v2.37.0.php')]: build=build.replace(old,new)
build=build.replace("required_added={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required_added.issubset(set(added)): raise SystemExit('required runtime additions missing '+json.dumps(added))", "if added != ['quick-save.php'] or removed: raise SystemExit('unexpected V2.37.0 add/remove boundary '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual V2.35.3 to V2.36.0 Atomic upgrade')
atomic=atomic.replace('v2360','v2370').replace('V2360','V2370')
atomic=atomic.replace('2.35.3','__SOURCE__').replace('2.36.0','2.37.0').replace('__SOURCE__','2.36.5')
atomic=atomic.replace('P01_V2353_TO_V2370_ATOMIC','P01_V2365_TO_V2370_ATOMIC')
atomic=atomic.replace('test -f "$UPGRADE/resource-cover-refresh.php"', 'test -f "$UPGRADE/resource-cover-refresh.php"; test -f "$UPGRADE/quick-save.php"')

fresh=run_block(T,'Strict fresh candidate runtime')
fresh=fresh.replace('v2360','v2370').replace('V2360','V2370').replace('2.36.0','2.37.0')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic),('04-fresh.sh',fresh)]:
    p=Path('/tmp/p01-v2370-generated')/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(0o755)
