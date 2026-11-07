#!/usr/bin/env python3
"""One-shot P01 Channel Owner/Guest parity proof against synthetic installed site.

143 fake channel records only; no Production endpoint, secrets, or real Owner data.
"""
from __future__ import annotations
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

PASSWORD="SyntheticOnly!Passw0rd"

def require(ok,reason):
    if not ok: raise AssertionError(reason)

def run(args,*,cwd=None,env=None,timeout=150):
    p=subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True,timeout=timeout)
    require(p.returncode==0,"command failed: "+" ".join(args[:3])+" "+p.stderr[-300:])
    return p

def get(opener,url):
    with opener.open(urllib.request.Request(url,headers={"Cache-Control":"no-cache"}),timeout=15) as response:
        require(response.status==200,"HTTP "+str(response.status))
        return response.read().decode("utf-8")

def start_php(site,port):
    p=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(site)],
                       cwd=site,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f"http://127.0.0.1:{port}"
    for _ in range(70):
        try:
            with urllib.request.urlopen(url+"/setup.php",timeout=2) as response:
                if response.status==200:return p,url
        except Exception:
            time.sleep(.15)
    p.terminate();p.wait(timeout=6)
    raise AssertionError("fresh local PHP server cannot start")

def stop_php(p):
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)

def owner_login(opener,url):
    request=urllib.request.Request(url+"/api.php?action=login",
         data=json.dumps({"password":PASSWORD}).encode(),
         headers={"Content-Type":"application/json","Accept":"application/json"},method="POST")
    with opener.open(request,timeout=16) as r:
        data=json.load(r)
        require(r.status==200 and data.get("ok") is True,"Owner authenticated login failed")

def assets_in_html(page):
    return [int(x) for x in re.findall(r'data-asset-row="([0-9]+)"',page)]

def validate_pages(opener,url,base,expected_count,expected_pages):
    found=[]
    for p in range(1,expected_pages+1):
        params=urllib.parse.urlencode({**base,"page":p})
        html=get(opener,url+"/channels.php?"+params)
        ids=assets_in_html(html)
        n=20 if p<expected_pages else expected_count-(expected_pages-1)*20
        require(len(ids)==n,"page "+str(p)+" count mismatch: "+str(len(ids))+" vs "+str(n))
        found.extend(ids)
    require(len(found)==len(set(found))==expected_count,"missing or duplicate channel identity across pages")
    return set(found)

