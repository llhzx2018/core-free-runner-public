#!/usr/bin/env python3
"""One-case Mode AD, machine prepublication proof only. No release write or channel write.
Uses existing P08 builder and native fresh-site tests; never runs an installed-old update.
All product bytes and detailed logs remain in this disposable hosted runner.
"""
from __future__ import annotations
import hashlib, http.client, importlib.util, io, json, os, re, shutil, socket, ssl
import subprocess, sys, time, urllib.parse, zipfile
from pathlib import Path

SOURCE="b95ccd8062191193bc8971e50fab96c30045e6be"
TREE="cdb50315102fc5693665c52bbdd9aa80a89db21b"
BASE="797821db7679b28d459d5c39a34a8b5f990146c8"
GOV="f7e967fc6fa590942b7cecfb1407ec25f1eaf320"
OLD="4df14f88af6733039c561bde86a98f4b05c05a5c"
OLDTREE="7ebc94da7796824c1b1ba22c835a913c7a8dfbb8"
OLD_ZIP="8376db3fffa9c2874ab4a8bc0e8b359e1cc250669b6189a235d00ad5c6c1256d"
OLD_FULL="8dc3503e5449a7bf5a7fa5da454bc1196fd6515f2d21f05eeb5e736a629cb6d0"
OLD_UI="4ec0e3d9df1b3f99222f4b01cbd1f1f8f410413c7822e4bb936d7efc568b5ab3"
ENV=dict(os.environ)
TMP=Path(ENV["RUNNER_TEMP"]).resolve()
ROOT=Path(ENV["GITHUB_WORKSPACE"]).resolve()
P=ROOT/"p08"; G=ROOT/"gov"; D=TMP/"p08-v018-formal-proof"
PASS=[]
def need(ok,code):
    if not ok: raise RuntimeError(code)
def digest(data): return hashlib.sha256(data).hexdigest()
def filehash(p): return digest(p.read_bytes())
def note(code):
    PASS.append(code)
    print(code+"=PASS",flush=True)
def run(code,args,cwd=P,env=None,timeout=180,markers=()):
    cp=subprocess.run(args,cwd=cwd,env=env or ENV,capture_output=True,timeout=timeout)
    (D/(code+".log")).write_bytes(cp.stdout+b"\n"+cp.stderr)
    if cp.returncode or any(m.encode() not in cp.stdout.splitlines() for m in markers):
        print(code+"_EXIT="+str(cp.returncode),flush=True)
        # Only fixed, non-sensitive diagnostic code tokens from the owning scripts.
        for row in re.findall(rb"\b(?:R43_[A-Z0-9_]{5,100}|P08_[A-Z0-9_]{5,100}|RECOVERY_[A-Z0-9_]{5,100}|FULL_[A-Z0-9_]{5,100})\b",cp.stderr)[:6]:
            print("P08_SAFE_REASON="+row.decode(),flush=True)
        raise RuntimeError(code+"_NOT_PROVEN")
    note(code)
    return cp.stdout.decode(errors="replace").strip()
def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True,stderr=subprocess.DEVNULL,timeout=30).strip()
def check_archive(path,source):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        need(z.testzip() is None and len(names)==len(set(names)),"ZIP_INTEGRITY")
        m=json.loads(z.read("FULL_MANIFEST.json"))
        need(m["source_sha"]==source and m["target_version"]=="0.1.18" and m["type"]=="CLEAN_FULL_ONLY" and m["update_type"]=="NOT_ATOMIC" and m["data_included"] is False and m["owner_setup_completed"] is False,"ZIP_IDENTITY")
        index={x["path"]:x for x in m["files"]}
        need(len(index)==len(m["files"]) and set(names)==set(index)|{"FULL_MANIFEST.json"} and len(index)>6000,"ZIP_INDEX")
        for n,x in index.items():
            need(not n.startswith("/") and ".." not in n.split("/") and "\\" not in n and not n.startswith("storage/") and n!=".env","ZIP_PRIVATE_PATH")
            b=z.read(n)
            need(len(b)==x["bytes"] and digest(b)==x["sha256"],"ZIP_MEMBER_HASH")
        return index
