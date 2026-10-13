#!/usr/bin/env python3
"""Synthetic WordPress HTTP integration for Ops-owned settings form.
Test-only admin/subscriber accounts and synthetic MariaDB, no Production calls.
"""
import http.cookiejar, html.parser, json, os, subprocess, urllib.parse, urllib.request, urllib.error, pathlib
BASE="http://127.0.0.1:18880"
CONTAINER=os.environ["WP"]
PROOF=[]
KEYS=("downloader_auto_part_enabled","downloader_part_size_mb","downloader_retry_count","downloader_wake_lock_enabled","downloader_filename_pattern","downloader_allow_user_override")
class Inputs(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.open=False;self.action=None;self.fields={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="form" and "vf-v6-tools-settings-form" in a.get("class","").split():
            self.open=True;self.action=a.get("action","")
        elif self.open and tag in ("input","select") and "name" in a:
            self.fields[a["name"]]=a.get("value","")
    def handle_endtag(self,tag):
        if tag=="form" and self.open:self.open=False
def check(x,why):
    if not x:raise AssertionError(why)
    print("PASS "+why,flush=True);PROOF.append(why)
def wp_eval(expression):
    result=subprocess.run(["docker","exec","--user","www-data",CONTAINER,"php","/usr/local/bin/wp",
      "eval",expression,"--path=/var/www/html"],text=True,capture_output=True,check=True)
    return result.stdout.strip().splitlines()[-1]
def snap():
    php=r'''require_once WP_PLUGIN_DIR."/vf-tool-m3u8/includes/v510-settings.php";
$r=m3u8_settings_readback();$a=(array)($r["data"]["engineSettings"]??[]);
echo wp_json_encode(["revision"=>(int)$r["revision"],"settings"=>array_intersect_key($a,array_fill_keys([
"downloader_auto_part_enabled","downloader_part_size_mb","downloader_retry_count",
"downloader_wake_lock_enabled","downloader_filename_pattern","downloader_allow_user_override"],true))]);'''
    return json.loads(wp_eval(php))
def login(user,passwd):
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(BASE+"/wp-login.php",timeout=20).read()
    opener.open(BASE+"/wp-login.php",data=urllib.parse.urlencode({"log":user,"pwd":passwd,
      "wp-submit":"Log In","redirect_to":BASE+"/wp-admin/","testcookie":"1"}).encode(),timeout=20)
    check(any("wordpress_logged_in_" in cookie.name for cookie in jar),"actual WordPress login session for "+user)
    return jar,opener
def form(opener):
    page=opener.open(BASE+"/wp-admin/admin.php?page=vf-toolsite-tools",timeout=30).read().decode()
    inputs=Inputs();inputs.feed(page)
    check(inputs.action is not None,"Ops Workbench settings form in real WP HTML")
    for k in KEYS:check(k in inputs.fields,"visible canonical field "+k)
    check("vf_s01_settings_revision" in inputs.fields,"form contains canonical revision")
    check("vf_ops_s01_settings_nonce" in inputs.fields,"form contains scoped nonce")
    return inputs
class DoNotFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def request(jar, f, *, revision="CURRENT", nonce="CURRENT", updates=None):
    posted={"action":"vf_ops_s01_m3u8_settings_save",
      "vf_s01_settings_revision":f.fields["vf_s01_settings_revision"] if revision=="CURRENT" else revision,
      "vf_ops_s01_settings_nonce":f.fields["vf_ops_s01_settings_nonce"] if nonce=="CURRENT" else nonce,
      "downloader_part_size_mb":"512","downloader_retry_count":"4",
      "downloader_filename_pattern":"{source}-{date}-{time}",
      "downloader_wake_lock_enabled":"on","downloader_allow_user_override":"on"}
    if updates:posted.update(updates)
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),DoNotFollow())
    data=urllib.parse.urlencode(posted).encode()
    try:
      response=opener.open(urllib.request.Request(BASE+"/wp-admin/admin-post.php",data=data,method="POST"),timeout=25)
      return response.status,response.headers.get("Location","")
    except urllib.error.HTTPError as e:
      return e.code,e.headers.get("Location","")
