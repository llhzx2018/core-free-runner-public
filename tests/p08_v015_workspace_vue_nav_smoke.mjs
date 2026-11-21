import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { join } from 'node:path'
import { writeFileSync, unlinkSync } from 'node:fs'
import assert from 'node:assert/strict'

const html='p08-v015-vue-workspace-preview.html'
const entry='p08-v015-vue-workspace-preview.ts'
const config='p08-v015-vue-workspace-preview.vite.mjs'
const mock = `import { createApp } from 'vue'
import Workspace from './resources/js/pages/Workspace.vue'
const modules=['landing_builder','static_deployment','domains','trackers','advertising','monitoring','automation']
  .map(id=>({id,label:id,status:'DEV_READY'}))
const initial={
  csrf:'synthetic-demo-csrf-no-server',owner:'Synthetic Owner',
  modules,activeTab:'overview',errors:[],status:null,
  pages:[],assets:[],bundles:[],pagesTargets:[],vpsTargets:[],
  trackerConnections:[],adConnections:[],metaConnections:[],
  tiktokConnections:[],popAdsConnections:[],domainRecords:[],
  monitoringOverview:{rows:[],generated_at:'2026-11-21T00:00:00Z',provenance:'owner_local_saved_snapshots_only'},
  automationOverview:{rules:[],history:[],mode:'MANUAL_LOCAL_SUGGESTIONS_ONLY'},
  upgrade:{version:'0.1.15',engine:'mysql',install_status:'INSTALLED_LOCAL_IDENTITY',
    deployment_layout:'VERSIONED',source_short:'369fcb0a',channel:'NOT_CONFIGURED',
    atomic:'OWNER_FUTURE_ATOMIC',can_upgrade:false,
    future_update:{status:'NONE',can_upgrade:false},github_credential:'managed',
    preparation_status:'NONE',job_status:'NONE'}
}
createApp(Workspace,{initial}).mount('#app')
`
const pageHtml=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/resources/css/app.css">
<title>P08 v015 isolated Vue-only panel smoke</title></head>
<body><div id="app"></div><script type="module" src="/${entry}"></script></body></html>`
const vite=`import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwind from '@tailwindcss/vite'
export default defineConfig({
 plugins:[vue(),tailwind()],
 server:{host:'127.0.0.1',port:4179,strictPort:true,hmr:false}
})
`
const files=[[html,pageHtml],[entry,mock],[config,vite]]
let server=null
let browser=null
try{
 for(const [name,content] of files) writeFileSync(join(process.cwd(),name),content)
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--config',config],{
   cwd:process.cwd(),stdio:['ignore','pipe','pipe']
 })
 let stderr=''
 server.stderr.on('data',buf=>{stderr+=String(buf).slice(-1500)})
 const base='http://127.0.0.1:4179/'+html
 let live=false
 for(let i=0;i<100;i++){
   try{const r=await fetch(base);if(r.ok){live=true;break}}catch{}
   await new Promise(resolve=>setTimeout(resolve,180))
 }
 assert.ok(live,'STANDALONE_VITE_NOT_STARTED: '+stderr.slice(-600))
 browser=await chromium.launch({headless:true,args:['--no-sandbox']})
 const sections=[
  ['运营概况','运营概况'],['落地页','落地页'],['静态部署','静态部署'],
  ['域名','域名'],['追踪器','追踪器'],['广告渠道','广告渠道'],
  ['效果监控','效果监控'],['自动化','自动化'],['系统更新','系统更新']
 ]
 for(const width of [390,768,1440]){
   const context=await browser.newContext({viewport:{width,height:900}})
   const page=await context.newPage()
   const errors=[],writes=[],external=[]
   page.on('pageerror',e=>errors.push(e.message))
   page.on('request',r=>{
     const u=new URL(r.url())
     if(u.hostname!=='127.0.0.1')external.push(u.origin)
     if(r.method()!=='GET'&&r.method()!=='HEAD')writes.push(r.method()+' '+u.pathname)
   })
   await page.goto(base)
   for(const [button,heading] of sections){
     await page.getByRole('button',{name:button,exact:true}).first().click()
     await page.getByRole('heading',{name:heading,exact:true}).first().waitFor()
     const scroll=await page.evaluate(()=>({
       doc:document.documentElement.scrollWidth,body:document.body.scrollWidth,inner:window.innerWidth
     }))
     assert.ok(scroll.doc<=scroll.inner+1 && scroll.body<=scroll.inner+1,JSON.stringify({width,button,scroll}))
   }
   assert.deepEqual(errors,[],JSON.stringify({width,errors}))
   assert.deepEqual(writes,[],JSON.stringify({width,writes}))
   assert.deepEqual(external,[],JSON.stringify({width,external}))
   console.log('P08_V015_VUE_ONLY_'+width+'_NINE_MODULES_NO_OVERFLOW_PASSIVE_WRITES=PASS')
   await context.close()
 }
 console.log('P08_V015_VUE_ONLY_THREE_VIEWPORTS_27_STATES=PASS')
}catch(e){console.error('P08_V015_VUE_ONLY_BROWSER_FAIL='+String(e.message||e));process.exitCode=1}
finally{
 if(browser)await browser.close()
 if(server)server.kill('SIGTERM')
 for(const [file] of files){try{unlinkSync(join(process.cwd(),file))}catch{}}
}
