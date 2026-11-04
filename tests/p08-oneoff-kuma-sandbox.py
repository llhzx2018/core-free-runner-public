#!/usr/bin/env python3
"""One-off synthetic Simple Kuma real HTTP test; no production endpoints or credentials."""
from __future__ import annotations
import argparse
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse, parse_qs, urljoin
from urllib.request import build_opener, HTTPSHandler, HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, Request

HOST = "https://kuma.example.test"
class CsrfInputs(HTMLParser):
    token = None
    def handle_starttag(self, tag, attrs):
        if tag == "input":
            data = dict(attrs)
            if data.get("name") == "install_csrf":
                self.token = data.get("value")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class HttpProbe:
    def __init__(self, cert, token=None):
        self.token = token
        self.context = ssl.create_default_context(cafile=str(cert))
        self.cookies = CookieJar()
        self.opener = build_opener(ProxyHandler({}), HTTPSHandler(context=self.context),
                                  HTTPCookieProcessor(self.cookies))
        self.no_redirect = build_opener(ProxyHandler({}), HTTPSHandler(context=self.context),
                                       HTTPCookieProcessor(self.cookies), NoRedirect())
    def send(self, path, data=None, auth=False, follow=True):
        url = path if path.startswith("https://") else HOST + path
        headers = {"Accept": "application/json" if auth else "text/html"}
        if auth:
            assert self.token and self.token.startswith("kuma_")
            headers["Authorization"] = "Bearer " + self.token
        payload = None if data is None else (json.dumps(data).encode() if auth else urlencode(data).encode())
        if payload is not None:
            headers["Content-Type"] = "application/json" if auth else "application/x-www-form-urlencoded"
        req = Request(url, data=payload, headers=headers, method="POST" if payload is not None else "GET")
        try:
            res = (self.opener if follow else self.no_redirect).open(req, timeout=25)
            with res:
                return res.status, res.headers, res.read(256*1024)
        except HTTPError as e:
            return e.code, e.headers, e.read(256*1024)
    def step(self, name, form=None):
        path = "/install.php?step=" + name
        status, headers, data = self.send(path)
        assert status == 200, f"KUMA_INSTALL_GET_{name}_HTTP_{status}"
        parser = CsrfInputs()
        parser.feed(data.decode("utf8", "replace"))
        assert parser.token and len(parser.token) == 64, f"KUMA_INSTALL_CSRF_{name}"
        status, headers, response = self.send(path, {"install_csrf":parser.token, **(form or {})})
        assert status == 200, f"KUMA_INSTALL_POST_{name}_HTTP_{status}"
        assert b"Invalid or expired form submission" not in response, f"KUMA_INSTALL_CSRF_REJECT_{name}"
        print("KUMA_INSTALL_STEP_SUBMITTED=" + name)

def install(cert):
    h = HttpProbe(cert)
    h.step("requirements")
    h.step("database", {
        "db_host":"mysql", "db_name":"simplekuma", "db_user":"kuma", "db_password":"kuma",
        "base_url":HOST, "base_url_same_host_ack":"1", "public_path_suffix":"",
        "admin_username":"synthetic_owner", "admin_email":"owner@kuma.example.test",
        "admin_password":"SyntheticOnlyOwnerNeverProduction123!",
        "admin_password_confirm":"SyntheticOnlyOwnerNeverProduction123!",
    })
    h.step("config")
    h.step("migrations")
    h.step("admin")
    status, headers, body = h.send("/install.php?step=complete")
    assert status == 200, f"KUMA_INSTALL_COMPLETE_HTTP_{status}"
    status, headers, body = h.send("/api/v1/health")
    if status != 200:
        # Status-only probes; never expose credentials, SQL, or raw web data.
        for label, path in [
            ("rewritten", "/api/v1/health"),
            ("direct_index", "/api/v1/index.php/health"),
            ("index_only", "/api/v1/index.php"),
            ("openapi", "/api/v1/openapi.json"),
        ]:
            code, response_headers, payload = h.send(path)
            print("P08_R31_KUMA_API_ROUTE_PROBE=" + label + ":" + str(code), flush=True)
        raise AssertionError("KUMA_REAL_HEALTH_HTTP_" + str(status))
    try: doc=json.loads(body)
    except ValueError: raise AssertionError("KUMA_REAL_HEALTH_BAD_JSON")
    assert isinstance(doc.get("data"),dict) and doc["data"].get("status")=="ok", "KUMA_REAL_HEALTH_SCHEMA_DRIFT"
    print("KUMA_REAL_UPSTREAM_INSTALL_AND_HEALTH_PASS")

