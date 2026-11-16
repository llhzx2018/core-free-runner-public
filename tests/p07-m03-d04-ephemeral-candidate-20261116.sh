#!/usr/bin/env bash
# P07-M03-D04 服务器迁移 — ephemeral package build/CLI smoke only.
# PUBLIC Runner never stores private code or archive; deletes after tests.
set -Eeuo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
readonly EXPECTED_SOURCE_SHA="54c4b4fbd89fe4c7035e599d90b69add3257e77a"
readonly CANDIDATE_ID="0.1.0-d04-trial-54c4b4fb"
readonly SOURCE="$(pwd)/.p07-private-exact"
WORK="$(mktemp -d -t p07-d04-ephemeral-candidate.XXXXXXXX)"
readonly OUT="$WORK/private-out"
readonly SAFE_PROOF="$(pwd)/public-proof"
cleanup() { rm -rf -- "$WORK"; }
trap cleanup EXIT
test -d "$SOURCE/.git"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_SOURCE_SHA"
test "$(cat "$SOURCE/VERSION")" = "0.1.0"
test -f "$SOURCE/BUILD_ID"
test -f "$SOURCE/bin/vfops"
test -f "$SOURCE/lib/server_migration_pull.py"
test -f "$SOURCE/lib/migration_source_sql_preimport_protection.py"
test -f "$SOURCE/lib/migration_prepared_static_snapshot.py"
test ! -e "$SAFE_PROOF"
mkdir -m 700 -p "$SAFE_PROOF" "$OUT" "$WORK/stage/vfops" "$WORK/test" "$WORK/test/releases" "$WORK/test/owner-data"
# Product source comes solely from the exact immutable private commit.
# git archive exports only tracked runtime paths and never exports .git.
git -C "$SOURCE" archive --format=tar HEAD \
    bin lib scripts components VERSION BUILD_ID |
    tar -x -f - -C "$WORK/stage/vfops"
