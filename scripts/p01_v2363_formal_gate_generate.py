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
test "$(git -C formal rev-parse origin/main)" = "$MAIN_EXPECTED"
test "$(git -C formal rev-parse origin/develop)" = "$DEVELOP_EXPECTED"
test "$(git -C formal rev-parse origin/develop^{tree})" = "$FORMAL_TREE"
test "$(git -C formal rev-parse origin/develop:src)" = "$FORMAL_RUNTIME_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(git -C production rev-parse HEAD:src)" = "$SOURCE_RUNTIME_TREE"
! git -C formal show-ref --verify --quiet refs/tags/v2.36.3
test "$(cat formal/VERSION)" = "$VERSION"
test "$(cat formal/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.36.3');" formal/src/app/bootstrap.php >/dev/null
python3 - <<'PY'
import json
D=json.load(open('formal/VF_PROJECT.json')); g=D['v2_36_3_candidate_gate']
assert D['production_version']=='2.36.2' and D['candidate_version']=='2.36.3' and D['schema_version']=='2026082901'
assert g['state']=='PASS' and g['candidate_readiness_run']==33501907010 and g['artifact']==9798055642
assert g['artifact_sha256']=='39225162784a38693175524142643866e8fafd9ed528324aa5fb4896829eacaa'
assert g['atomic_upgrade']=='V2.36.2 -> V2.36.3 PASS' and g['visual_readback'].startswith('PASS')
PY
test "$(git -C formal rev-parse HEAD:database)" = "$(git -C production rev-parse HEAD:database)"
find formal/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >"$EVID/php-syntax.txt"
find formal/src/assets -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >"$EVID/js-syntax.txt"
git -C formal diff --name-status "$SOURCE"...HEAD -- src | tee "$EVID/runtime-delta.txt"
actual="$(git -C formal diff --name-only "$SOURCE"...HEAD -- src | sort | tr '\n' ' ')"
expected='src/VERSION.txt src/app/FunctionalWorkspace.php src/app/bootstrap.php src/assets/workspace-domain-nav.css src/index.php src/start.php src/surface.php '
test "$actual" = "$expected"
added="$(git -C formal diff --diff-filter=A --name-only "$SOURCE"...HEAD -- src | tr '\n' ' ')"; test -z "$added"
removed="$(git -C formal diff --diff-filter=D --name-only "$SOURCE"...HEAD -- src | tr '\n' ' ')"; test -z "$removed"
grep -F "require_once __DIR__ . '/app/FunctionalWorkspace.php';" formal/src/index.php >/dev/null
grep -F "require __DIR__ . '/index.php';" formal/src/start.php >/dev/null
grep -F 'vf_security_headers(true);' formal/src/index.php >/dev/null
grep -F 'vf_security_headers(true);' formal/src/surface.php >/dev/null
grep -F 'background:var(--ws-bg)' formal/src/assets/workspace-domain-nav.css >/dev/null
! grep -F 'var(--ws-topbar) + 8px' formal/src/assets/workspace-domain-nav.css >/dev/null
! grep -F 'frontend-legacy.css' formal/src/index.php >/dev/null
for needle in public_view preview_return '管理员视角' '公开视角' '查看公开版' '返回管理'; do ! grep -R -F "$needle" formal/src/index.php formal/src/start.php formal/src/surface.php formal/src/app/FunctionalWorkspace.php; done
printf 'P01_V2363_FORMAL_FENCE=PASS\nFORMAL=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nCANDIDATE_GATE=%s/PASS\nDEVELOP=%s\nDEVELOP_TREE_IDENTITY=PASS\nOWNER_PRODUCTION_WRITE=NO\n' "$FORMAL" "$FORMAL_TREE" "$FORMAL_RUNTIME_TREE" "$SCHEMA" "$CANDIDATE_GATE" "$DEVELOP_EXPECTED" | tee "$EVID/fence.txt"
'''

build=run_block(T,'Build deterministic formal release artifacts')
for old,new in [
    ('/tmp/p01-v2360-formal-build.py','/tmp/p01-v2363-formal-build.py'),
    ('/tmp/p01-v2360-formal-first','/tmp/p01-v2363-formal-first'),
    ('P01_V2360','P01_V2363'),('p01-v2360','p01-v2363'),('V2.36.0','V2.36.3'),('v2.36.0','v2.36.3'),
    ('2.35.3','__SOURCE_VERSION__'),('2.36.0','2.36.3'),('__SOURCE_VERSION__','2.36.2'),
]: build=build.replace(old,new)
build=build.replace("required={'app/ResourceCoverCache.php','app/ResourceMetadata.php','resource-cover-refresh.php'}\nif not required.issubset(set(added)): raise SystemExit('formal additions missing '+json.dumps(added))", "if added or removed: raise SystemExit('formal runtime add/remove fence failed '+json.dumps({'added':added,'removed':removed}))")

atomic=run_block(T,'Actual formal V2.35.3 to V2.36.0 upgrade')
for old,new in [('p01-v2360','p01-v2363'),('P01_V2360','P01_V2363')]: atomic=atomic.replace(old,new)
atomic=atomic.replace('2.35.3','__SOURCE_VERSION__').replace('2.36.0','2.36.3').replace('__SOURCE_VERSION__','2.36.2')
atomic=atomic.replace('P01_V2353_TO_V2363','P01_V2362_TO_V2363')

for name,text in [('01-exact.sh',exact),('02-build.sh',build),('03-atomic.sh',atomic)]:
    p=Path('/tmp/p01-v2363-formal-generated')/name
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(0o755)
