#!/usr/bin/env python3
"""Only disposable P07 MariaDB/MySQL CloudPanel VM: *official admin form* proof.

Discovers routes and HTML forms from a successfully authenticated synthetic
CloudPanel admin session; never synthesizes privileged URLs, edits db.sq3,
disables the origin engine, or sends credentials outside localhost.
"""
from __future__ import annotations

from html.parser import HTMLParser
from http.cookiejar import CookieJar
import os
from pathlib import Path
import re
import ssl
import sys
from urllib.parse import urlencode, urljoin, urlsplit
import urllib.request
import sqlite3


BASE="https://127.0.0.1:8443"
USER="p07testadmin"
PASS="SyntheticOnly2026ABC!"
TARGET_USER="p07d05admin"
TARGET_PASS="P07_Synthetic_D05_Control_Only!"
TARGET_PORT=13307
STORE=Path("/home/clp/htdocs/app/data/db.sq3")


def say(k, v="PASS"):
    print(f"P07_D05_CP_UI_{k}={v}", flush=True)


class HTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms=[]
        self.links=[]
        self.form=None
        self.current_link=None
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=="form":
            self.form={"action":d.get("action",""),"method":d.get("method","GET").upper(),"inputs":{}}
        if tag=="input" and self.form is not None:
            name=d.get("name","")
            if name:
                self.form["inputs"][name]={"type":d.get("type","text"),"value":d.get("value","")}
        if tag=="a" and d.get("href"):
            self.current_link={"href":d["href"],"text":""}
    def handle_data(self,data):
        if self.current_link is not None:
            self.current_link["text"]+=data.strip()+" "
    def handle_endtag(self,tag):
        if tag=="form" and self.form is not None:
            self.forms.append(self.form)
            self.form=None
        if tag=="a" and self.current_link is not None:
            self.links.append(self.current_link)
            self.current_link=None


def must_local(url):
    u=urlsplit(url)
    if u.scheme!="https" or u.hostname!="127.0.0.1" or u.port!=8443:
        raise ValueError("P07_D05_CP_UI_OFFHOST_URL_REFUSED")
    return url


def cp_request(opener,path,post=None):
    url=must_local(urljoin(BASE+"/",path))
    args={"data":urlencode(post).encode() if post is not None else None}
    request=urllib.request.Request(url,**args)
    with opener.open(request,timeout=22) as response:
        resolved=must_local(response.geturl())
        content=response.read(300000).decode("utf8","replace")
    p=HTML();p.feed(content)
    return resolved,p,content


def sqlite_state():
    with sqlite3.connect("file:"+str(STORE)+"?mode=ro",uri=True) as conn:
        rows=conn.execute(
           "SELECT host,port,is_active FROM database_server ORDER BY id"
        ).fetchall()
    if sum(1 for r in rows if r[2]==1)!=1:
        raise RuntimeError("P07_D05_CP_UI_ACTIVE_COUNT_UNSAFE")
    return rows


def select_link(document, keys):
    for k in keys:
        for link in document.links:
            text=link["text"].strip().lower()
            url=link["href"].lower()
            if k in text or k in url:
                try:
                    must_local(urljoin(BASE+"/",link["href"]))
                except ValueError:
                    continue
                if not url.startswith("javascript:") and not url.startswith("#"):
                    return link["href"]
    return None


def find_add_form(document):
    for form in document.forms:
        names=list(form["inputs"])
        joined=" ".join(names).lower()
        if (form["method"]=="POST" and "port" in joined
                and "host" in joined and ("user" in joined or "username" in joined)
                and "password" in joined):
            return form
    return None