test -f "$WORK/stage/vfops/lib/migration_matched_engine.py"
test -f "$WORK/stage/vfops/lib/migration_site_ingress_fence.py"
test -f "$WORK/stage/vfops/bin/vfops-migrate-ui"
# Source code itself remains identical; only the offline trial build identity
# is stamped in the distribution copy, with the exact transformation recorded.
printf '%s\n' "$CANDIDATE_ID" > "$WORK/stage/vfops/BUILD_ID"
SOURCE_BUILD_ID="$(cat "$SOURCE/BUILD_ID")"
export SOURCE_BUILD_ID
python3 - "$WORK/stage/vfops" "$EXPECTED_SOURCE_SHA" "$CANDIDATE_ID" <<'PY'
import json, pathlib, sys
root, sha, trial = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
assert len(sha)==40 and sha.isalnum()
(root/"TRIAL_CANDIDATE.json").write_text(
    json.dumps({
        "schema":"p07.m03.d04.private-trial.v1",
        "product_commit":sha,
        "version":"0.1.0",
        "source_build_id":__import__("os").environ["SOURCE_BUILD_ID"],
        "trial_build_id":trial,
        "trial_only":True,
        "formal_release":False,
        "production_approved":False,
        "source_stop_or_dns_change_authorized":False,
        "candidate_install_path":"NOT_ACTIVATED",
        "change_from_exact_git":["BUILD_ID","TRIAL_CANDIDATE.json"],
    },indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
PY
test "$(cat "$WORK/stage/vfops/BUILD_ID")" = "$CANDIDATE_ID"
test -f "$WORK/stage/vfops/TRIAL_CANDIDATE.json"
# Prevent obvious private config/keys/backup data from leaking into a private
# candidate even if accidentally tracked in an allowed runtime directory.
python3 - "$WORK/stage/vfops" <<'PY'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
blocked={"id_rsa","id_ed25519",".env","credentials.json","secret.json","token","*.pem"}
items=list(root.rglob("*"))
assert len(items)<10000
for item in items:
    rel=item.relative_to(root)
    assert not item.is_symlink(), "unexpected candidate symlink"
    assert item.is_file() or item.is_dir(), "unexpected nonregular candidate payload"
    parts=[p.lower() for p in rel.parts]
    assert not any(p in {".ssh",".git",".github","__pycache__","private","backups"} for p in parts)
    assert not any(p in {"id_rsa","id_ed25519",".env","credentials.json","secret.json","token"} or p.endswith((".pem",".key",".sqlite",".sql",".gz",".zip",".tar")) for p in parts)
    if item.is_file():
        assert item.stat().st_size < 6*1024*1024
print("P07_D04_PRIVATE_CANDIDATE_TRACKED_RUNTIME_SANITIZE=PASS")
PY
export PYTHONPYCACHEPREFIX="$WORK/pycache"
python3 -m compileall -q "$WORK/stage/vfops/lib"
bash -n "$WORK/stage/vfops/bin/vfops"
bash -n "$WORK/stage/vfops/bin/vfops-migrate-ui"
find "$WORK/stage/vfops/lib" -name '*.sh' -type f -print0 |
  xargs -0 -r -n1 bash -n
"$WORK/stage/vfops/bin/vfops" --version | grep -Fqx "VF Server Ops 0.1.0"
"$WORK/stage/vfops/bin/vfops" --help | grep -Fq "server-migrate plan"
python3 "$WORK/stage/vfops/lib/server_migration_pull.py" --help > "$WORK/cli-help"
grep -Fq "_stage-prepared-static-online" "$WORK/cli-help"
grep -Fq "failed-prepare-audit" "$WORK/cli-help"
echo P07_D04_PRIVATE_CANDIDATE_ROOTLESS_CLI_SMOKE=PASS
# Exercise a separate synthetic release pointer, without touching /opt,
# existing website files, databases or the host's /usr/local/bin.
cp -a "$WORK/stage/vfops" "$WORK/test/releases/previous"
printf '%s\n' "0.1.0-release136" > "$WORK/test/releases/previous/BUILD_ID"
printf '%s\n' "OWNER_DATA_CANARY_KEEP" > "$WORK/test/owner-data/existing-database-simulated"
(
  cd "$WORK/test"
  ln -s "releases/previous" current
  test "$(cat current/BUILD_ID)" = "0.1.0-release136"
)
# Negative injection: an incomplete "release" is not eligible for switching.
mkdir "$WORK/test/releases/broken"
if test -f "$WORK/test/releases/broken/bin/vfops"; then
  echo "Unexpected installed broken candidate" >&2
  exit 7
fi
test "$(readlink "$WORK/test/current")" = "releases/previous"
# Independent full payload extracted as a second release generation.
cp -a "$WORK/stage/vfops" "$WORK/test/releases/next"
"$WORK/test/releases/next/bin/vfops" --help >/dev/null
ln -s "releases/next" "$WORK/test/current.next"
mv -Tf "$WORK/test/current.next" "$WORK/test/current"
test "$(cat "$WORK/test/current/BUILD_ID")" = "$CANDIDATE_ID"
# Bounded failure drill: revert pointer without replacing the existing release.
ln -s "releases/previous" "$WORK/test/current.rollback"
mv -Tf "$WORK/test/current.rollback" "$WORK/test/current"
test "$(cat "$WORK/test/current/BUILD_ID")" = "0.1.0-release136"
test "$(cat "$WORK/test/owner-data/existing-database-simulated")" = "OWNER_DATA_CANARY_KEEP"
echo P07_D04_PRIVATE_CANDIDATE_ISOLATED_POINTER_SWITCH_AND_ROLLBACK=PASS
CANDIDATE_FILE="vfops-p07-m03-d04-trial-54c4b4fb.tar.gz"
tar -C "$WORK/stage" --sort=name --mtime="@0" --numeric-owner \
  --owner=0 --group=0 --format=gnu -czf "$OUT/$CANDIDATE_FILE" vfops
test -s "$OUT/$CANDIDATE_FILE"
tar -tzf "$OUT/$CANDIDATE_FILE" | grep -Fxq "vfops/TRIAL_CANDIDATE.json"
tar -tzf "$OUT/$CANDIDATE_FILE" | grep -Fxq "vfops/bin/vfops"
tar -tzf "$OUT/$CANDIDATE_FILE" | grep -Fxq "vfops/lib/server_migration_pull.py"
tar -tzf "$OUT/$CANDIDATE_FILE" | grep -Fxq "vfops/lib/migration_prepared_static_snapshot.py"
(
 cd "$OUT"
 sha256sum "$CANDIDATE_FILE" > "$CANDIDATE_FILE.sha256"
 sha256sum -c "$CANDIDATE_FILE.sha256"
)
python3 - "$OUT" "$CANDIDATE_FILE" "$EXPECTED_SOURCE_SHA" "$CANDIDATE_ID" <<'PY'
import hashlib,json,pathlib,sys
out,name,source,build=pathlib.Path(sys.argv[1]),sys.argv[2],sys.argv[3],sys.argv[4]
pkg=out/name
digest=hashlib.sha256(pkg.read_bytes()).hexdigest()
assert len(digest)==64 and pkg.stat().st_size>0
(out/"candidate-proof.json").write_text(
    json.dumps({
      "schema":"p07.m03.d04.trial-build-proof.v1",
      "exact_product_commit":source,
      "candidate_build_id":build,
      "file":name,
      "sha256":digest,
      "bytes":pkg.stat().st_size,
      "scope":"PRIVATE_ISOLATED_OFFLINE_TRIAL",
      "rootless_install_smoke":"PASS",
      "sandbox_pointer_rollback":"PASS",
      "real_cloudpanel_install":"NOT_RUN",
      "real_two_host_migration":"NOT_RUN",
      "formal_release":"NO",
      "production":"NO",
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
print("P07_D04_EPHEMERAL_ARCHIVE_DIGEST="+digest)
print("P07_D04_EPHEMERAL_ARCHIVE_BYTES="+str(pkg.stat().st_size))
PY
echo P07_D04_PRIVATE_CANDIDATE_ARCHIVE_INTEGRITY=PASS
echo P07_D04_PRIVATE_CANDIDATE_OWNER_DISTRIBUTION=NOT_RUN

# Deliver only metadata. Private archive and extracted source stay inside the
# disposable runner workspace; private source never uploaded or committed.
python3 - "$OUT/candidate-proof.json" "$SAFE_PROOF/candidate-proof.json" <<'PY'
import json, pathlib, sys
source, target=map(pathlib.Path, sys.argv[1:])
data=json.loads(source.read_text(encoding="utf-8"))
allowed={"schema","exact_product_commit","candidate_build_id","file","sha256",
         "bytes","scope","rootless_install_smoke","sandbox_pointer_rollback",
         "real_cloudpanel_install","real_two_host_migration","formal_release",
         "production"}
assert set(data)==allowed
assert data["real_two_host_migration"]=="NOT_RUN"
assert data["production"]=="NO"
data["scope"]="PUBLIC_SAFE_EPHEMERAL_CANDIDATE_CHECK_NO_ARCHIVE"
data["actual_archive_delivered"]=False
target.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY
test -f "$SAFE_PROOF/candidate-proof.json"
test ! -f "$SAFE_PROOF/$CANDIDATE_FILE"
echo P07_D04_PUBLIC_ONLY_SANITIZED_PROOF_NO_PRIVATE_ARCHIVE=PASS
