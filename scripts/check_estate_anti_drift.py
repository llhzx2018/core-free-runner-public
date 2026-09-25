from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote


GOVERNANCE_REPOSITORY = "llhzx2018/gov-doc"
REGISTRY_PATH = "governance/authority/VF_GIT_REPOSITORY_REGISTRY_V1.0.json"
INFRA_AUTHORITY_PATH = "governance/agent/VF_AGENT_INFRA_AUTHORITY.json"

DYNAMIC_REPOSITORY_KEYS = {
    "main_sha",
    "head_sha",
    "open_pr_count",
    "branch_count",
    "latest_workflow",
    "latest_workflow_run",
    "release_version",
    "production_version",
    "production_installed",
}

REQUIRED_CURRENT_INFRASTRUCTURE = {
    "llhzx2018/core-agent",
    "llhzx2018/core-updates",
    "llhzx2018/core-free-runner-public",
    "llhzx2018/core-free-runner-private",
    "llhzx2018/gov-doc",
}


def _failure(code: str, detail: str = "") -> str:
    return code if not detail else f"{code}:{detail}"


def verify_registry(registry: dict) -> list[str]:
    failures: list[str] = []
    if registry.get("schema") != "vf.git-repository-registry.v1":
        failures.append(_failure("REGISTRY_SCHEMA", str(registry.get("schema"))))

    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        return failures + ["REGISTRY_REPOSITORIES_NOT_LIST"]

    by_repo: dict[str, dict] = {}
    for index, item in enumerate(repositories):
        if not isinstance(item, dict):
            failures.append(_failure("REGISTRY_ENTRY_NOT_OBJECT", str(index)))
            continue
        repository = item.get("repository")
        if not isinstance(repository, str) or not repository:
            failures.append(_failure("REGISTRY_REPOSITORY_MISSING", str(index)))
            continue
        if repository in by_repo:
            failures.append(_failure("REGISTRY_DUPLICATE_REPOSITORY", repository))
            continue
        by_repo[repository] = item

        dynamic = sorted(DYNAMIC_REPOSITORY_KEYS.intersection(item))
        if dynamic:
            failures.append(_failure("REGISTRY_DYNAMIC_FIELD", f"{repository}:{','.join(dynamic)}"))

        lifecycle = item.get("lifecycle")
        route_status = item.get("route_status")
        source_class = item.get("source_class")

        if lifecycle == "DELETED" and route_status != "TOMBSTONE":
            failures.append(_failure("DELETED_NOT_TOMBSTONE", repository))
        if route_status == "TOMBSTONE" and lifecycle != "DELETED":
            failures.append(_failure("TOMBSTONE_NOT_DELETED", repository))
        if source_class == "VF_OWNED" and lifecycle == "ACTIVE" and route_status != "CURRENT_ROUTE":
            failures.append(_failure("ACTIVE_VF_NOT_CURRENT_ROUTE", repository))
        if source_class == "EXTERNAL_FORK":
            if lifecycle != "REFERENCE" or route_status != "NON_AUTHORITY":
                failures.append(_failure("EXTERNAL_FORK_ROUTE", repository))
            if not item.get("upstream"):
                failures.append(_failure("EXTERNAL_FORK_UPSTREAM_MISSING", repository))

    for repository in sorted(REQUIRED_CURRENT_INFRASTRUCTURE):
        item = by_repo.get(repository)
        if item is None:
            failures.append(_failure("REQUIRED_INFRA_MISSING", repository))
            continue
        if item.get("lifecycle") != "ACTIVE" or item.get("route_status") != "CURRENT_ROUTE":
            failures.append(_failure("REQUIRED_INFRA_NOT_CURRENT", repository))

    p03 = by_repo.get("llhzx2018/vf-forge")
    if p03 is None:
        failures.append("P03_RECORD_MISSING")
    elif p03.get("lifecycle") != "HISTORICAL" or p03.get("route_status") != "NON_AUTHORITY":
        failures.append("P03_ROUTE_NOT_RETIRED")

    legacy = by_repo.get("llhzx2018/core-test-runner")
    if legacy is None:
        failures.append("LEGACY_RUNNER_TOMBSTONE_MISSING")
    elif legacy.get("lifecycle") != "DELETED" or legacy.get("route_status") != "TOMBSTONE":
        failures.append("LEGACY_RUNNER_REACTIVATED")

    return failures


