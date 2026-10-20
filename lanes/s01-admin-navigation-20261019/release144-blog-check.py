import json,urllib.request,concurrent.futures,re,html
from pathlib import Path
rows=json.loads(Path('control/lanes/s01-admin-navigation-20261019/release144-articles.json').read_text())
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'S01-Authorized-Public-Verification/1.0'}),timeout=45) as r:
  assert r.status==200
  return r.geturl(),r.read().decode()
def verify(row):
 final,text=get(row['link']);title=html.unescape(row['title']['raw'])
 assert final.rstrip('/')==row['link'].rstrip('/'),final
 headings=re.findall(r'<h1\b[^>]*>(.*?)</h1>',text,re.S)
 assert any(html.unescape(re.sub('<[^>]+>','',h)).strip()==title for h in headings),row['id']
 assert 'section-1' in text and 'section-4' in text,row['id']
 canon=re.findall(r'<link\b[^>]*rel=["\']canonical["\'][^>]*>',text,re.I)
 assert len(canon)==1 and row['link'] in canon[0],canon
 partner=next(x for x in rows if x['id']==row['translations']['zh' if row['lang']=='en' else 'en'])
 assert partner['link'] in text,'translation link missing'
 assert not re.search(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*noindex',text,re.I),'unexpected noindex'
 return {'id':row['id'],'language':row['lang'],'url':final,'title':title,'http':200,'heading':'PASS','body':'PASS','canonical':'PASS','translation_link':'PASS'}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(verify,rows))
lists={}
for lang,path in [('en','/blog/'),('zh','/zh/blog/')]:
 _,text=get('https://www3.m3u8.one'+path)
 expected=[x for x in rows if x['lang']==lang]
 found=[x['id'] for x in expected if x['link'] in html.unescape(text)]
 assert len(found)==7,(lang,found)
 lists[lang]=found
Path('proof/blog-publication-readback.json').write_text(json.dumps({'status':'PASS','posts':results,'lists':lists,'translation_pairs':7,'scope':'Public read-only checks; authored content published separately through authorized native REST'},ensure_ascii=False,indent=2))
print('BLOG_PUBLIC_READBACK_14_ARTICLES_7_PAIRS_TWO_LISTS=PASS')
