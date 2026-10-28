#!/usr/bin/env python3
"""One-time bounded public stream metadata + browser-CORS feasibility probe.
No rebroadcast, protected audio extraction, arbitrary-user URL input or saved
stream bytes. Runs entirely on ephemeral public Runner, emits JSON metadata only.
"""
import json, re, ssl, socket, ipaddress, urllib.request, urllib.parse, urllib.error
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone

MIRRORS=("https://de1.api.radio-browser.info","https://nl1.api.radio-browser.info",
         "https://at1.api.radio-browser.info")
CASES=(
 ("RTHK Radio 1","RTHK Radio 1"),
 ("RTHK Radio 3","RTHK Radio 3"),
 ("AsiaFM Cantonese","AsiaFM"),
 ("RTHK Radio 2","香港电台第二台"),
 ("Good Friend Radio","良友"),
)
CTX=ssl.create_default_context()
HEADERS={"User-Agent":"VFMusicRadioQualityProbe/1.0 (source metadata; no stream recording)",
 "Accept":"application/json"}
def public_url(raw):
    if not isinstance(raw,str) or len(raw)>2048:return False
    try:
        u=urlparse(raw)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.port:return False
        if u.fragment or u.hostname.endswith(('.local','.internal','.localhost')):return False
        name=u.hostname.lower()
        if not re.fullmatch(r'[a-z0-9.-]+',name) or '.' not in name:return False
        try:
            ip=ipaddress.ip_address(name)
            return ip.is_global
        except ValueError:pass
        # Avoid runner-side request to DNS names resolving into RFC1918/loopback.
        ips=socket.getaddrinfo(name,443,type=socket.SOCK_STREAM)
        return bool(ips) and all(ipaddress.ip_address(x[4][0]).is_global for x in ips)
    except Exception:return False

def fetch_url(url,limit=4096,origin=False,timeout=6):
    if not public_url(url):return {"outcome":"unsafe-url"}
    req=urllib.request.Request(url,headers={**HEADERS,
         **({'Origin':'https://start.kewaro.com','Range':f'bytes=0-{limit-1}','Accept':'*/*'} if origin else {})})
    try:
        with urllib.request.urlopen(req,timeout=timeout,context=CTX) as resp:
            final=resp.geturl()
            if not public_url(final):return {"outcome":"unsafe-redirect"}
            h=resp.headers
            data=resp.read(limit)
            aca=h.get('Access-Control-Allow-Origin','')
            return {"outcome":"http-ok","code":resp.status,
                    "cors":aca in ('*','https://start.kewaro.com'),
                    "acao":aca[:80],"mime":h.get('Content-Type','')[:90],
                    "final_url":final,"bytes_read":len(data),
                    "text":data.decode('utf-8',errors='replace') if origin else data.decode('utf-8')}
    except urllib.error.HTTPError as e:return {"outcome":"HTTP-"+str(e.code)}
    except Exception as e:return {"outcome":"blocked-"+type(e).__name__}

def directory(term):
    for base in MIRRORS:
        url=base+'/json/stations/search?'+urllib.parse.urlencode({
            'name':term,'limit':12,'hidebroken':'true','order':'clickcount','reverse':'true'})
        v=fetch_url(url,limit=75000,timeout=7)
        if v.get('outcome')!='http-ok':continue
        try:
            o=json.loads(v['text'])
            if isinstance(o,list):return o,base
        except Exception:pass
    return [],"all-directory-mirrors-unavailable"

def classify(station):
    result={"name":str(station.get('name',''))[:130],
            "uuid":station.get('stationuuid',''),
            "directory_health":station.get('lastcheckok'),
            "tags":str(station.get('tags',''))[:120],
            "codec":str(station.get('codec',''))[:30],
            "hls":station.get('hls'),"stream_host":None,
            "stream_kind":"none","stream_probe":"not-checked"}
    url=station.get('url_resolved','')
    if not public_url(url):
        result['stream_probe']="no-safe-https-direct-url"
        return result
    result['stream_host']=urlparse(url).hostname
    result['stream_url']=url  # publicly listed direct broadcast URL; read-only playback proof
    kind='HLS' if station.get('hls')==1 or re.search(r'\.m3u8(?:\?|$)',url,re.I) else 'other'
    result['stream_kind']=kind
    v=fetch_url(url,origin=True,limit=4096,timeout=7)
    result["stream_probe"]=v['outcome']
    result['cors']=v.get('cors')
    result['mime']=v.get('mime','')
    if kind=="HLS" and v.get('outcome')=='http-ok':
        lines=v.get('text','').splitlines()
        result['manifest']=bool(lines and lines[0].startswith('#EXTM3U'))
        next_ref=next((x.strip() for x in lines if x.strip() and not x.startswith('#')),None)
        if next_ref:
            segment=urljoin(v.get("final_url",url),next_ref)
            if public_url(segment):
                sv=fetch_url(segment,origin=True,limit=1024,timeout=5)
                result['first_segment']={"probe":sv['outcome'],"cors":sv.get('cors'),
                                         "mime":sv.get('mime','')}
            else:result['first_segment']={"probe":"unsafe-segment-url"}
    return result

report={"time_utc":datetime.now(timezone.utc).isoformat(),"origin":"https://start.kewaro.com",
"note":"GET+Origin+Range only; not proof of browser audio playback or rebroadcast rights",
"results":[]}
for label,term in CASES:
    rows,mirror=directory(term)
    print("RADIO_SEARCH",label,"records",len(rows),"mirror",mirror,flush=True)
    selected=[x for x in rows if str(x.get('name','')).strip()][:3]
    data=[classify(x) for x in selected]
    report["results"].append({"case":label,"term":term,"directory_count":len(rows),
       "checked":data})
    for z in data:
        print("RADIO_PROBE",label,z['name'],z['stream_kind'],
             z['stream_probe'],"CORS",z.get('cors'),"mime",z.get('mime'),
             "segment",z.get('first_segment'),flush=True)
with open("p01-radio-source-evidence.json","w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
print("RADIO_PUBLIC_SOURCE_PROBE_COMPLETE=YES")