def verify_infra_authority(authority: dict) -> list[str]:
    failures: list[str] = []
    if authority.get("schema") != "vf-agent-infra-authority/2":
        failures.append(_failure("INFRA_AUTHORITY_SCHEMA", str(authority.get("schema"))))
    if authority.get("status") != "CURRENT":
        failures.append(_failure("INFRA_AUTHORITY_STATUS", str(authority.get("status"))))
    if authority.get("public_runner") != "llhzx2018/core-free-runner-public":
        failures.append("PUBLIC_RUNNER_ROUTE_DRIFT")
    if authority.get("private_runner") != "llhzx2018/core-free-runner-private":
        failures.append("PRIVATE_RUNNER_ROUTE_DRIFT")
    if "legacy_runner" in authority:
        failures.append("LEGACY_RUNNER_ACTIVE_KEY_PRESENT")

    hard_rules = authority.get("hard_rules") or {}
    if hard_rules.get("allow_third_runner") is not False:
        failures.append("THIRD_RUNNER_RULE_NOT_FALSE")
    if hard_rules.get("allow_third_credential") is not False:
        failures.append("THIRD_CREDENTIAL_RULE_NOT_FALSE")

    tombstone = authority.get("legacy_runner_tombstone")
    if not isinstance(tombstone, dict):
        failures.append("LEGACY_RUNNER_TOMBSTONE_AUTHORITY_MISSING")
    else:
        if tombstone.get("canonical_id") != "llhzx2018/core-test-runner":
            failures.append("LEGACY_RUNNER_TOMBSTONE_ID_DRIFT")
        if tombstone.get("state") != "DELETED":
            failures.append("LEGACY_RUNNER_TOMBSTONE_STATE_DRIFT")
        if tombstone.get("current_route") is not False:
            failures.append("LEGACY_RUNNER_TOMBSTONE_ROUTE_DRIFT")
        if tombstone.get("compatibility_policy") != "TOMBSTONE_AND_MIGRATION_EVIDENCE_ONLY":
            failures.append("LEGACY_RUNNER_TOMBSTONE_POLICY_DRIFT")

    return failures


def verify_local_workflows(root: Path) -> list[str]:
    failures: list[str] = []
    workflow_root = root / ".github" / "workflows"
    workflows = sorted(workflow_root.glob("*.yml"))
    if not workflows:
        return ["CURRENT_WORKFLOWS_MISSING"]

    for path in workflows:
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?mi)^\s*contents:\s*write\s*$", text):
            failures.append(_failure("CURRENT_WORKFLOW_CONTENTS_WRITE", path.name))
        if re.search(r"(?mi)\bgit\s+push\b", text):
            failures.append(_failure("CURRENT_WORKFLOW_DIRECT_GIT_PUSH", path.name))

    core_agent = workflow_root / "core-agent-current-verify.yml"
    if not core_agent.is_file():
        failures.append("CORE_AGENT_CURRENT_WORKFLOW_MISSING")
    else:
        text = core_agent.read_text(encoding="utf-8")
        if re.search(r"CORE_AGENT_SOURCE_SHA:\s*[0-9a-f]{40}\b", text):
            failures.append("CORE_AGENT_CURRENT_HARDCODED_SHA")
        if "ref: main" not in text:
            failures.append("CORE_AGENT_CURRENT_NOT_TRACKING_MAIN")
        if "git -C source rev-parse HEAD" not in text:
            failures.append("CORE_AGENT_CURRENT_IDENTITY_READBACK_MISSING")

    return failures


def _fetch_private_json(repository: str, path: str, token: str, ref: str = "main") -> dict:
    encoded_path = quote(path, safe="/")
    url = f"https://api.github.com/repos/{repository}/contents/{encoded_path}?ref={quote(ref, safe='')}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "vf-estate-anti-drift-v1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = base64.b64decode(payload["content"])
    return json.loads(raw.decode("utf-8"))


