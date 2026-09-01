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
! git -C formal show-ref --verify --quiet refs/tags/v2.37.0
test "$(cat formal/VERSION)" = "$VERSION"
test "$(cat formal/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.37.0');" formal/src/app/bootstrap.php >/dev/null
python3 - <<'PY'
import json
D=json.load(open('formal/VF_PROJECT.json')); c=D['v2_37_0_release_candidate']
assert D['production_version']=='2.36.5' and D['candidate_version']=='2.37.0' and D['schema_version']=='2026082901'
assert c['candidate_source']=='0020ddc866f888a5d9485d3abfd3ae664a15cb7d'
assert c['candidate_tree']=='04b5833614997afe51e542720ec6e1d5e5196592'
assert c['candidate_runtime_tree']=='057fbba8822950f163aa322d99b889ed3ab24842'
assert c['candidate_readiness_gate']==33567195059 and c['candidate_readiness_artifact']==9823578793
assert c['candidate_readiness_artifact_digest']=='sha256:aad7d03454c9063ee72c48e5158653a9494e8caa7f2f8d378044545da464edcb'
assert c['unknown_runtime_bytes']==0 and c['schema_change'] is False and c['migration'] is None
assert D['current_change']['release_authorized_by_owner'] is True
PY
test "$(git -C formal rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find formal/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find formal/src/assets formal/src/browser-extension -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C formal diff --name-only "$SOURCE" HEAD -- src | sort | tee "$EVID/runtime-delta.txt"
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
test "$(git -C formal diff --diff-filter=A --name-only "$SOURCE" HEAD -- src)" = src/quick-save.php
test -z "$(git -C formal diff --diff-filter=D --name-only "$SOURCE" HEAD -- src)"
grep -F 'confirmRuntimeThenReload(toVersion)' formal/src/assets/update-core.js >/dev/null
grep -F "'apple-podcasts' => 2 * 1024 * 1024" formal/src/app/ResourceCoverCache.php >/dev/null
grep -F "vf_asset_url('assets/resource-actions.css')" formal/src/app/FunctionalWorkspace.php >/dev/null
! grep -F '@import url("resource-actions.css")' formal/src/assets/resource-media.css >/dev/null
grep -F '.vf-functional-head>div{min-width:0}' formal/src/assets/workspace-rebaseline.css >/dev/null
grep -F 'savePendingCapture' formal/src/quick-save.php >/dev/null
grep -F 'categorySuggestions' formal/src/surface-manager.php >/dev/null
printf 'P01_V2370_FORMAL_FENCE=PASS\nFORMAL=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nCANDIDATE_GATE=%s/PASS\nRUNTIME_DELTA=30\nADDED=src/quick-save.php\nOWNER_PRODUCTION_WRITE=NO\n' "$FORMAL" "$FORMAL_TREE" "$FORMAL_RUNTIME_TREE" "$SCHEMA" "$CANDIDATE_GATE" | tee "$EVID/fence.txt"
'''

build=run_block(T,'Build deterministic formal release artifacts')
for old,new in [('/tmp/p01-v2360-formal-build.py','/tmp/p01-v2370-formal-build.py'),('/tmp/p01-v2360-formal-first','/tmp/p01-v2370-formal-first'),('P01_V2360','P01_V2370'),('p01-v2360','p01-v2370'),('V2.36.0','V2.37.0'),('v2.36.0','v2.37.0'),('2.35.3','__SOURCE_VERSION__'),('2.36.0','2.37.0'),('__SOURCE_VERSION__','2.36.5')]: build=build.replace(old,new)
build=build.replace("required={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required.issubset(set(added)): raise SystemExit('formal additions missing '+json.dumps(added))", "if added != ['quick-save.php'] or removed: raise SystemExit('formal V2.37.0 add/remove fence failed '+json.dumps({'added':added,'removed':removed}))")
build=build.replace('FORMAL_ARTIFACT_GATE_PASS_PENDING_RUNTIME','FORMAL_ARTIFACT_GATE_PASS')

atomic=run_block(T,'Actual formal V2.35.3 to V2.36.0 upgrade')
for old,new in [('p01-v2360','p01-v2370'),('P01_V2360','P01_V2370')]: atomic=atomic.replace(old,new)
atomic=atomic.replace('2.35.3','__SOURCE_VERSION__').replace('2.36.0','2.37.0').replace('__SOURCE_VERSION__','2.36.5')
atomic=atomic.replace('test -f "$UPGRADE/resource-cover-refresh.php"', 'test -f "$UPGRADE/resource-cover-refresh.php"; test -f "$UPGRADE/quick-save.php"')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic)]:
    p=Path('/tmp/p01-v2370-formal-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(0o755)
