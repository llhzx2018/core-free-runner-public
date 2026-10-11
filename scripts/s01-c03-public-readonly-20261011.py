#!/usr/bin/env python3
"""One-time, public-only WordPress page route probe. Never mutates remote state."""
import json, re, ssl, urllib.request, urllib.error, html
from html.parser import HTMLParser
from pathlib import Path
HOST='https://www3.m3u8.one'
ROUTES=[
 '/m3u8-playlist-checker/',
 '/zh/m3u8-playlist-checker/',
 '/zh/m3u8-playlist-checker-2/',
 '/wp-json/wp/v2/pages?slug=m3u8-playlist-checker-2&per_page=10&_fields=id,slug,status,link,parent',
 '/wp-json/wp/v2/pages?slug=m3u8-playlist-checker&per_page=20&_fields=id,slug,status,link,parent',
 '/wp-json/wp/v2/pages/4348?_fields=id,slug,status,link,parent,content,modified',
 '/wp-json/wp/v2/pages/1286?_fields=id,slug,lang,translations,link',
 '/wp-json/wp/v2/pages/1124?_fields=id,slug,lang,translations,link',
 '/wp-json/wp/v2/pages/4348?_fields=id,slug,lang,translations,link',
 '/sitemap_index.xml',
 '/page-sitemap.xml',
]
class Doc(HTMLParser):
 def __init__(self):
  super().__init__()
  self.canonical='';self.lang='';self.title='';self.h1='';self.in_title=False;self.in_h1=False;self.robots='';self.alternates=[];self.duplicate_links=0;self.links_to_official=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='html':self.lang=a.get('lang','')
  if tag=='link' and a.get('rel','').lower()=='canonical':self.canonical=a.get('href','')
  if tag=='meta' and a.get('name','').lower()=='robots':self.robots=a.get('content','')
  if tag=='link' and a.get('rel','').lower()=='alternate' and a.get('hreflang'):
   self.alternates.append({'hreflang':a.get('hreflang'),'href':a.get('href','')})
  if tag=='a' and '/zh/m3u8-playlist-checker-2/' in a.get('href',''):self.duplicate_links+=1
  if tag=='a' and '/zh/m3u8-playlist-checker/' in a.get('href',''):self.links_to_official+=1
  if tag=='title':self.in_title=True
  if tag=='h1':self.in_h1=True
 def handle_endtag(self,tag):
  if tag=='title':self.in_title=False
  if tag=='h1':self.in_h1=False
 def handle_data(self,data):
  if self.in_title:self.title+=data
  if self.in_h1:self.h1+=data
def probe(route):
 req=urllib.request.Request(HOST+route,headers={'User-Agent':'Mozilla/5.0 (compatible; VF-S01-ReadOnly-Route-Probe/1.0)','Accept':'text/html,application/json'})
 result={'route':route,'method':'GET','production_write':False}
 try:
  try:
   resp=urllib.request.urlopen(req,timeout=20)
  except urllib.error.HTTPError as e:
   resp=e
  with resp:
   data=resp.read(1024*1024)
   text=data.decode('utf-8','replace')
   result.update(status=resp.getcode(),effective_url=resp.geturl(),bytes_read=len(data),content_type=resp.headers.get('content-type',''))
   if route.startswith('/wp-json/'):
    try:
     body=json.loads(text)
     result['public_page_results']=[{k:x.get(k) for k in ('id','slug','status','link','parent')} for x in body if isinstance(x,dict)] if isinstance(body,list) else []
     if isinstance(body,dict):
      content=body.get('content',{}).get('rendered','') if isinstance(body.get('content'),dict) else ''
      result['page_object']={k:body.get(k) for k in ('id','slug','status','link','parent','modified','lang','translations') if k in body}
      result['content_summary']={'chars':len(content),'playlist_shortcode_or_mount':('vf_m3u8_playlist_checker' in content or 'data-vf-module="playlist-checker"' in content),'contains_media_tool':('playlist-checker' in content)}
    except Exception:result['json_parse']='not_public_json'
   elif route.endswith('.xml'):
    locs=re.findall(r'<loc>\s*([^<]+)\s*</loc>',text,re.I)
    result['sitemap_summary']={'url_count':len(locs),'duplicate_route_count':sum('/zh/m3u8-playlist-checker-2/' in x for x in locs),'official_zh_count':sum('/zh/m3u8-playlist-checker/' in x for x in locs),'sub_sitemaps':[x for x in locs if x.endswith('.xml')][:20]}
   else:
    p=Doc()
    try:p.feed(text)
    except Exception:pass
    result.update(html_lang=p.lang,canonical=p.canonical,robots=p.robots,hreflang=p.alternates,duplicate_nav_links=p.duplicate_links,official_zh_nav_links=p.links_to_official,title=html.unescape(p.title.strip())[:170],h1=html.unescape(p.h1.strip())[:170],playlist_mount_count=text.count('data-vf-module="playlist-checker"'),version_12582_present=('1.25.82' in text))
 except Exception as e:
  result.update(error_class=type(e).__name__,error_message=str(e).split('(')[0][:180])
 return result
rows=[probe(x) for x in ROUTES]
out={'purpose':'S01-C03 public read-only page truth','evidence_type':'PUBLIC_HTTP_GET','production_mutated':False,'pages':rows}
Path('proof').mkdir(exist_ok=True)
Path('proof/s01-checker-route-readonly.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('S01_CHECKER_READONLY_PROBE',json.dumps(out,ensure_ascii=False))