def audit(site,port,fixture):
    php,url=start_php(site,port)
    try:
        owner=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        setup=get(owner,url+"/setup.php")
        csrf=re.search(r'name="setup_csrf"\s+value="([^"]+)"',setup)
        require(csrf is not None,"synthetic setup csrf unavailable")
        data=urllib.parse.urlencode({"setup_csrf":csrf.group(1),
            "site_title":"P01 Channel Parity Synthetic Test",
            "admin_password":PASSWORD,"admin_password_confirm":PASSWORD}).encode()
        with owner.open(urllib.request.Request(url+"/setup.php",data=data,method="POST"),timeout=24) as r:
            require(r.status in (200,302),"synthetic setup POST failed")
        run(["php",str(site/"cli/verify.php")],cwd=site,timeout=40)
    finally:
        stop_php(php)

    env=os.environ.copy()
    env["P01_SYNTHETIC_CHANNEL_PARITY"]="YES"
    env["P01_CHANNEL_SITE_ROOT"]=str(site)
    fixture_result=run(["php",str(fixture)],cwd=site,env=env,timeout=180)
    for token in ("P01_CHANNELS_143_RAW_130_ORGANIZED_104_PUBLIC_13_INBOX=PASS",
                  "P01_CHANNELS_REDISCOVERY_ALL_130_NO_24_ROW_CLAMP=PASS",
                  "P01_CHANNELS_OWNER_GUEST_20_PER_PAGE_NO_MISSING_DUPLICATES=PASS"):
        require(token in fixture_result.stdout,"fixture missing proof "+token)
        print(token,flush=True)

    php,url=start_php(site,port)
    try:
        owner=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        guest=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        owner_login(owner,url)

        def inventory(organized,offset,limit):
            params=urllib.parse.urlencode({
                "surface":"channels","organized_only":str(organized),
                "offset":offset,"limit":limit})
            return json.loads(get(owner,url+"/api.php?action=resource_inventory&"+params))
        raw=inventory(0,0,100)
        require(raw["ok"] is True and raw["total"]==143,"real owner API raw total not 143")
        organized=[inventory(1,o,60) for o in (0,60,120)]
        require(all(v.get("ok") is True and v.get("total")==130 for v in organized),
                "real owner API organized count diverges")
        ids=[int(row["id"]) for page in organized for row in page["rows"]]
        require(len(ids)==130 and len(set(ids))==130,"manual Owner inventory missed/paged duplicates")
        require(all(int(row["is_pending"])==0 for page in organized for row in page["rows"]),
                "Pending Inbox leaked into daily Channel updater")
        print("P01_CHANNEL_OWNER_API_REAL_143_RAW_130_ORGANIZED_60_60_10_PAGES=PASS",flush=True)

        directory=validate_pages(owner,url,{"view":"directory"},130,7)
        require(directory==set(ids),"native Owner directory ID set != management API")
        owner_home=get(owner,url+"/channels.php?view=directory")
        require("<strong>130</strong> 个频道" in owner_home,"Owner directory has no full count")
        print("P01_CHANNEL_OWNER_REAL_HTML_130_SEVEN_PAGES_API_ID_PARITY=PASS",flush=True)

        discovered=validate_pages(owner,url,{"view":"directory","discover":"1"},130,7)
        require(discovered==directory,"rediscovery lost sorted identities")
        print("P01_CHANNEL_REDISCOVERY_REAL_HTTP_ALL_130_NO_24_LIMIT=PASS",flush=True)

        public_owner=validate_pages(owner,url,{"view":"directory","scope":"public"},104,6)
        private_owner=validate_pages(owner,url,{"view":"directory","scope":"private"},26,2)
        require(public_owner.isdisjoint(private_owner) and public_owner|private_owner==directory,
                "Owner public/private split did not reconstruct all 130 records")
        print("P01_CHANNEL_OWNER_SCOPE_104_PUBLIC_26_PRIVATE_UNION_130=PASS",flush=True)

        guest_html=get(guest,url+"/channels.php?view=directory")
        require("<strong>104</strong> 个频道" in guest_html,
                "Guest public-only count drift")
        guest_ids=validate_pages(guest,url,{"view":"directory"},104,6)
        require(guest_ids==public_owner,"Guest leaked private or lost public channels")
        try:
            get(guest,url+"/api.php?action=resource_inventory&surface=channels")
            raise AssertionError("Guest unexpectedly accessed Owner-only inventory")
        except urllib.error.HTTPError as error:
            require(error.code in (401,403,404),"unexpected denial status "+str(error.code))
        print("P01_CHANNEL_GUEST_HTTP_104_NO_PRIVATE_PENDING_AND_OWNER_API_DENIED=PASS",flush=True)

        plain=get(owner,url+"/channels.php")
        require("频道目录" in plain and "130" in plain,"cached-video landing does not disclose full source directory")
        require(not assets_in_html(plain),"default cached-video reader must not masquerade as directory")
        print("P01_CHANNEL_VIDEO_READER_DISTINCT_FROM_COMPLETE_SOURCE_DIRECTORY=PASS",flush=True)
    finally:
        stop_php(php)

    print("P01_CHANNEL_LIVE_OWNER_PRODUCTION_DATA=NOT_ACCESSED",flush=True)
    print("P01_CHANNEL_FIX_SYNTHETIC_FULL_AUDIT=PASS",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--work",required=True)
    a.add_argument("--official-full",required=True)
    a.add_argument("--candidate",required=True)
    z=a.parse_args()
    w=Path(z.work).resolve()
    site=w/"synthetic-channel-installed"
    site.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(z.official_full) as archive:
        names=archive.namelist()
        require(not any(n.startswith("/") or ".." in Path(n).parts for n in names),"unsafe package")
        archive.extractall(site)
    src=Path(z.candidate).resolve()
    overlay=("app/SurfaceRepository.php","app/ChannelLibraryPage.php",
             "assets/global-remote-channels.js")
    for rel in overlay:
        target=site/rel
        require(target.is_file() and (src/"src"/rel).is_file(),"missing overlay "+rel)
        target.write_bytes((src/"src"/rel).read_bytes())
    require((site/"VERSION.txt").read_text().strip()=="2.47.501",
            "synthetic baseline version wrong")
    audit(site,19633,src/"tests/integration/p01_channels_130_parity_fixture.php")

if __name__=="__main__":main()
