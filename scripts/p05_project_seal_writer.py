#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "llhzx2018/vf-seo"
BASE_SHA = "e37d4f61f3c2e1de535c6c4518f793f18bfbc718"
BRANCH = "docs/p05-project-seal-20260904"
SEAL_AUTHORITY = "docs/authority/PROJECT_SEAL_V1.2.5.md"
SEALED_HANDOFF = "docs/handoff/SEALED_STATE.md"
TOKEN = os.environ.get("VF_RELEASE_WRITE_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("VF_RELEASE_WRITE_TOKEN missing")

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "p05-project-seal-writer",
}


def api(method, path, payload=None, allow_404=False):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API {method} {path} -> {exc.code}: {body[:1000]}") from exc


def ref_sha(branch):
    quoted = urllib.parse.quote(branch, safe="")
    obj = api("GET", f"/repos/{REPO}/git/ref/heads/{quoted}")
    return obj["object"]["sha"]


def get_content(path, branch):
    p = urllib.parse.quote(path, safe="/")
    r = urllib.parse.quote(branch, safe="")
    obj = api("GET", f"/repos/{REPO}/contents/{p}?ref={r}")
    return base64.b64decode(obj["content"]).decode("utf-8"), obj["sha"]


def put_content(path, text, message, sha=None):
    p = urllib.parse.quote(path, safe="/")
    payload = {
        "message": message,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    return api("PUT", f"/repos/{REPO}/contents/{p}", payload)


main_sha = ref_sha("main")
branch_sha = ref_sha(BRANCH)
assert main_sha == BASE_SHA, ("main drift", main_sha)
assert branch_sha == BASE_SHA, ("seal branch drift", branch_sha)

raw, vf_sha = get_content("VF_PROJECT.json", BRANCH)
v = json.loads(raw)
assert v["version"] == "1.2.5"
assert v["production_version"] == "1.2.5"
assert v["status"] == "V1.2.5_RELEASED / PRODUCTION_CLOSED"
assert v["next_action"] == "V1.2.5_PRODUCTION_CLOSED → L2_PRODUCT_OPTIMIZATION"

v["status"] = "PROJECT_SEALED / V1.2.5_RELEASED / PRODUCTION_CLOSED / MAINTENANCE_ONLY"
v["project_lifecycle"] = "SEALED_MAINTENANCE_ONLY"
v["seal_date"] = "2026-09-04"
v["seal_reason"] = "NO_ACTIVE_WEBSITE_OPERATIONS / NO_REAL_SEO_OPERATING_DATA"
v["seal_authority"] = SEAL_AUTHORITY
v["maintenance_policy"] = "SECURITY_DATA_LOSS_RUNTIME_BREAKAGE_ONLY_WITH_EXPLICIT_OWNER_AUTHORIZATION"
v["reopen_policy"] = "OWNER_EXPLICIT_REOPEN_AFTER_REAL_WEBSITE_OPERATIONS_AND_REAL_SEO_DATA"
v["runtime_handoff"] = SEALED_HANDOFF
v["next_action"] = "PROJECT_SEALED / NO_ACTIVE_PRODUCT_OPTIMIZATION / WAIT_FOR_REAL_WEBSITE_OPERATIONS_AND_REAL_SEO_DATA"
v["deployment_readiness"] = "V1.2.5_PRODUCTION_CLOSED / PROJECT_SEALED"
if "current_engineering_state" in v:
    v["current_engineering_state"] = "PROJECT_SEALED_AT_V1.2.5_PRODUCTION_CLOSED"
v.setdefault("authority", {})["project_seal"] = SEAL_AUTHORITY

vf_text = json.dumps(v, ensure_ascii=False, indent=2) + "\n"
put_content("VF_PROJECT.json", vf_text, "docs(P05): mark project sealed", vf_sha)

seal_doc = """# P05 · VF SEO · Project Seal Authority\n\nStatus: `PROJECT SEALED / MAINTENANCE ONLY`\n\nEffective date: `2026-09-04`\n\n## Frozen operating baseline\n\n- Current formal release: `v1.2.5`\n- Production state: `v1.2.5 · RELEASED / PRODUCTION CLOSED`\n- Immutable v1.2.5 Release source: `e37db145111366a29fc91c33348216a7af79ae8c`\n- Immutable Release tree: `9107865be22bfcd237d13186d735406c0501a7c2`\n- Production closure authority: `docs/authority/RELEASE_V1.2.5_PRODUCTION_CLOSURE.md`\n- Schema: `VF-SEO-SCHEMA@1 / 1`\n\n## Owner seal decision\n\nP05 is sealed at v1.2.5 because there are currently no actively operated websites supplying sustained real SEO operating data. Continuing ordinary Product Optimization without real Search Console / analytics / crawl / ranking evidence would be speculative rather than operations-driven.\n\nThis is a lifecycle seal, not a deletion and not a claim that the product failed. Production v1.2.5 remains the current deployed baseline. Existing Demo data may remain for demonstration and verification, but Demo data is not authority for real SEO operating decisions.\n\n## While sealed\n\nNo proactive L2 Product Optimization, feature expansion, redesign, release train or Production deployment should start automatically. Maintenance is limited to security issues, data-loss or data-integrity risk, runtime breakage, availability failure, or another explicit Owner-authorized maintenance need. Any new Release or Production mutation requires fresh explicit Owner authorization.\n\n## Reopen gate\n\nNormal product optimization may resume only after all of the following are true:\n\n1. At least one real website is actively operated.\n2. Real SEO data sources are connected and producing trustworthy observations.\n3. There is enough real observation history to distinguish baseline, change and opportunity without fabricating certainty.\n4. The Owner explicitly authorizes P05 to reopen.\n\nUntil then the correct next action is: `WAIT / MAINTAIN ONLY`.\n\n## Authority boundary\n\nThis seal does not rewrite the immutable v1.2.5 Release, Tag, FULL/UPDATE assets, schema, update channel or Production runtime. It only changes the project lifecycle Current Truth after the completed v1.2.5 Production closure.\n"""

handoff_doc = """# P05 · VF SEO · Sealed State\n\n```text\nProject Lifecycle: SEALED / MAINTENANCE ONLY\nCurrent Formal Release: v1.2.5 · RELEASED / PRODUCTION CLOSED\nProduction: v1.2.5 · MACHINE + OWNER VERIFIED\nSchema: VF-SEO-SCHEMA@1 / 1\nActive Product Optimization: OFF\nActive Release Authorization: NONE\nActive Production Authorization: NONE\nSeal Reason: No active website operations / no real SEO operating data yet\nNext Action: WAIT / MAINTAIN ONLY\nSeal Authority: docs/authority/PROJECT_SEAL_V1.2.5.md\n```\n\nP05 must not automatically resume L2 Product Optimization from historical handoff text. The project was explicitly sealed by the Owner after v1.2.5 Production closure.\n\nReopen only when at least one real website is actively operated, trustworthy real SEO observations exist, and the Owner explicitly authorizes reopening. Demo data is not sufficient by itself to reopen the project.\n\nFor immutable release and Production evidence, use `docs/authority/RELEASE_V1.2.5_PRODUCTION_CLOSURE.md`.\n"""

for path, text, message in [
    (SEAL_AUTHORITY, seal_doc, "docs(P05): add project seal authority"),
    (SEALED_HANDOFF, handoff_doc, "docs(P05): add sealed handoff"),
]:
    p = urllib.parse.quote(path, safe="/")
    r = urllib.parse.quote(BRANCH, safe="")
    existing = api("GET", f"/repos/{REPO}/contents/{p}?ref={r}", allow_404=True)
    assert existing is None, f"unexpected existing file: {path}"
    put_content(path, text, message)

final_head = ref_sha(BRANCH)
compare = api("GET", f"/repos/{REPO}/compare/{BASE_SHA}...{final_head}")
files = sorted(f["filename"] for f in compare.get("files", []))
expected = sorted(["VF_PROJECT.json", SEAL_AUTHORITY, SEALED_HANDOFF])
assert compare["status"] == "ahead", compare["status"]
assert compare["behind_by"] == 0, compare["behind_by"]
assert files == expected, (files, expected)

final_raw, _ = get_content("VF_PROJECT.json", BRANCH)
final = json.loads(final_raw)
assert final["status"].startswith("PROJECT_SEALED")
assert final["project_lifecycle"] == "SEALED_MAINTENANCE_ONLY"
assert final["production_version"] == "1.2.5"
assert final["runtime_handoff"] == SEALED_HANDOFF
assert final["authority"]["project_seal"] == SEAL_AUTHORITY

print(f"P05_PROJECT_SEAL_WRITE=PASS")
print(f"PRODUCT_HEAD={final_head}")
print("PRODUCT_SCOPE=3_FILES")
print("VERSION_CHANGE=0")
print("RELEASE_WRITE=0")
print("PRODUCTION_WRITE=0")