def extract(zip_path,site):
    need(not site.exists() and not site.is_symlink() and site.parent==TMP,"DISPOSABLE_SITE_EXISTS")
    site.mkdir(mode=0o700)
    with zipfile.ZipFile(zip_path) as z: z.extractall(site)
def terminate(p):
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(timeout=8)
        except subprocess.TimeoutExpired: p.kill();p.wait(timeout=8)
def native(archive,engine):
    site=TMP/("p08-r43-clean-full-"+engine)
    extract(archive,site)
    e=dict(ENV,P08_R43_ENGINE=engine)
    cid=None
    try:
        if engine!="sqlite":
            image={"mysql":"mysql:8.4","mariadb":"mariadb:11.8"}[engine]
            name="p08-mode-ad-"+ENV["GITHUB_RUN_ID"]+"-"+engine
            cid=run("DB_START_"+engine,["docker","run","--rm","-d","--name",name,"-p","127.0.0.1:3306:3306","-e","MYSQL_ROOT_PASSWORD="+e["P08_R43_DB_PASSWORD"],"-e","MYSQL_DATABASE=p08_r43_new_main",image],env=e,timeout=240)
            need(re.fullmatch(r"[a-f0-9]{64}",cid),"DB_CONTAINER_ID")
            probe='new PDO("mysql:host=127.0.0.1;port=3306;dbname=p08_r43_new_main","root",getenv("P08_R43_DB_PASSWORD"),[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);'
            for _ in range(60):
                x=subprocess.run(["php","-r",probe],env=e,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=6)
                if x.returncode==0: break
                time.sleep(2)
            else: raise RuntimeError("DB_READY_"+engine)
            note("DB_READY_"+engine)
        run("NATIVE_INSTALL_"+engine,["php","tests/native/r43_clean_full_three_engines.php"],env=e,timeout=180,markers=["P08_R43_REAL_018_FRESH_FULL_SOURCE_AND_INSTALL=PASS","P08_R43_REAL_018_"+engine+"_23_MIGRATIONS_S9_OWNER=PASS","P08_R43_REAL_018_LANDING_REVISION_AND_REINSTALL_REFUSAL=PASS"])
        run("NATIVE_RESTORE_"+engine,["php","tests/native/r43_clean_full_snapshot_restore.php"],env=e,timeout=240,markers=["P08_R43_REAL_018_COORDINATED_NATIVE_BACKUP_"+engine+"=PASS","P08_R43_REAL_018_PRIVATE_MEDIA_TOKEN_OWNER_INDEPENDENT_RESTORE=PASS","P08_R43_REAL_018_INDEPENDENT_NATIVE_DB_23_DDL_OWNER_DATA_RESTORE=PASS","P08_R43_REAL_018_DIRTY_AND_SAME_DB_RESTORE_REFUSED=PASS"])
        run("NATIVE_SIGKILL_"+engine,["php","tests/native/r43_clean_full_fault_matrix.php"],env=e,timeout=240,markers=["P08_R43_NEW_FULL_NATIVE_SNAPSHOT_REAL_SIGKILL_137=PASS","P08_R43_NEW_FULL_CORRUPT_NATIVE_DB_SNAPSHOT_REFUSED=PASS","P08_R43_NEW_FULL_CORRUPT_PRIVATE_MEDIA_PRESTAGE_REFUSED=PASS","P08_R43_NEW_FULL_POST_SIGKILL_WRITE_AND_RESNAPSHOT_REFUSED=PASS"])
        run("NATIVE_INDEPENDENT_RECOVERY_"+engine,["php","tests/native/r43_snapshot_only_independent_recovery.php"],env=e,timeout=180,markers=["P08_R43_SNAPSHOT_RECOVERY_WRITER_GATE_AND_NEW_NATIVE_BACKUP=PASS","P08_R43_SNAPSHOT_RECOVERY_NO_SCHEMA_UPDATE_NO_ACTIVE_RESTORE=PASS"])
    finally:
        if cid and re.fullmatch(r"[a-f0-9]{64}",cid):
            run("DB_CLEANUP_"+engine,["docker","rm","-f",cid],timeout=60)
