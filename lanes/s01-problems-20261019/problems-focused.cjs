const {chromium}=require('playwright');
const fs=require('fs');
const expected=JSON.parse(fs.readFileSync('proof/problems-fixture.json','utf8'));
const checks=[];
function check(name,pass,detail){checks.push({name,pass:!!pass,detail});if(!pass)throw new Error(name+': '+JSON.stringify(detail));}
(async()=>{
 const browser=await chromium.launch();
 try{
  for(const lang of ['en','zh']){
   const base='http://127.0.0.1:18880'+(lang==='zh'?'/zh':'')+'/problems/';
   for(const width of [1440,1024]){
    const page=await browser.newPage({viewport:{width,height:1000}});
    const response=await page.goto(base,{waitUntil:'networkidle'});
    const cards=await page.locator('.vf-directory-card--problem').evaluateAll(xs=>xs.map(x=>({title:x.querySelector('h3')?.textContent,category:x.dataset.vfDirectoryCategory,severity:x.dataset.vfProblemSeverity,tool:x.dataset.vfProblemTool,url:x.href})));
    check(`${lang}/${width} source subjects`,response.status()===200&&cards.length===9,cards.length);
    for(const row of expected[lang]){
     const card=cards.find(x=>x.title===row.title);
     check(`${lang}/${width} ${row.title}`,card&&['category','severity','tool','url'].every(k=>card[k]===row[k]),card);
    }
    check(`${lang}/${width} desktop geometry`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    check(`${lang}/${width} single heading`,await page.locator('h1').count()===1);
    check(`${lang}/${width} canonical`,await page.locator('link[rel=canonical]').count()===1);
    await page.screenshot({path:`proof/problems-${lang}-${width}.png`,fullPage:true});
    await page.close();
   }
   const page=await browser.newPage({viewport:{width:1440,height:1000}});
   await page.goto(base,{waitUntil:'networkidle'});
   for(const [category,count] of Object.entries({browser:1,access:1,encryption:1,structure:2,playback:4})){
    await page.locator(`[data-vf-directory-filter-button="${category}"]`).click();
    await page.waitForTimeout(400);
    const visible=page.locator('.vf-directory-card--problem:visible');
    check(`${lang} filter ${category}`,await visible.count()===count,await visible.count());
    check(`${lang} filter subject ${category}`,await visible.evaluateAll((xs,c)=>xs.every(x=>x.dataset.vfDirectoryCategory===c),category));
   }
   await page.goto(base,{waitUntil:'networkidle'});
   const query=lang==='en'?'out of sync':'音画';
   await page.locator('input[name=vf_q]').fill(query);
   await page.locator('input[name=vf_q]').press('Enter');
   await page.waitForLoadState('networkidle');
   check(`${lang} search`,await page.locator('.vf-directory-card--problem:visible').count()===1);
   await page.goto(base+'?vf_q=vf-empty-fixture-9f82',{waitUntil:'networkidle'});
   check(`${lang} empty state`,await page.locator('.vf-directory-card--problem:visible').count()===0&&await page.locator('[data-vf-directory-empty]').isVisible());
   await page.goto(base+'?vf_fixture_help=1',{waitUntil:'networkidle'});
   const first=await page.locator('.vf-directory-card--problem').evaluateAll(xs=>xs.map(x=>x.href));
   const next=page.locator('.page-numbers.next');
   check(`${lang} pagination exists`,first.length===3&&await next.count()===1);
   await next.click();await page.waitForLoadState('networkidle');
   const second=await page.locator('.vf-directory-card--problem').evaluateAll(xs=>xs.map(x=>x.href));
   check(`${lang} pagination advances`,second.length===3&&!second.some(x=>first.includes(x)),{first,second});
   await page.close();
   const nojs=await browser.newPage({javaScriptEnabled:false});
   await nojs.goto(base+'?vf_filter=encryption',{waitUntil:'networkidle'});
   check(`${lang} native server filter`,await nojs.locator('.vf-directory-card--problem').count()===1);
   await nojs.close();
  }
  console.log('PROBLEMS_FOCUSED_PASS',checks.length);
 }finally{fs.writeFileSync('proof/problems-focused.json',JSON.stringify({status:checks.every(x=>x.pass)?'PASS':'FAIL',checks},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
