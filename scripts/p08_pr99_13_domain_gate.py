#!/usr/bin/env python3
"""P08 one-case formal release 13-domain + immutable old UI proof gate.

Does not publish, operate Owner Production, print credentials, or create data.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys
from pathlib import Path

GOV="e57edc475b44df7d682c857703dabc3d75fc8193"
MAIN="349f4c0d46a8350c18cb36b6c8b0c60d2c096c6b"
OLD_V016="ed96b18627cd0a63b1da20a1fd8c9b6c1808f159"
BLOB="c0e1bd8e26337b8463b57f99f12b8cd44903d0f6"
def need(c,msg):
    if not c:raise ValueError("P08_PR99_13DOMAIN_STOP_"+msg)
def git(root):
    return subprocess.run(["git","-C",root,"rev-parse","HEAD"],check=True,text=True,capture_output=True).stdout.strip()
def api(path):
    proc=subprocess.run(["gh","api",path],check=True,text=True,capture_output=True,timeout=65)
    return json.loads(proc.stdout)
def check_run(runid,n,sha=None):
    base=f"repos/llhzx2018/core-free-runner-public/actions/runs/{runid}"
    run=api(base);jobs=api(base+"/jobs?per_page=100").get("jobs",[])
    need(run["conclusion"]=="success" and (sha is None or run["head_sha"]==sha),"RUN_"+str(runid))
    need(len(jobs)==n and all(j["conclusion"]=="success" and len(j.get("steps",[]))>=10 for j in jobs),"JOBS_"+str(runid))
    return True
def main():
    need(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("CI")=="true","RUNNER")
    need(git("gov")==GOV and git("target")==MAIN,"EXACT_MERGED_MAIN")
    current=Path("gov/CURRENT.md").read_text()
    skill=Path("gov/skills/skill-release/V3.26/SKILL.md").read_text()
    accept=Path("target/docs/authority/ACCEPTANCE_MATRIX.md").read_text()
    need("| skill-release | V3.26 |" in current and "Mode AA" in skill and "## RP-07AA" in accept,"DUAL_AUTH")
    case=Path("gov/governance/release/cases/P08_PR99_OFFICIAL_V015_MYSQL_EMPTY_SITE_ONEFILE_MAINTENANCE_MODE_AA_20261122.md")
    need(case.is_file() and "POST_OWNER_MANUAL_PRODUCTION_REQUIRED_NOT_PASS" in case.read_text(),"CASE_CONTRACT")
    b=Path("target/src/Upgrade/LegacyMediaUpgradeBridgeCli.php").read_bytes()
    blob=hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
    need(blob==BLOB,"EXACT_SCRIPT_BLOB")
    changed=api(f"repos/llhzx2018/vf-adops/compare/{OLD_V016}...{MAIN}")
    paths={x["filename"] for x in changed["files"]}
    need(paths=={"AGENTS.md","docs/authority/CURRENT.md","docs/authority/ACCEPTANCE_MATRIX.md",
                 "src/Upgrade/LegacyMediaUpgradeBridgeCli.php"},"UI_OR_CODE_SCOPE_CHANGED")
    print("P08_PR99_FINAL_CHANGED_WEB_UI_BYTES=ZERO")
    # Prior genuine HTTPS two-source Chromium proof can be reused only because
    # no public/server UI file changed and both original issued ZIPs are immutable.
    check_run(44916014874,2,"ec3124c09b1b14de43a794cef6d384d9c52ca10f")
    check_run(44978114989,9)
    check_run(44977937833,1)
    print("P08_PR99_ORIGINAL_015_AND_016_REAL_HTTPS_CHROMIUM_390_768_1440_REUSED_SAME_BYTES=PASS")
    # GitHub live online channel must remain deliberately ineligible for
    # unsafe unbridged ordinary issued-v015 PHP, regardless of the new tag.
    channel=api("repos/llhzx2018/core-updates/contents/projects/P08-ADOPS.json?ref=main")
    import base64
    m=json.loads(base64.b64decode(channel["content"]))
    need(m.get("target_version")=="0.1.16" and m.get("from_versions")==[]
        and m.get("production_auto_apply") is False
        and channel["sha"]=="879513c26585cbb38670d155d09f4636005fcdc2",
        "UNSAFE_NORMAL_CHANNEL")
    published=api("repos/llhzx2018/vf-adops/releases/tags/v0.1.16")
    need(published["target_commitish"]==OLD_V016 and published["id"]==453771143,"IMMUTABLE_V016_RELEASE")
    dig={a["name"]:a.get("digest") for a in published["assets"]}
    need(dig.get("VF_AdOps_V0.1.16_FULL.zip")==
         "sha256:7f6a3050db060448df391f0dc5a8a3a2de45c9f28a704cb76606694b82bd084f"
         and dig.get("VF_AdOps_V0.1.16_UPDATE.zip")==
         "sha256:6cd533631c3651117f09ffce3829a565d16d945f7f1e4938c27d678c75e3c399",
         "HISTORIC_V016_ASSETS")
    print("P08_PR99_GENUINE_OFFICIAL_ASSET_AND_OLD_UI_CHANNEL_SAFETY=PASS")
    router=json.loads(Path("gov/governance/public-authority/VF_PUBLIC_AUTHORITY_APPLICABILITY_ROUTER_V1.0.json").read_text())
    applicability=Path("target/docs/authority/PUBLIC_AUTHORITY_APPLICABILITY.md").read_text()
    classifications={
        "INSTALL":"REQUIRED",
        "SECURITY":"REQUIRED",
        "TESTING":"REQUIRED",
        "UPGRADE":"REQUIRED",
        "DATA_SCHEMA":"REQUIRED",
        "API_PROVIDER":"REQUIRED",
        "SEO":"N_A",
        "CRON_JOB":"N_A",
        "NOTIFICATION":"N_A",
        "OBSERVABILITY":"REQUIRED",
        "PERFORMANCE":"CONDITIONAL",
        "GIT":"REQUIRED",
        "UA_UI":"CONDITIONAL"
    }
    need(len(classifications)==13 and set(classifications)==set(router["domains"]),"ALL_DOMAINS")
    for key,state in classifications.items():
        authority=Path("gov")/router["domains"][key]["authority"]
        need(authority.is_file() and len(authority.read_bytes())>400,"AUTHORITY_"+key)
        need("| "+key+" |" in applicability,"PROJECT_MAPPING_"+key)
        need(state in ("REQUIRED","CONDITIONAL","N_A"),"UNKNOWN_"+key)
        print("P08_PR99_DOMAIN_"+key+"="+state)
    print("P08_PR99_PUBLIC_AUTHORITY_ALL_13_CLASSIFIED_SOURCE_BOUND=PASS")
    print("P08_PR99_OWNER_PREVIEW=POST_RELEASE_REQUIRED_NOT_PASS")
    print("P08_PR99_OWNER_REAL_USE=POST_OWNER_MANUAL_PRODUCTION_REQUIRED_NOT_PASS")
    print("P08_PR99_FORMAL_PREISSUE_POLICY_GATES=PASS")
if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,FileNotFoundError,subprocess.CalledProcessError) as e:
        print("P08_PR99_13DOMAIN_GATE=BLOCKED:"+type(e).__name__+":"+str(e)[:150],file=sys.stderr)
        sys.exit(1)
