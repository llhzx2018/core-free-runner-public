#!/usr/bin/env python3
"""Real isolated WordPress admin-post, nonce/capability/revision/DB readback.
No Production calls or external application endpoints.
"""
import http.cookiejar
import html.parser
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import urllib.error

BASE="http://127.0.0.1:18880"
WP=os.environ["WP"]
RESULTS=[]
KEYS=("downloader_auto_part_enabled","downloader_part_size_mb","downloader_retry_count",
      "downloader_wake_lock_enabled","downloader_filename_pattern","downloader_allow_user_override")
class FormParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__();self.inside=False;self.form=None;self.fields={}
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="form" and "vf-v6-tools-settings-form" in a.get("class","").split():
            self.inside=True;self.form=a.get("action","")
        elif tag=="input" and self.inside and "name" in a:
            self.fields[a["name"]]=a.get("value","") if a.get("type")!="checkbox" else "on"
        elif tag=="textarea" and self.inside and "name" in a:
            self.fields[a["name"]]=""
    def handle_endtag(self, tag):
        if tag=="form" and self.inside:self.inside=False
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def check(condition,label):
    if not condition:raise AssertionError(label)
    print("PASS",label,flush=True);RESULTS.append(label)
def snapshot():
    php="""$v=m3u8_settings_readback();$e=(array)($v["data"]["engineSettings"]??[]);
echo wp_json_encode(["revision"=>(int)$v["revision"],"settings"=>array_intersect_key($e,array_fill_keys([
"downloader_auto_part_enabled","downloader_part_size_mb","downloader_retry_count",
"downloader_wake_lock_enabled","downloader_filename_pattern","downloader_allow_user_override"],true))]);"""
    proc=subprocess.run(["docker","exec","--user","www-data",WP,"php","/usr/local/bin/wp",
        "eval",php,"--path=/var/www/html"],capture_output=True,text=True,check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])
def login(user,pwd):
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(BASE+"/wp-login.php",timeout=20).read()
    params={"log":user,"pwd":pwd,"wp-submit":"Log In","redirect_to":BASE+"/wp-admin/","testcookie":"1"}
    r=opener.open(BASE+"/wp-login.php",data=urllib.parse.urlencode(params).encode(),timeout=20)
    check(any("wordpress_logged_in_" in c.name for c in jar),"real WP authenticated cookie "+user)
    return jar,opener
def form(opener):
    html=opener.open(BASE+"/wp-admin/admin.php?page=vf-toolsite-tools",timeout=25).read().decode("utf-8")
    f=FormParser();f.feed(html)
    check(f.form is not None,"Ops six-settings form rendered to actual authenticated browser")
    for k in KEYS:check(k in f.fields,"Ops renders "+k)
    check("vf_ops_s01_settings_nonce" in f.fields and "vf_s01_settings_revision" in f.fields,
          "real WordPress form has nonce and revision")
    return f
def post(jar, f, revision=None, nonce=None, choices=None):
    args={"action":"vf_ops_s01_m3u8_settings_save",
          "vf_ops_s01_settings_nonce":nonce if nonce is not None else f.fields["vf_ops_s01_settings_nonce"],
          "vf_s01_settings_revision":revision if revision is not None else f.fields["vf_s01_settings_revision"],
          "downloader_part_size_mb":"512","downloader_retry_count":"4",
          "downloader_filename_pattern":"{source}-{date}-{time}",
          "downloader_wake_lock_enabled":"on",
          "downloader_allow_user_override":"on"}
    if choices is not None:args.update(choices)
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),NoRedirect())
    request=urllib.request.Request(BASE+"/wp-admin/admin-post.php",
                                   data=urllib.parse.urlencode(args).encode("utf-8"),
                                   method="POST")
    try:
        res=opener.open(request,timeout=25)
        status=res.status;location=res.headers.get("Location","")
    except urllib.error.HTTPError as e:
        status=e.code;location=e.headers.get("Location","")
    return status,location

start=snapshot()
check(start["revision"]>=1,"Provider canonical revision exists in MariaDB")
admin,ao=login("admin","Synthetic-Only-PR407!")
f=form(ao)
check(int(f.fields["vf_s01_settings_revision"])==start["revision"],
      "Ops WP HTML form revision equals Provider database readback")