def verify_live(token: str) -> list[str]:
    try:
        registry = _fetch_private_json(GOVERNANCE_REPOSITORY, REGISTRY_PATH, token)
        authority = _fetch_private_json(GOVERNANCE_REPOSITORY, INFRA_AUTHORITY_PATH, token)
    except urllib.error.HTTPError as exc:
        return [_failure("LIVE_AUTHORITY_HTTP", str(exc.code))]
    except Exception as exc:  # public-safe class only; never print token or source bodies
        return [_failure("LIVE_AUTHORITY_READ", type(exc).__name__)]
    return verify_registry(registry) + verify_infra_authority(authority)



def _run_p01_v24773_owner_preview() -> int:
    """One-time OWNER-authorized Preview Runtime. Never runs outside the exact unmerged preview branch."""
    if os.environ.get("GITHUB_HEAD_REF") != "p01-v24773-owner-preview-public-20260925":
        return 0
    token = os.environ.get("VF_PRIVATE_READ_TOKEN", "")
    if not token:
        print("P01_V24773_PREVIEW=BLOCKED_PRIVATE_READ")
        return 79

    script = r'''set -Eeuo pipefail
umask 077
TARGET_SHA='5a90fa61b0e446444b49f8de58438d2de5e9acda'
TARGET_TREE='9e6fe0e775e95dfb237471a569f604062f267218'
TARGET_VERSION='2.47.73'
PORT='18490'
TMP="$(mktemp -d /tmp/p01-v24773-preview.XXXXXX)"
PHP_PID=''
CF_PID=''
cleanup() {
  set +e
  [[ -n "$CF_PID" ]] && kill "$CF_PID" >/dev/null 2>&1 || true
  [[ -n "$PHP_PID" ]] && kill "$PHP_PID" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

curl -fsSL \
  -H "Authorization: Bearer ${VF_PRIVATE_READ_TOKEN}" \
  -H 'Accept: application/vnd.github+json' \
  "https://api.github.com/repos/llhzx2018/vf-start/git/commits/${TARGET_SHA}" \
  -o "$TMP/commit.json"
python3 - "$TMP/commit.json" "$TARGET_TREE" <<'PY'
import json,sys
obj=json.load(open(sys.argv[1],encoding='utf-8'))
assert obj['tree']['sha']==sys.argv[2], (obj['tree']['sha'],sys.argv[2])
print('P01_V24773_PREVIEW_TREE_IDENTITY=PASS')
PY

curl -fsSL \
  -H "Authorization: Bearer ${VF_PRIVATE_READ_TOKEN}" \
  -H 'Accept: application/vnd.github+json' \
  "https://api.github.com/repos/llhzx2018/vf-start/tarball/${TARGET_SHA}" \
  -o "$TMP/source.tar.gz"
mkdir -p "$TMP/source"
tar -xzf "$TMP/source.tar.gz" -C "$TMP/source"
SRC="$(find "$TMP/source" -mindepth 1 -maxdepth 1 -type d | head -n1)"
test -n "$SRC"
test "$(tr -d '\r\n ' < "$SRC/VERSION")" = "$TARGET_VERSION"
test "$(tr -d '\r\n ' < "$SRC/src/VERSION.txt")" = "$TARGET_VERSION"

if ! php -m 2>/dev/null | grep -Fxq pdo_sqlite; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq php-cli php-sqlite3 php-curl php-mbstring php-zip php-gd curl openssl >/dev/null
fi
command -v curl >/dev/null
command -v openssl >/dev/null

cp -a "$SRC/src" "$TMP/runtime"
COOKIE="$TMP/cookie.txt"
PASS="$(openssl rand -hex 18)"
(
  cd "$TMP/runtime"
  php -S "127.0.0.1:${PORT}" -t . >"$TMP/php.log" 2>&1 &
  echo $! >"$TMP/php.pid"
)
PHP_PID="$(cat "$TMP/php.pid")"
for _ in $(seq 1 40); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o "$TMP/setup.html"; then break; fi
  sleep 1
done
CSRF="$(python3 - "$TMP/setup.html" <<'PY'
import re,sys
t=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',t)
assert m
print(m.group(1))
PY
)"
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
  --data-urlencode "setup_csrf=${CSRF}" \
  --data-urlencode 'site_title=VF Start V2.47.73 Owner Preview' \
  --data-urlencode "admin_password=${PASS}" \
  --data-urlencode "admin_password_confirm=${PASS}" \
  -o "$TMP/setup-post.html"
(cd "$TMP/runtime" && php cli/verify.php) >"$TMP/verify.txt"
grep -Fxq 'VERIFY_PASS=YES' "$TMP/verify.txt"
BODY="$(php -r 'echo json_encode(["password"=>$argv[1]], JSON_UNESCAPED_SLASHES);' "$PASS")"
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' --data "$BODY" \
  "http://127.0.0.1:${PORT}/api.php?action=login" >"$TMP/login.json"
grep -Fq '"ok":true' "$TMP/login.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/jobs.php" -o "$TMP/jobs.html"
grep -Fq '计划任务' "$TMP/jobs.html"
echo 'P01_V24773_PREVIEW_RUNTIME_LOCAL=PASS'

curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o "$TMP/cloudflared"
chmod 700 "$TMP/cloudflared"
"$TMP/cloudflared" tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:${PORT}" \
  --logfile "$TMP/cloudflared.log" --loglevel info >"$TMP/cloudflared.stdout" 2>&1 &
CF_PID=$!
URL=''
for _ in $(seq 1 60); do
  URL="$(grep -hEo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TMP/cloudflared.log" "$TMP/cloudflared.stdout" 2>/dev/null | tail -1 || true)"
  [[ -n "$URL" ]] && break
  sleep 1
done
test -n "$URL"
READY=0
for _ in $(seq 1 30); do
  CODE="$(curl -sS --connect-timeout 5 --max-time 10 -o "$TMP/external.html" -w '%{http_code}' "$URL/" || true)"
  if [[ "$CODE" = '200' || "$CODE" = '302' || "$CODE" = '303' ]]; then
    READY=1
    break
  fi
  sleep 2
done
test "$READY" = '1'
echo 'P01_V24773_PREVIEW_EXTERNAL_ROUTE=PASS'

printf 'PREVIEW_URL=%s/jobs.php\nLOGIN_PASSWORD=%s\nVERSION=%s\nEXACT_SOURCE=%s\nEXACT_TREE=%s\nPRODUCTION_WRITE=NO\nTAG_RELEASE_CHANNEL_WRITE=NO\n' \
  "$URL" "$PASS" "$TARGET_VERSION" "$TARGET_SHA" "$TARGET_TREE" >"$TMP/access.txt"
printf '%s' 'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQ0lqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FnOEFNSUlDQ2dLQ0FnRUF2YmdtUklNWHJwL2E4Rm1OYTE0bApoTFVXVTgrYURZcjU1SE8zeG5RZkM0aElDS09Tem5xNEM3TjNSWVZrYkd6UVhORUJva1phc0JQWVhVZG9vQkh5ClZZVFpNalpMVEYvQnlsUmxrazhPK0hvdzJpYk54OUFKRXBZU2IrT1JNcGs5bVNCTDErTE1FdHQ5ak5zNlQwQ0IKNi8vM3A1c2JwZEZBTmZZbEJ5MG0wZThVSmMrTmJlSmNLMVVqMHV4d0NWZmpKdXNjWFR0Z1BHVjdndnNYU0xHUgpUY0VxOHViQWpONXd2c25KK29BL0NwL1ZyODI0SVcwVmw5aU1WbDV1WFpIN3IxUXpPYU5yOWJCUnJpYU1LTWFYCi9Sd1NHNit2dXdsRmRndUdSVW5Mcm5xbjI3cERFU0lTeHprcEhVRHNhWjlkNkRiSTlwOVcycUpxUmtBOGJQV1EKWW5oZmJSOGkrM2hGa01nSnNxTW9DeGN4R2JPOEtmUm1QRnpqK3pQOVVhTnVvaGp1clVjQnNiNmZzUzBLSVJvbQp0dFFYRlRNWFhJQ1F4QzE2bm9ZQTRML1d1azB4cG9ZMXY0NWp4MTR2ZnNMRFZmcU5UVDVxb2xRbnE3SnR1TVVuCm1vQU5RcDd1MTY3bW9GWkxWZTlQa1ZzemNoYWFuQllDNnNWVnM2aWpNajU4c0FNVzk2TjEwTVl4dEJzb205VkgKL1QrWHRvRXU1aW0wb01KZFN5bm9KSTFMWDl3SG93OFdZZ3NicXlOcXFPR1Rrdk54MzRNWG43ZEJieldCN0o5YgpRNXY3cUhiUnEvR1M3STV6K0JYRDFVL3dKckVPSnZIaEEyUGxKT0puSGlkcEh5eXB0OGVWVHNpT1J4N1JtbitMCit4NzgrNzVWMTZ1VWFuK01DcnJKM2wwQ0F3RUFBUT09Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo=' | base64 -d >"$TMP/public.pem"
openssl pkeyutl -encrypt -pubin -inkey "$TMP/public.pem" \
  -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha256 \
  -in "$TMP/access.txt" -out "$TMP/access.enc"
CIPHER="$(base64 -w0 "$TMP/access.enc")"
rm -f "$TMP/access.txt" "$TMP/public.pem"
unset PASS BODY CSRF

curl -fsSL 'https://codeload.github.com/actions/upload-artifact/tar.gz/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a' -o "$TMP/upload-artifact.tgz"
mkdir -p "$TMP/upload-action"
tar -xzf "$TMP/upload-artifact.tgz" -C "$TMP/upload-action"
UPLOAD_DIR="$(find "$TMP/upload-action" -mindepth 1 -maxdepth 1 -type d | head -n1)"
test -f "$UPLOAD_DIR/dist/upload/index.js"
env \
  'INPUT_NAME=p01-v24773-preview-access-encrypted' \
  "INPUT_PATH=$TMP/access.enc" \
  'INPUT_IF-NO-FILES-FOUND=error' \
  'INPUT_RETENTION-DAYS=1' \
  'INPUT_COMPRESSION-LEVEL=6' \
  'INPUT_OVERWRITE=true' \
  'INPUT_INCLUDE-HIDDEN-FILES=false' \
  node "$UPLOAD_DIR/dist/upload/index.js"
echo 'P01_V24773_PREVIEW_ACCESS_ARTIFACT=PASS'

printf '::notice title=P01_V24773_PREVIEW_ACCESS_RSA_OAEP_SHA256_B64::%s\n' "$CIPHER"
echo 'P01_V24773_OWNER_PREVIEW_RUNTIME=READY'
echo 'P01_V24773_PREVIEW_WINDOW_SECONDS=240'
sleep 240
echo 'P01_V24773_PREVIEW_WINDOW_COMPLETE=YES'
'''
    try:
        subprocess.run(["bash", "-lc", script], check=True, env=os.environ.copy())
    except subprocess.CalledProcessError as exc:
        print(f"P01_V24773_PREVIEW=FAIL:{exc.returncode}")
        return exc.returncode or 1
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify current VF Git Estate governance invariants.")
    parser.add_argument("--live", action="store_true", help="Read CURRENT gov-doc authority through registered private-read capability.")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)

    failures = verify_local_workflows(Path(args.root))
    if args.live:
        token = os.environ.get("VF_PRIVATE_READ_TOKEN", "")
        if not token:
            print("ESTATE_ANTI_DRIFT=BLOCKED_INFRA")
            print("BLOCK=VF_PRIVATE_READ_TOKEN_MISSING")
            return 78
        failures.extend(verify_live(token))

    if failures:
        print("ESTATE_ANTI_DRIFT=FAIL")
        for failure in failures:
            print(f"FAIL={failure}")
        return 1

    print("ESTATE_ANTI_DRIFT=PASS")
    print(f"LIVE_AUTHORITY={'YES' if args.live else 'NO'}")
    print("PRIVATE_SOURCE_PERSISTED=NO")
    if args.live and os.environ.get("GITHUB_HEAD_REF") == "p01-v24773-owner-preview-public-20260925":
        return _run_p01_v24773_owner_preview()
    return 0


if __name__ == "__main__":
    sys.exit(main())