start=snap()
check(start["revision"]>=1,"Provider MariaDB canonical revision exists")
check(all(k in start["settings"] for k in KEYS),"all six settings exist in Provider canonical state")
admin,web=login("admin","Synthetic-Only-PR407!")
f=form(web)
check(int(f.fields["vf_s01_settings_revision"])==start["revision"],"Ops form revision matches real Provider DB")
# PHP $_POST absent revision is distinct from supplied malformed strings.
for bad in ("","0","-1","1.3","garbage","999999999999999999999999999"):
  status,loc=request(admin,f,revision=bad)
  check(status==302 and "settings_conflict" in loc,"malformed revision rejected: "+repr(bad))
  check(snap()==start,"malformed revision leaves canonical DB intact: "+repr(bad))
status,_=request(admin,f,nonce="wrong")
check(status==403,"incorrect scoped nonce rejected HTTP 403")
check(snap()==start,"bad nonce does not alter DB")
guest,guest_web=login("subscriber","Synthetic-Only-Reader!")
status,_=request(guest,f)
check(status==403,"subscriber forbidden before settings write")
check(snap()==start,"subscriber cannot change Provider settings")
# Accept a real permitted POST through the existing Provider transaction.
status,loc=request(admin,f)
check(status==302 and "settings_saved" in loc,"valid role+nonce+revision saves real settings")
after=snap()
check(after["revision"]==start["revision"]+1,"Provider revision advances exactly one")
checks={"downloader_auto_part_enabled":False,"downloader_part_size_mb":"512",
  "downloader_retry_count":4,"downloader_wake_lock_enabled":True,
  "downloader_filename_pattern":"{source}-{date}-{time}",
  "downloader_allow_user_override":True}
for key,expected in checks.items():
  value=after["settings"][key]
  if key in ("downloader_retry_count","downloader_part_size_mb"):
    check(str(value)==str(expected),"real DB saved "+key)
  else:check(value==expected,"real DB saved "+key)
status,loc=request(admin,f)
check(status==302 and "settings_conflict" in loc,"stale optimistic-lock form rejected")
check(snap()==after,"stale form does not mutate Provider settings")
# A separate authorized request restores all original values, not history.
fresh=form(web)
original={"action":"vf_ops_s01_m3u8_settings_save",
  "vf_s01_settings_revision":fresh.fields["vf_s01_settings_revision"],
  "vf_ops_s01_settings_nonce":fresh.fields["vf_ops_s01_settings_nonce"],
  "downloader_part_size_mb":str(start["settings"]["downloader_part_size_mb"]),
  "downloader_retry_count":str(start["settings"]["downloader_retry_count"]),
  "downloader_filename_pattern":str(start["settings"]["downloader_filename_pattern"])}
for k in ("downloader_auto_part_enabled","downloader_wake_lock_enabled","downloader_allow_user_override"):
    if start["settings"][k]:original[k]="on"
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(admin),DoNotFollow())
try:
  response=opener.open(urllib.request.Request(BASE+"/wp-admin/admin-post.php",
      data=urllib.parse.urlencode(original).encode(),method="POST"),timeout=25)
  status,loc=response.status,response.headers.get("Location","")
except urllib.error.HTTPError as e:status,loc=e.code,e.headers.get("Location","")
check(status==302 and ("settings_saved" in loc or "settings_no_change" in loc),"original canonical settings restored by valid admin POST")
final=snap()
check(final["settings"]==start["settings"],"six canonical settings restored exactly")
check(final["revision"]>=after["revision"],"revision remains monotonic")
pathlib.Path("proof").mkdir(exist_ok=True)
pathlib.Path("proof/ops-407-http-post.json").write_text(json.dumps({
  "result":"PASS","checks":len(PROOF),"scenarios":PROOF,
  "site":"disposable_synthetic_wordpress","production":"NOT_EXECUTED","scope":"PR407_exact_source"
},indent=2))
print("S01_OPS_407_REAL_HTTP_POST_SECURITY_PASS",len(PROOF))
