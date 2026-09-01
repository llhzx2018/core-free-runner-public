const {chromium}=require('playwright-core');
const fs=require('fs'),path=require('path');
const base=`http://127.0.0.1:${process.env.PORT}/`;
const E=process.env.EVID, pass=process.env.ADMIN_PASS, source=process.env.SOURCE;
const canonical=[
  ['links','links-admin.php'],['health','health.php'],['duplicates','duplicates.php'],['transfer','transfer.php'],
  ['browser','browser-helper.php'],['safety','data-safety.php'],['settings','settings.php'],['rss','workbench.php?route=rss'],
  ['system','system.php'],['update','update.php']
];
const low=[
  ['affiliate','affiliate.php'],['tags','tags.php'],['plugins','plugins.php'],['governance','governance.php'],
  ['jobs','jobs.php'],['icons','icons.php'],['security','security.php'],['diagnose','diagnose.php'],
  ['systemInfo','system-info.php'],['systemBaseline','system-baseline.php'],['surfaceManager','surface-manager.php'],['manage','manage.php']
];
const tech=['插件','治理','任务','安全','诊断','基线','Affiliate','推广','标签','图标','作业','Schema','Migration','runtime','manifest'];
const clean=s=>(s||'').replace(/\s+/g,' ').trim();
const rel=u=>{try{let x=new URL(u);return x.pathname.replace(/^\//,'')+(x.search||'')+(x.hash||'')}catch{return u}};
const vis=async(p,sel)=>p.locator(sel).evaluateAll(es=>es.filter(e=>{let s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0}).length).catch(()=>0);
async function inspect(p,label,route,width){
  let resp=null,err='';
  try{resp=await p.goto(base+route,{waitUntil:'domcontentloaded',timeout:15000});await p.waitForTimeout(180);}catch(e){err=String(e.message||e)}
  const data=await p.evaluate(({tech})=>{
    const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
    const txt=(document.body?.innerText||'').replace(/\s+/g,' ').trim();
    const rectOverflow=document.documentElement.scrollWidth-document.documentElement.clientWidth;
    const hrefs=qa('a[href]').map(a=>({href:a.getAttribute('href')||'',text:(a.innerText||'').replace(/\s+/g,' ').trim(),display:getComputedStyle(a).display,visibility:getComputedStyle(a).visibility,r:a.getBoundingClientRect()}));
    const visibleHrefs=hrefs.filter(x=>x.display!=='none'&&x.visibility!=='hidden'&&x.r.width>0&&x.r.height>0).map(({href,text})=>({href,text}));
    const terms={};for(const t of tech){terms[t]=(txt.match(new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'))||[]).length}
    return {
      finalUrl:location.href,
      title:document.title,
      h1:(q('h1')?.innerText||'').replace(/\s+/g,' ').trim(),
      description:(q('.vf-admin-titleblock p')?.innerText||'').replace(/\s+/g,' ').trim(),
      shell:document.body?.dataset?.vfAdminShell||'',
      group:document.body?.dataset?.vfGroup||'',
      pageKey:document.body?.dataset?.vfPage||'',
      railTop:qa('.vf-rail-item').map(x=>(x.innerText||'').replace(/\s+/g,' ').trim()),
      railSub:qa('.vf-rail-subitem').map(x=>(x.innerText||'').replace(/\s+/g,' ').trim()),
      activeTop:qa('.vf-rail-item.active').map(x=>(x.innerText||'').replace(/\s+/g,' ').trim()),
      visibleHrefs,
      allHrefs:hrefs.map(({href,text})=>({href,text})),
      controls:{anchors:qa('a').length,buttons:qa('button').length,forms:qa('form').length,inputs:qa('input').length,selects:qa('select').length,textareas:qa('textarea').length},
      overflowX:rectOverflow,
      bodyLength:txt.length,
      techTerms:terms,
      bodySample:txt.slice(0,1000)
    };
  },{tech}).catch(()=>({finalUrl:p.url(),title:'',h1:'',description:'',shell:'',group:'',pageKey:'',railTop:[],railSub:[],activeTop:[],visibleHrefs:[],allHrefs:[],controls:{},overflowX:null,bodyLength:0,techTerms:{},bodySample:''}));
  data.requested=route;data.label=label;data.width=width;data.status=resp?resp.status():null;data.navigationError=err;data.finalRoute=rel(data.finalUrl);
  return data;
}
(async()=>{
  fs.mkdirSync(path.join(E,'screens'),{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME,args:['--no-sandbox']});
  const out={source,widths:{},canonicalLinkGraph:{},lowFrequencyLinkCounts:{}};
  for(const width of [390,1440]){
    const ctx=await browser.newContext({viewport:{width,height:width===390?844:900}});
    const login=await ctx.request.post(base+'api.php?action=login',{data:{password:pass}});
    if(!login.ok()||!(await login.json()).ok)throw Error(`login failed ${width}`);
    const p=await ctx.newPage();out.widths[width]={canonical:{},low:{}};
    const canonLinks=[];
    for(const [label,route] of canonical){
      const d=await inspect(p,label,route,width);out.widths[width].canonical[label]=d;
      canonLinks.push(...d.visibleHrefs.map(x=>({...x,from:route})));
      await p.screenshot({path:path.join(E,'screens',`${width}-canonical-${label}.png`),fullPage:false});
    }
    for(const [label,route] of low){
      const d=await inspect(p,label,route,width);out.widths[width].low[label]=d;
      await p.screenshot({path:path.join(E,'screens',`${width}-low-${label}.png`),fullPage:false});
    }
    if(width===1440){
      out.canonicalLinkGraph=canonLinks;
      for(const [label,route] of low){
        const target=route.split('?')[0];
        out.lowFrequencyLinkCounts[label]={route,visibleCanonicalLinks:canonLinks.filter(x=>{try{return new URL(x.href,base).pathname.replace(/^\//,'')===target}catch{return false}})};
      }
    }
    await ctx.close();
  }
  fs.writeFileSync(path.join(E,'browser.json'),JSON.stringify(out,null,2));
  await browser.close();
  console.log('P01_ADMIN_IA_BROWSER_AUDIT=PASS');
})().catch(e=>{console.error(e);process.exit(1)});