def https_install(archive):
    site=TMP/"p08-v018-formal-proof"/"https-site"
    # A unique, owned directory under the exact proof workspace.
    need(not site.exists(),"HTTPS_SITE_EXISTS")
    site.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as z: z.extractall(site)
    sqlite=site/"database"/("a"*32+".sqlite")
    sqlite.touch(mode=0o600,exist_ok=False)
    router=D/"https-router.php"
    router.write_text("<?php\n$_SERVER['HTTPS']='on';\n$_SERVER['SERVER_PORT']=443;\n$p=parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH) ?: '/';\nif ($p!=='/' && is_file($_SERVER['DOCUMENT_ROOT'].$p)) return false;\nrequire $_SERVER['DOCUMENT_ROOT'].'/index.php';\n")
    relay=D/"https-relay.cjs"
    relay.write_text("const tls=require('node:tls'),net=require('node:net'),fs=require('node:fs');const s=tls.createServer({key:fs.readFileSync(process.argv[2]),cert:fs.readFileSync(process.argv[3])},c=>{const b=net.connect(18080,'127.0.0.1');const stop=()=>{c.destroy();b.destroy()};c.on('error',stop);b.on('error',stop);c.on('close',stop);b.on('close',stop);c.pipe(b);b.pipe(c)});s.listen(18443,'127.0.0.1');\n")
    key=D/"key.pem"; cert=D/"cert.pem"
    run("HTTPS_CERT",["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","1","-keyout",str(key),"-out",str(cert),"-subj","/CN=127.0.0.1"],cwd=D)
    php=None; tls=None
    # Self-signed TLS confined to this synthetic loopback certificate; no product TLS bypass.
    ctx=ssl._create_unverified_context()
    origin="https://127.0.0.1:18443"
    def request(method,path="/setup.php",body=None,cookie="",host="127.0.0.1:18443",orig=None):
        con=http.client.HTTPSConnection("127.0.0.1",18443,timeout=25,context=ctx)
        headers={"Host":host}
        if cookie: headers["Cookie"]=cookie
        if orig is not None: headers["Origin"]=orig
        if body is not None:
            body=urllib.parse.urlencode(body).encode()
            headers["Content-Type"]="application/x-www-form-urlencoded"
        try:
            con.request(method,path,body,headers)
            res=con.getresponse()
            return res.status,res.getheaders(),res.read().decode(errors="replace")
        finally: con.close()
    def fresh():
        status,headers,html=request("GET")
        m=re.search(r'name="csrf" value="([a-f0-9]{64})"',html)
        cookie=next((v.split(";",1)[0] for k,v in headers if k.lower()=="set-cookie" and v.startswith("adops_setup=")),"")
        need(status==200 and m and cookie,"HTTPS_SETUP_GET")
        return m.group(1),cookie
    password="Synthetic-SQLite-Owner-12345!"
    def payload(token):
        return {"csrf":token,"site_name":"P08 final isolated","owner_username":"isolated_admin","owner_email":"owner@isolated.example","owner_password":password,"owner_confirm":password,"db_driver":"sqlite","db_database":sqlite.name,"github_token_later":"1","github_read_token":""}
    try:
        php=subprocess.Popen(["php","-S","127.0.0.1:18080","-t",str(site/"public"),str(router)],cwd=site,env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        tls=subprocess.Popen(["node",str(relay),str(key),str(cert)],cwd=D,env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                fresh()
                break
            except (OSError,RuntimeError,http.client.HTTPException): time.sleep(1)
        else: raise RuntimeError("HTTPS_SETUP_NOT_READY")
        note("HTTPS_REAL_SETUP_GET")
        token,cookie=fresh()
        status,_,html=request("POST",body=payload("0"*64),cookie=cookie,orig=origin)
        need(status==419 and password not in html and not (site/".env").exists(),"HTTPS_CSRF_NEGATIVE")
        note("HTTPS_CSRF_NEGATIVE")
        for bad,host in [("https://invalid.example","127.0.0.1:18443"),("http://127.0.0.1:18443","127.0.0.1:18443"),(origin,"invalid.example")]:
            token,cookie=fresh()
            status,_,html=request("POST",body=payload(token),cookie=cookie,orig=bad,host=host)
            need(status==403 and password not in html and not (site/".env").exists(),"HTTPS_HOST_ORIGIN_NEGATIVE")
        note("HTTPS_HOST_ORIGIN_NEGATIVE")
        token,cookie=fresh()
        status,_,html=request("POST",body=payload(token),cookie=cookie,orig=origin)
        need(status==200 and "安装成功" in html and password not in html and (site/"current").is_symlink() and os.readlink(site/"current")=="releases/"+SOURCE,"HTTPS_REAL_OWNER_SETUP")
        note("HTTPS_REAL_OWNER_SETUP")
        need(request("GET")[0]==403 and request("GET","/login")[0]==200 and request("GET","/app")[0] in (302,303),"HTTPS_INSTALLED_BOUNDARY")
        note("HTTPS_INSTALLED_BOUNDARY")
        browser=dict(ENV,P08_TEST_BASE_URL=origin,P08_R43_CLEAN_FULL_BROWSER="YES",PLAYWRIGHT_BROWSERS_PATH=str(D/"browsers"))
        run("LOCKED_CHROMIUM",["pnpm","exec","playwright","install","chromium"],env=browser,timeout=360)
        run("HTTPS_OWNER_LOGIN_UPDATE_REFUSAL",["pnpm","exec","playwright","test","tests/e2e/r43-clean-full-no-autoupgrade.spec.ts","--reporter=line","--output="+str(D/"browser-output")],env=browser,timeout=180)
        need("1 passed" in (D/"HTTPS_OWNER_LOGIN_UPDATE_REFUSAL.log").read_text(errors="replace"),"HTTPS_BROWSER_SKIPPED_OR_EMPTY")
        note("HTTPS_OWNER_BROWSER_ACTUAL_CASE")
    finally:
        terminate(tls);terminate(php)
        note("HTTPS_PROCESS_CLEANUP")
def canonical_reuse(builder,archive,index):
    original=D/"original.zip"
    need(original.is_file() and filehash(original)==OLD_ZIP,"ORIGINAL_B_ARTIFACT_NOT_AVAILABLE")
    with zipfile.ZipFile(original) as outer:
        need(set(outer.namelist())=={"p08-dev-full.zip","p08-ui-evidence.zip","full-receipt.json"},"B_ARTIFACT_MEMBERS")
        oldfull=outer.read("p08-dev-full.zip"); oldui=outer.read("p08-ui-evidence.zip")
        receipt=json.loads(outer.read("full-receipt.json"))
        need(digest(oldfull)==OLD_FULL and digest(oldui)==OLD_UI and receipt["source"]==OLD and receipt["tree"]==OLDTREE and receipt["run_id"]=="46140343955","B_ARTIFACT_IDENTITY")
    oldpath=D/"original-full.zip";oldpath.write_bytes(oldfull)
    oldindex=check_archive(oldpath,OLD)
    need(set(oldindex)==set(index),"B_RUNTIME_MEMBER_SET_CHANGED")
    delta={x for x in index if index[x]["sha256"]!=oldindex[x]["sha256"]}
    allowed={"CLOUDPANEL_INSTALL.txt","public/p08-install-build.txt","vendor/composer/installed.php"}
    need(delta<=allowed and {"CLOUDPANEL_INSTALL.txt","public/p08-install-build.txt"}<=delta,"B_RUNTIME_BYTES_CHANGED")
    if "vendor/composer/installed.php" in delta:
        with zipfile.ZipFile(oldpath) as o,zipfile.ZipFile(archive) as n:
            f="vendor/composer/installed.php"
            need(o.read(f).replace(OLD.encode(),SOURCE.encode())==n.read(f),"B_COMPOSER_NON_IDENTITY_DRIFT")
    print("P08_B_RUNTIME_UNCHANGED_FILES="+str(len(index)-len(delta)),flush=True)
    note("P08_B_RUNTIME_PARITY")
    # Only the already independently adjudicated original screenshot bytes are reused.
    # Current source/tree and installation bind the new package; the captures retain
    # original source/Run identity explicitly, never relabeled as new captures.
    groups={
      "landing":("landing-entry","s2-editor","s2-saved-preview","s2-export-refused"),
      "static":("deploy-entry","s3-landing-revision","s3-version-diff","s3-verified-download"),
      "domains":("domains-entry","s4-domain-registered","s4-filter-empty"),
      "tracker":("trackers-entry","s5-kuma-connect","s5-bemob-connect","s5-campaign-report"),
      "ads":("advertising-entry","s6-saved-report","s6-no-report","s6-pop-report"),
      "monitoring":("monitoring-entry","s7-account-report","s7-pair-reviewed","s7-persisted-review"),
      "automation":("automation-entry","s8-paused-rule","s8-reviewed-suggestion","s8-emergency-stopped")}
    refs={
      "landing":("https://landingi.com/help/editor-available-options/","LandingPanel"),
      "static":("https://developers.cloudflare.com/pages/get-started/direct-upload/","StaticPanel"),
      "domains":("https://developers.cloudflare.com/dns/","DomainPanel"),
      "tracker":("https://v10.docs.keitaro.io/en/get-started/working-area.html","TrackerPanel"),
      "ads":("https://help.redtrack.io/knowledgebase/kb/basic-setup-9785/reports-and-dashboards-r-10959/reporting-ads-manager-10970/","AdsPanel"),
      "monitoring":("https://help.redtrack.io/knowledgebase/kb/basic-setup-9785/reports-and-dashboards-r-10959/reporting-dashboard-10967/","MonitoringPanel"),
      "automation":("https://help.optmyzr.com/en/articles/3076017-what-is-the-rule-engine","AutomationPanel")}
    acts={
      "landing-entry":"open landing list","s2-editor":"edit order and undo redo","s2-saved-preview":"save and preview immutable revision","s2-export-refused":"reject unsafe export retaining edits",
      "deploy-entry":"open static deployment","s3-landing-revision":"import landing revision","s3-version-diff":"compare local versions","s3-verified-download":"verify local download",
      "domains-entry":"open domain registry","s4-domain-registered":"register edit TXT proof","s4-filter-empty":"filter and remove local record",
      "trackers-entry":"open trackers","s5-kuma-connect":"select Simple Kuma account form","s5-bemob-connect":"select BeMob account form","s5-campaign-report":"inspect saved campaign report and missing ROI",
      "advertising-entry":"open advertising","s6-saved-report":"filter export and review selected account report","s6-no-report":"refuse export without report","s6-pop-report":"inspect saved PopAds report",
      "monitoring-entry":"open monitoring","s7-account-report":"inspect source-bound account metrics","s7-pair-reviewed":"review source pair and CPA","s7-persisted-review":"read persisted review",
      "automation-entry":"open rules","s8-paused-rule":"create paused rule","s8-reviewed-suggestion":"review dry-run suggestion","s8-emergency-stopped":"stop and resume local rule"}
    analysis=D/"accepted-reference-analysis.md"
    analysis.write_bytes((P/"docs/product/P08_S0_R02_PROTOTYPE_ACCEPT_SIMPLIFY_REJECT_20261122.md").read_bytes())
    baseline={"category":"B","scope_source":SOURCE,"scope_tree":TREE,"scope_ref":"Accepted original B scope 27 states x 3; controller delta PASS 46140343955, unchanged runtime bytes proven; exact new package Mode AD RP-07AD","references":{},"items":{}}
    mappings=[]
    with zipfile.ZipFile(io.BytesIO(oldui)) as u:
        m=json.loads(u.read("manifest.json"))
        need(m["source"]==OLD and m["tree"]==OLDTREE and m["run_id"]=="46140343955" and m["count"]==81 and m["complete"] is True and not m["capture_failed"] and len(m["browser_specs"])==7 and all(v=="PASS" for v in m["browser_specs"].values()),"B_UI_MANIFEST")
        rows=m["screenshots"]
        need(len(rows)==81 and len({x["file"] for x in rows})==81 and {x["state"] for x in rows}==set(acts),"B_UI_DENOMINATOR")
        for group,states in groups.items():
            locator,component=refs[group]
            baseline["references"][group]={"locator":locator,"owner_selection":"Accepted mature prototype B scope per R02/R03 and independent B review","observation_source":"Original documented prototype observations and actual installed developer Run 46140343955","analysis_file":analysis.name,"analysis_sha256":filehash(analysis)}
            for state in states:
                rr=sorted([x for x in rows if x["state"]==state],key=lambda x:x["width"])
                need([x["width"] for x in rr]==[390,768,1440],"B_UI_WIDTH")
                captures=[]
                for x in rr:
                    name=x["file"]
                    need(re.fullmatch(r"p08-ui-"+OLD+r"-[a-z0-9-]+-(390|768|1440)\.png",name) is not None,"B_CAPTURE_NAME")
                    data=u.read(name)
                    need(digest(data)==x["sha256"] and len(data)==x["bytes"],"B_CAPTURE_HASH")
                    need(data[:8]==b"\x89PNG\r\n\x1a\n" and int.from_bytes(data[16:20],"big")==x["width"] and int.from_bytes(data[20:24],"big")==x["height"],"B_CAPTURE_DIMENSIONS")
                    (D/name).write_bytes(data)
                    captures.append({"viewport":[x["width"],x["height"]],"screenshot":name,"sha256":x["sha256"],"original_source":OLD,"original_run":"46140343955"})
                action=acts[state]
                baseline["items"][state]={"reference":group,"surface":state,"observed_flow":action,"components":component,"feature_scope":"Local synthetic, no real provider write or remote deployment","acceptance":"Original controller B adjudication retained; only on proven identical runtime","actions":[action],"viewports":[x["viewport"] for x in captures]}
                implementation="resources/js/modules/"+group+"/"+component+".vue"
                need((P/implementation).is_file(),"B_IMPLEMENTATION_PATH")
                mappings.append({"item":state,"reference":group,"actions":[action],"implementation_paths":[implementation],"interaction_evidence":"Original Run 46140343955 / "+rr[0]["spec"]+"; prior controller independent review accepted, current exact package runtime parity PASS","comparison":"MEETS_CONTRACT","captures":captures})
    proof=D/"final-install-machine.json"
    proof.write_text(json.dumps({"source":SOURCE,"tree":TREE,"run":ENV["GITHUB_RUN_ID"],"full_sha256":filehash(archive),"executed_passes":PASS},sort_keys=True))
    report={"category":"B","new_source":SOURCE,"new_tree":TREE,"capture_source":OLD,"capture_tree":OLDTREE,"mappings":mappings,"installation":{"source":SOURCE,"tree":TREE,"status":"PASS","executed_steps":len(PASS),"run":ENV["GITHUB_RUN_ID"],"evidence_file":proof.name,"evidence_sha256":filehash(proof)},"developer_use":"https://github.com/llhzx2018/vf-adops/pull/135#issuecomment-7236594406 and Run 46140343955, inherited only on verified runtime parity","independent_review":"Controller actual independent B delta PASS recorded in https://github.com/llhzx2018/vf-adops/pull/113#issuecomment-7238922637; no new visual verdict claimed"}
    b=D/"prototype-scope.json";q=D/"prototype-report.json"
    b.write_text(json.dumps(baseline));q.write_text(json.dumps(report))
    builder.verify_canonical_full_contract(P,archive,SOURCE,G,"delivery",ux_baseline=b,owner_ux_status="PENDING",prototype_report=q)
    note("P08_MODE_AD_CANONICAL_DELIVERY_STRUCTURE")
def main():
    need(ENV.get("GITHUB_ACTIONS")=="true" and ENV.get("GITHUB_ACTOR")=="llhzx2018" and ENV.get("GITHUB_REPOSITORY")=="llhzx2018/core-free-runner-public" and os.geteuid()!=0,"RUN_SCOPE")
    need(D.is_dir() and not D.is_symlink() and git(P,"rev-parse","HEAD")==SOURCE and git(P,"rev-parse","HEAD^{tree}")==TREE and git(P,"rev-parse","refs/remotes/origin/main")==SOURCE and git(G,"rev-parse","HEAD")==GOV,"EXACT_SOURCE")
    need((P/"VERSION").read_text().strip()=="0.1.18" and "## RP-07AD" in (P/"docs/authority/ACCEPTANCE_MATRIX.md").read_text() and "| skill-release | V3.30 |" in (G/"CURRENT.md").read_text(),"MODE_AD_AUTHORITY")
    need(set(git(P,"diff","--name-only",BASE,SOURCE).splitlines())=={"CLOUDPANEL_INSTALL.txt","public/p08-install-build.txt","docs/authority/ACCEPTANCE_MATRIX.md"},"FINAL_DIFF")
    note("P08_MODE_AD_FINAL_SOURCE")
    run("PHP84_FLOOR",["php","-r",'exit(PHP_VERSION_ID>=80428 && PHP_VERSION_ID<80500 && extension_loaded("pdo_mysql") && extension_loaded("pdo_sqlite") && extension_loaded("pcntl") && extension_loaded("zip")?0:2);'])
    need(run("NODE_VERSION",["node","--version"])=="v24.22.3","NODE_PIN")
    need("Composer version 2.11.3" in run("COMPOSER_VERSION",["composer","--no-plugins","--no-scripts","--no-ansi","--version"]),"COMPOSER_PIN")
    prefix=D/"pnpm";prefix.mkdir(mode=0o700)
    run("PNPM_TOOL",["npm","install","--prefix",str(prefix),"--ignore-scripts","--no-fund","--no-audit","pnpm@11.29.0"],cwd=D,timeout=240)
    ENV["PATH"]=str(prefix/"node_modules/.bin")+":"+ENV["PATH"]
    need(run("PNPM_VERSION",["pnpm","--version"])=="11.29.0","PNPM_PIN")
    run("COMPOSER_LOCK",["composer","install","--no-dev","--no-scripts","--no-plugins","--prefer-dist","--no-interaction","--no-progress"],timeout=600)
    run("COMPOSER_PLATFORM",["composer","check-platform-reqs","--no-dev"],timeout=90)
    run("PNPM_LOCK",["pnpm","install","--frozen-lockfile"],timeout=600)
    run("VITE_BUILD",["pnpm","run","build"],timeout=240)
    need(not git(P,"status","--porcelain","--untracked-files=all"),"TRACKED_OR_UNIGNORED_DRIFT")
    run("STACK_FULL",["python3","-B","scripts/check_stack_contract.py","--phase","full"],timeout=90)
    sys.path.insert(0,str(P/"scripts"))
    import build_full as builder
    a=D/"VF_AdOps_V0.1.18_FULL.zip";b=D/"second.zip"
    # Prepublication construction only, delivery checker runs after actual install and B byte parity.
    builder.verify_canonical_full_contract(P,a,SOURCE,G,"resolve")
    for z in (a,b): builder.write_full(P,z,"0.1.18",SOURCE)
    need(filehash(a)==filehash(b),"DOUBLE_BUILD_BYTES")
    index=check_archive(a,SOURCE);check_archive(b,SOURCE)
    print("P08_MODE_AD_FULL_SHA256="+filehash(a),flush=True)
    print("P08_MODE_AD_FULL_BYTES="+str(a.stat().st_size),flush=True)
    print("P08_MODE_AD_FULL_PAYLOAD_FILES="+str(len(index)),flush=True)
    note("P08_MODE_AD_DOUBLE_BUILD")
    # Run the original native backup/restore/fault/recovery scripts on independent clean sites.
    if not shutil.which("mariadb-dump"):
        run("SQL_NATIVE_CLIENT_INDEX",["sudo","apt-get","update","-qq"],cwd=D,timeout=180)
        run("SQL_NATIVE_CLIENT",["sudo","apt-get","install","-y","-qq","mariadb-client"],cwd=D,timeout=240)
    errors=[]
    for engine in ("sqlite","mysql","mariadb"):
        try: native(a,engine)
        except Exception as exc:
            print("P08_NATIVE_"+engine+"_NOT_PROVEN",flush=True);errors.append(engine)
    try: https_install(a)
    except Exception as exc:
        print("P08_HTTPS_NOT_PROVEN",flush=True);errors.append("https")
    need(not errors,"NATIVE_OR_HTTPS_GATES_NOT_PROVEN")
    canonical_reuse(builder,a,index)
    print("P08_MODE_AD_MACHINE_PREPUBLICATION_PROOF=PASS",flush=True)
    print("P08_MODE_AD_FORMAL_RELEASE=NOT_ISSUED",flush=True)
if __name__=="__main__":
    try: main()
    except Exception as e:
        reason=str(e)
        print("P08_MODE_AD_PREISSUE_STOP="+(reason if re.fullmatch(r"[A-Z0-9_a-z]{3,120}",reason) else "UNCLASSIFIED_SAFE"),flush=True)
        sys.exit(1)
