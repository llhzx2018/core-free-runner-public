import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const root = process.cwd()
const previewHtml = 'p08-owner-ux-preview.html'
const previewTs = 'p08-owner-ux-preview.ts'
const config = 'p08-owner-ux-preview.vite.mjs'
const created = [previewHtml, previewTs, config]
const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Isolated P08 Owner UX</title><link rel="stylesheet" href="/resources/css/app.css"></head><body><main class="updates-unified-panel surface" style="max-width:1100px;margin:24px auto"><div id="app"></div></main><script type="module" src="/${previewTs}"></script></body></html>`
const app = `import { createApp } from 'vue'
import Panel from './resources/js/modules/updates/FutureOwnerUpdatePanel.vue'
const search = new URLSearchParams(window.location.search)
const state = search.get('state') ?? 'NONE'
const target = '0.1.14'
const readiness = {
  version: target,
  engine: 'mysql',
  install_status: 'INSTALLED_LOCAL_IDENTITY',
  deployment_layout: 'VERSIONED',
  source_short: 'snapshot-only',
  channel: 'NOT_CONFIGURED',
  atomic: 'OWNER_FUTURE_ATOMIC',
  can_upgrade: false,
  future_update: {
    status: state,
    can_upgrade: false,
    ...(state === 'NONE' ? {} : {
      preparation_id: 'a'.repeat(32),
      target_version: target
    })
  }
}
createApp(Panel, { readiness, csrf: 'only-test-token', tokenReady: true }).mount('#app')
`
const vite = `import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwind from '@tailwindcss/vite'
export default defineConfig({
  plugins: [vue(),tailwind()],
  server: {host:'127.0.0.1',port:4178,strictPort:true,hmr:false},
  preview: {port:4178}
})
`
let server = null
let browser = null
const base = 'http://127.0.0.1:4178/' + previewHtml
const waitForServer = async () => {
  for (let i=0;i<100;i++) {
    try {
      const r=await fetch(base)
      if(r.ok) return
    } catch {}
    await new Promise(resolve=>setTimeout(resolve,200))
  }
  throw new Error('UX_VITE_SERVER_START_TIMEOUT')
}
const scenarios=[
 {name:'idle',state:'NONE'},
 {name:'current',state:'NONE'},
 {name:'available',state:'NONE'},
 {name:'history',state:'SUCCEEDED'},
 {name:'status_read_retry',state:'SUCCEEDED',first503:true},
 {name:'running',state:'RUNNING_PREPARE'},
 {name:'recovery',state:'NEEDS_RECOVERY'},
]
try {
 for(const [file,text] of [[previewHtml,html],[previewTs,app],[config,vite]])fs.writeFileSync(path.join(root,file),text)
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--config',config],{cwd:root,stdio:['ignore','pipe','pipe'],env:{...process.env,APP_URL:'http://127.0.0.1'}})
 let serverError=''
 server.stderr.on('data',d=>{serverError+=String(d).slice(-3000)})
 await waitForServer()
 browser=await chromium.launch({headless:true,args:['--no-sandbox']})
 for(const width of [390,768,1440]){
   for(const scenario of scenarios) {
     const context=await browser.newContext({viewport:{width,height:900}})
     const page=await context.newPage()
     const errors=[]
     const posts=[]
     let statusReads=0
     page.on('pageerror',err=>errors.push(err.message))
     await page.route('**/app/system/update/next/**',async route=>{
       const request=route.request()
       const url=new URL(request.url())
       if(request.method()==='POST')posts.push(url.pathname)
       if(url.pathname.endsWith('/status')){
         statusReads++
         if(scenario.first503 && statusReads===1) {
           await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({status:'STATE_UNAVAILABLE',can_upgrade:false})})
           return
         }
         await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
           status:scenario.state,can_upgrade:false,
           ...(scenario.state==='NONE'?{}:{target_version:'0.1.14',preparation_id:'a'.repeat(32)})
         })})
       } else if(url.pathname.endsWith('/check')){
         await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(
           scenario.name==='current'? {status:'OFFICIAL_VERSION_CURRENT',can_install:false}:
           {status:'OFFICIAL_NEXT_VERIFIED_NOT_STAGED',target_version:'0.1.15',
            target_sha:'b'.repeat(40),can_install:false}
         )})
       }else{
         throw new Error('UNEXPECTED_UPGRADE_ROUTE_'+url.pathname)
       }
     })
     await page.goto(base+'?state='+scenario.state)
     await page.locator('.updates-step-header').waitFor({state:'visible'})
     if(scenario.name==='idle') {
       await page.getByText('准备检查官方更新',{exact:true}).waitFor()
       assert.equal(posts.length,0,'idle POST')
       assert.equal(statusReads,0,'passive status network for NONE')
       assert.equal(await page.getByRole('button',{name:'检查官方更新'}).count(),1)
     }
     if(scenario.name==='current'){
       await page.getByRole('button',{name:'检查官方更新'}).click()
       await page.getByText('当前已是官方最新版',{exact:true}).waitFor()
       assert.equal(await page.getByRole('button',{name:/一键安全升级/}).count(),0)
       assert.deepEqual(posts,['/app/system/update/next/check'])
     }
     if(scenario.name==='available'){
       await page.getByRole('button',{name:'检查官方更新'}).click()
       await page.getByText('发现新版本 0.1.15',{exact:true}).waitFor()
       await page.getByRole('button',{name:'一键安全升级到 0.1.15'}).waitFor()
       assert.deepEqual(posts,['/app/system/update/next/check'])
       assert.equal(await page.locator('.updates-next-action--available').count(),1)
     }
     if(scenario.name==='history'){
       await page.getByRole('button',{name:'检查官方更新'}).waitFor()
       assert.equal(await page.locator('.updates-step-badge').innerText(),'等待检查')
       assert.equal(await page.getByText('升级成功',{exact:true}).count(),0)
       assert.equal(await page.locator('.updates-last-result').isVisible(),false)
       await page.getByText('升级记录、技术详情与故障恢复').click()
       await page.getByText('最近一次升级记录：已完成至 0.1.14。',{exact:false}).waitFor()
       assert.equal(posts.length,0,'history POST')
     }
     if(scenario.name==='status_read_retry'){
       await page.getByText('升级记录暂时无法核实').waitFor()
       await page.getByRole('button',{name:'重试读取任务状态'}).click()
       await page.getByRole('button',{name:'检查官方更新'}).waitFor()
       assert.equal(statusReads,2)
       assert.equal(posts.length,0,'retry POST')
     }
     if(scenario.name==='running') {
       await page.locator('.updates-next-action--running strong').filter({hasText:'正在下载、校验和备份'}).waitFor()
       assert.equal(await page.getByRole('button',{name:'检查官方更新'}).count(),0)
       assert.equal(posts.length,0,'running POST')
     }
     if(scenario.name==='recovery'){
       await page.getByText('需要安全恢复',{exact:true}).waitFor()
       assert.equal(await page.getByRole('button',{name:'检查官方更新'}).count(),0)
       assert.equal(await page.locator('.updates-next-action--danger').count(),1)
       assert.equal(posts.length,0,'recovery POST')
     }
     const horizontal=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1)
     assert.equal(horizontal,false,'horizontal page overflow at '+width+' '+scenario.name)
     assert.deepEqual(errors,[],'JS errors at '+width+' '+scenario.name)
     console.log('P08_UX_BROWSER_'+width+'_'+scenario.name.toUpperCase()+'=PASS')
     await context.close()
   }
 }
 console.log('P08_UX_BROWSER_390_768_1440_ALL_21_SCENARIOS=PASS')
}catch(error){
 console.error('P08_UX_BROWSER_FAIL',error?.message??String(error))
 process.exitCode=1
}finally {
 if(browser)await browser.close()
 if(server){server.kill('SIGTERM')}
 for(const f of created){try{fs.unlinkSync(path.join(root,f))}catch{}}
}
