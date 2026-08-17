const base=process.env.P05_BASE_URL??'http://127.0.0.1:3105';
const password=process.env.P05_TEST_ADMIN_PASSWORD??'P05-Browser-Gate-2026!';

const login=await fetch(base+'/api/auth/login',{
  method:'POST',
  headers:{'content-type':'application/json'},
  body:JSON.stringify({username:'admin',password}),
});
if(!login.ok) throw new Error('LOGIN_'+login.status);
const cookie=(login.headers.get('set-cookie')??'').split(';',1)[0];
const lb=await login.json();
const csrf=lb.csrfToken;

async function req(path,method='GET',body){
  const r=await fetch(base+path,{
    method,
    headers:{cookie,'content-type':'application/json','x-csrf-token':csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  const text=await r.text();
  let j={}; try{j=JSON.parse(text)}catch{}
  if(!r.ok) throw new Error(`${method} ${path} ${r.status} ${text.slice(0,240)}`);
  return j;
}

let x=await req('/api/projects','POST',{name:'Owner Review Fixture'});
const projectId=x.project.id;
x=await req('/api/websites','POST',{
  projectId,
  name:'Kewaro Owner Review',
  url:'https://example.test/',
  businessValue:'HIGH',
  language:'zh-CN',
  countryCode:'US',
  siteType:'CONTENT',
});
const websiteId=x.website.id;

x=await req('/api/providers/accounts','POST',{
  provider:'GSC',
  externalAccountId:'owner-review@example.test',
  displayName:'GSC Owner Review',
});
const gscAccount=x.account.id;
x=await req(`/api/providers/accounts/${gscAccount}/discover`,'POST',{kind:'GSC'});
const propertyId=x.properties[0].id;
x=await req('/api/data-sources','POST',{websiteId,propertyId});
const sourceId=x.dataSource.id;
await req(`/api/data-sources/${sourceId}/sync`,'POST',{from:'2026-08-12',to:'2026-08-14'});
await req(`/api/opportunities/rebuild/${websiteId}`,'POST',{});
await req(`/api/alerts/rebuild/${websiteId}`,'POST',{});

await req('/api/audit/single','POST',{
  websiteId,
  url:'https://example.test/seo',
  status:200,
  html:'<html><head><meta name="description" content="SEO page"></head><body><h1>SEO</h1></body></html>',
});
await req('/api/audit/single','POST',{
  websiteId,
  url:'https://example.test/start',
  status:200,
  html:'<html><head><title>Start</title></head><body><h1>Start</h1></body></html>',
});
await req('/api/audit/single','POST',{
  websiteId,
  url:'https://example.test/library',
  status:200,
  html:'<html><head><title>Library</title><meta name="description" content="Library"></head><body>Library content</body></html>',
});
await req('/api/changes','POST',{
  websiteId,
  changeType:'TITLE_CHANGE',
  description:'Owner review fixture title change',
});
await req(`/api/opportunities/rebuild/${websiteId}`,'POST',{});
await req(`/api/alerts/rebuild/${websiteId}`,'POST',{});

console.log('FIXTURE_WEBSITE_ID='+websiteId);
console.log('OWNER_REVIEW_FIXTURE=PASS');