def api(cert, key):
    h=HttpProbe(cert,key)
    # Public-safe triage only: the same disposable key via TLS proxy vs the
    # local Apache API entrypoint. Emit status codes, never headers/credentials.
    for label, url in [
        ("direct_apache", "http://127.0.0.1:8080/api/v1/index.php/catalog"),
        ("canonical_tls", HOST + "/api/v1/catalog"),
    ]:
        req = Request(url, headers={"Authorization":"Bearer "+key,
                                   "Accept":"application/json"})
        try:
            with build_opener(ProxyHandler({}), HTTPSHandler(context=h.context)).open(req, timeout=15) as response:
                status = response.status
        except HTTPError as e:
            status = e.code
        print("P08_R31_KUMA_BEARER_TRANSPORT_PROBE=" + label + ":" + str(status), flush=True)
    def call(path,body=None):
        status,headers,raw=h.send("/api/v1"+path,body,auth=True)
        try: obj=json.loads(raw)
        except ValueError: raise AssertionError(f"KUMA_API_JSON_INVALID_{status}")
        if status not in (200,201):
            error=obj.get("error") or {}
            raise AssertionError(f"KUMA_API_HTTP_{status}_CODE_{error.get('code','UNKNOWN')}")
        assert isinstance(obj.get("data"),(dict,list)), f"KUMA_API_ENVELOPE_INVALID_{status}"
        return obj["data"]
    catalog=call("/catalog")
    sources=catalog.get("traffic_sources") if isinstance(catalog,dict) else None
    assert isinstance(sources,list) and sources and int(sources[0]["id"])>0, "KUMA_CATALOG_NO_TRAFFIC_SOURCE"
    source_id=int(sources[0]["id"])
    net=call("/networks",{"name":"P08 Synthetic Network"})
    network_id=int(net["id"])
    offer=call("/offers",{
        "name":"P08 Synthetic CPA Offer", "url":"https://offers.example.test/out?subid={click_id}",
        "payout_type":"CPA", "payout_value":1.75, "network_id":network_id,
    })
    offer_id=int(offer["id"])
    lp=call("/landing-pages",{"name":"P08 Synthetic Lander",
                              "url":"https://lander.example.test/landing/r15"})
    landing_id=int(lp["id"])
    camp=call("/campaigns",{"name":"P08 Synthetic LP Campaign","flow_type":"LP",
           "traffic_source_id":source_id, "status":"active",
           "rotation":{"landing_pages":[{"type":"landing_page","id":landing_id,"weight":100,"enabled":True}],
                       "offers":[{"type":"offer","id":offer_id,"weight":100,"enabled":True}]}})
    campaign_id=int(camp["id"])
    read=call(f"/campaigns/{campaign_id}")
    assert read["id"]==campaign_id and read["status"]=="active" and read["flow_type"]=="LP", "KUMA_CAMPAIGN_READBACK_MISMATCH"
    assert call(f"/offers/{offer_id}")["id"]==offer_id
    assert call(f"/landing-pages/{landing_id}")["id"]==landing_id
    tracking=call(f"/campaigns/{campaign_id}/tracking-link")
    url=tracking.get("url")
    assert isinstance(url,str) and urlparse(url).hostname=="kuma.example.test", "KUMA_TRACKING_LINK_INVALID"
    stats=call(f"/stats/campaigns/{campaign_id}")
    assert isinstance(stats,dict), "KUMA_STATS_NOT_OBJECT"
    print("KUMA_REAL_CATALOG_CREATE_BIND_READBACK_STATS_PASS")
    # Traffic is synthetic and local. Disable redirects before visiting third-party Offer URLs.
    path=url
    path=re.sub(r"\\{[A-Za-z_0-9]+\\}", "synthetic", path)
    status,headers,data=h.send(path,follow=False)
    location=headers.get("Location","")
    assert status in (301,302,303,307,308) and location, f"KUMA_REAL_CLICK_NOT_REDIRECT_{status}"
    u=urlparse(urljoin(HOST,location))
    click_id=(parse_qs(u.query).get("click_id") or [None])[0]
    assert u.hostname=="lander.example.test" and click_id and re.fullmatch(r"[0-9a-fA-F-]{36}",click_id), "KUMA_REAL_LP_CLICK_ID_NOT_RETURNED"
    print("KUMA_REAL_TRACKING_CLICK_ID_TO_LP_PASS")
    # Real tracker LP exit; never follow any external network/offer URL.
    status,headers,data=h.send("/click.php?click_id="+click_id,follow=False)
    target=headers.get("Location","")
    assert status in (301,302,303,307,308) and target.startswith("https://offers.example.test/"), f"KUMA_REAL_OFFER_EXIT_NOT_REDIRECT_{status}"
    print("KUMA_REAL_LP_EXIT_TO_SYNTHETIC_OFFER_PASS")
    status,headers,data=h.send("/postback.php?"+urlencode({"click_id":click_id,"txid":"p08-synthetic-tx-0001","payout":"1.75","status":"approved"}),follow=False)
    assert status in (200,204), f"KUMA_TEST_POSTBACK_HTTP_{status}"
    conversions=call("/conversions?campaign_id="+str(campaign_id))
    assert isinstance(conversions,list) and any(str(x.get("click_id"))==click_id for x in conversions), "KUMA_TEST_POSTBACK_CONVERSION_READBACK_MISSING"
    print("KUMA_REAL_TEST_POSTBACK_AND_CONVERSION_READBACK_PASS")
    print(f"KUMA_SANDBOX_IDS=campaign:{campaign_id},offer:{offer_id},landing:{landing_id}")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("install","api"))
    p.add_argument("--cert",required=True,type=Path)
    p.add_argument("--key-file",type=Path)
    a=p.parse_args()
    if a.mode=="install": install(a.cert)
    else:
        assert a.key_file and a.key_file.is_file()
        api(a.cert,a.key_file.read_text().strip())
