'use strict';
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:768,height:1000}});
 await page.goto('http://127.0.0.1:18880/m3u8-player/');await page.evaluate(()=>document.fonts.ready);
 const proof=await page.evaluate(()=>{
  const stage=document.querySelector('.vf-tool-runtime-stage'),owner=stage.querySelector('[data-vf-runtime-owner="vf-tool-m3u8"]');
  const shape=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return {tag:n.tagName,classes:n.className,client:n.clientWidth,scroll:n.scrollWidth,rect:{left:r.left,right:r.right,width:r.width},style:Object.fromEntries(['width','minWidth','maxWidth','display','paddingLeft','paddingRight','marginLeft','marginRight','overflowX','position','boxSizing'].map(k=>[k,s[k]]))};};
  const bad=root=>[...root.querySelectorAll('*')].filter(n=>n.getClientRects().length && getComputedStyle(n).visibility!=='hidden' && (n.scrollWidth>n.clientWidth+4 || n.getBoundingClientRect().right>root.getBoundingClientRect().right+4)).slice(0,25).map(shape);
  const original={stage:shape(stage),owner:shape(owner),children:bad(stage)};
  const parent=owner.parentNode,next=owner.nextSibling,width=stage.clientWidth;owner.remove();const emptyStage=shape(stage);parent.insertBefore(owner,next);
  const box=document.createElement('div');box.style.cssText='width:'+width+'px;max-width:none;overflow:visible;';document.body.appendChild(box);box.appendChild(owner);
  const relocated={box:shape(box),owner:shape(owner),children:bad(box)};
  const styles=[...document.querySelectorAll('link[data-vf-runtime-css]')],disabled=styles.map(n=>n.disabled);styles.forEach(n=>n.disabled=true);
  const providerOnly={box:shape(box),owner:shape(owner),children:bad(box)};
  styles.forEach((n,i)=>n.disabled=disabled[i]);parent.insertBefore(owner,next);box.remove();
  return {original,emptyStage,relocated,providerOnly};
 });
 console.log('VF_STAGE_PROOF_BEGIN');console.log(JSON.stringify(proof));console.log('VF_STAGE_PROOF_END');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