def submit_add(opener,path,page,form):
    # Only the discovered, already-rendered CloudPanel form is accepted.
    submit={}
    found=set()
    for name,info in form["inputs"].items():
        x=name.lower()
        value=info["value"]
        if "csrf" in x:
            submit[name]=value
        elif "host" in x and not "hostname" in x:
            submit[name]="127.0.0.1"
            found.add("host")
        elif "port" in x:
            submit[name]=str(TARGET_PORT)
            found.add("port")
        elif "password" in x:
            submit[name]=TARGET_PASS
            found.add("password")
        elif "user" in x:
            submit[name]=TARGET_USER
            found.add("user")
        else:
            submit[name]=value
    if found!={"host","port","password","user"}:
        raise RuntimeError("P07_D05_CP_UI_ADD_FIELDS_NOT_PROVEN")
    action=form["action"] or path
    next_path=urljoin(page,action)
    url,document,_=cp_request(opener,next_path,post=submit)
    rows=sqlite_state()
    if not any(int(port)==TARGET_PORT for _,port,_ in rows):
        raise RuntimeError("P07_D05_CP_UI_ADD_DID_NOT_REGISTER_SERVER")
    say("OFFICIAL_ADD_TARGET_REGISTERED")
    return url,document


def run():
    if (os.geteuid()!=0 or os.environ.get("P07_ALLOW_SYNTHETIC_D05")!="1"
        or Path("/root/.p07-d05-synthetic-qemu").read_bytes()!=
          b"P07_D05_EPHEMERAL_CLOUDPANEL_VM_ONLY\n"):
        raise RuntimeError("P07_D05_CP_UI_NO_EPHEMERAL_MARKER")
    opener=urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
        urllib.request.HTTPCookieProcessor(CookieJar()),
    )
    url,document,_=cp_request(opener,"/login")
    login=None
    for form in document.forms:
        names=list(form["inputs"])
        if "userName" in names and any(v["type"]=="password" for v in form["inputs"].values()):
            login=form
            break
    if login is None:
        raise RuntimeError("P07_D05_CP_UI_LOGIN_FORM_UNVERIFIED")
    fields={n:i["value"] for n,i in login["inputs"].items()}
    fields["userName"]=USER
    password_fields=[n for n,i in login["inputs"].items() if i["type"]=="password"]
    if len(password_fields)!=1:
        raise RuntimeError("P07_D05_CP_UI_PASSWORD_FORM_UNVERIFIED")
    fields[password_fields[0]]=PASS
    url,document,html=cp_request(opener,urljoin(url,login["action"] or "/login"),post=fields)
    if "/login" in urlsplit(url).path or "name=\"userName\"" in html:
        raise RuntimeError("P07_D05_CP_UI_SESSION_LOGIN_NOT_PROVEN")
    say("OFFICIAL_ADMIN_SESSION")
    url,document,html=cp_request(opener,"/")
    dbpath=select_link(document,["database servers","database-servers","database-server"])
    if dbpath is None:
        settings=select_link(document,["settings","admin area","admin"])
        if settings:
            u,d,_=cp_request(opener,settings)
            dbpath=select_link(d,["database servers","database-servers","database-server"])
    if dbpath is None:
        say("DATABASE_SERVERS_NAVIGATION","NOT_DISCOVERED")
        return 3
    page,document,html=cp_request(opener,dbpath)
    say("OFFICIAL_DATABASE_SERVERS_PAGE")
    form=find_add_form(document)
    if form is None:
        say("OFFICIAL_ADD_FORM","NOT_DISCOVERED")
        return 3
    page,document=submit_add(opener,page,page,form)
    # Detect Set Active only via button/form offered in authenticated official UI.
    # Unknown AJAX actions are not guessed, and SQLite is NEVER edited directly.
    say("SET_ACTIVE_ACTION","NOT_PROVEN")
    say("MYSQL_8_4_EXTERNAL_SUPPORT","NOT_PROVEN")
    return 3


if __name__=="__main__":
    try:
        exit_code=run()
    except Exception as ex:
        code=str(ex)
        if not re.fullmatch(r"[A-Z0-9_]+",code):
            code="P07_D05_CP_UI_NOT_PROVEN"
        say("BLOCK_REASON",code)
        exit_code=3
    raise SystemExit(exit_code)