# Reject accidental initial revision 1 when valid nonce but invalid revision.
for invalid in ("","0","-1","1.7","junk","9999999999999999999999999999999"):
    status,location=post(admin,f,revision=invalid)
    check(status==302 and "vf_s01_action=settings_conflict" in location,
          "malformed revision is rejected: "+repr(invalid))
    check(snapshot()==start,"malformed revision preserves canonical state: "+repr(invalid))
status,_=post(admin,f,nonce="invalid-explicit-nonce")
check(status==403,"admin invalid nonce rejected HTTP 403")
check(snapshot()==start,"invalid nonce preserves Provider MariaDB settings")
subscriber,so=login("subscriber","Synthetic-Only-Reader!")
status,_=post(subscriber,f)
check(status==403,"subscriber role rejected HTTP 403 before nonce")
check(snapshot()==start,"subscriber denial preserves Provider state")
# Fresh valid request must save all six fields in original owning transaction.
status,location=post(admin,f)
check(status==302 and "vf_s01_action=settings_saved" in location,
      "valid nonce and revision save through real WordPress admin-post")
changed=snapshot()
check(changed["revision"]==start["revision"]+1,"Provider canonical revision increments after POST")
check(changed["settings"]["downloader_part_size_mb"]=="512","M3U8 saved part size")
check(int(changed["settings"]["downloader_retry_count"])==4,"M3U8 saved retry count")
check(changed["settings"]["downloader_auto_part_enabled"] is False,"M3U8 saved unchecked auto-part")
check(changed["settings"]["downloader_wake_lock_enabled"] is True,"M3U8 saved checked wake-lock")
check(changed["settings"]["downloader_allow_user_override"] is True,"M3U8 saved checked override")
check(changed["settings"]["downloader_filename_pattern"]=="{source}-{date}-{time}","M3U8 saved filename pattern")
status,location=post(admin,f)
check(status==302 and "settings_conflict" in location,"stale normal form revision rejected")
check(snapshot()==changed,"stale valid request does not modify Provider settings")
# Restore original six fields by new valid authorized transaction.
fresh=form(ao)
restore={"downloader_part_size_mb":str(start["settings"]["downloader_part_size_mb"]),
         "downloader_retry_count":str(start["settings"]["downloader_retry_count"]),
         "downloader_filename_pattern":str(start["settings"]["downloader_filename_pattern"])}
for k in ("downloader_auto_part_enabled","downloader_wake_lock_enabled","downloader_allow_user_override"):
    if bool(start["settings"][k]):restore[k]="on"
    else:restore.pop(k,None)
# post() supplies defaults for checkboxes: explicit override for missing keys
def authorized_restore():
    p={"action":"vf_ops_s01_m3u8_settings_save",
       "vf_ops_s01_settings_nonce":fresh.fields["vf_ops_s01_settings_nonce"],
       "vf_s01_settings_revision":fresh.fields["vf_s01_settings_revision"]}
    p.update(restore)
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(admin),NoRedirect())
    try:
        r=op.open(urllib.request.Request(BASE+"/wp-admin/admin-post.php",
                   data=urllib.parse.urlencode(p).encode(),method="POST"),timeout=25)
        return r.status,r.headers.get("Location","")
    except urllib.error.HTTPError as e:return e.code,e.headers.get("Location","")
status,location=authorized_restore()
check(status==302 and ("settings_saved" in location or "settings_no_change" in location),
      "original Provider settings restored by authorized WordPress POST")
end=snapshot()
check(end["settings"]==start["settings"],"all six canonical settings restored after test")
check(end["revision"]>=changed["revision"],"restore preserves monotonic optimistic-lock revision")
proof={"status":"PASS","checked":RESULTS,"checks":len(RESULTS),
       "source":"PR407_exact","production":"NOT_EXECUTED","canonical_preserved":True}
with open("proof/s01-ops-pr407-real-post.json","w") as fp:json.dump(proof,fp,indent=2)
print("S01_OPS_PR407_REAL_WP_POST_SECURITY_PASS",len(RESULTS),flush=True)
