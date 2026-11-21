import { test, expect } from '@playwright/test'

/**
 * P08 v0.1.15 final business navigation / passive safety smoke only.
 * Synthetic test login, disposable localhost SQLite. NEVER Production.
 * Business mutations are covered by source Feature tests with synthetic fixtures.
 */
const base=process.env.P08_TEST_BASE_URL
const safe=process.env.GITHUB_ACTIONS==='true'
 && process.env.P08_ISOLATED_INSTALL_TEST==='YES'
 && base==='http://127.0.0.1:18080'
test.skip(!safe,'Only in registered localhost synthetic Runner')

const tabs=[
  {label:'运营概况',tab:'overview',heading:'运营概况'},
  {label:'落地页',tab:'landing',heading:'落地页'},
  {label:'静态部署',tab:'deploy',heading:'静态部署'},
  {label:'域名',tab:'domains',heading:'域名'},
  {label:'追踪器',tab:'trackers',heading:'追踪器'},
  {label:'广告渠道',tab:'advertising',heading:'广告渠道'},
  {label:'效果监控',tab:'monitoring',heading:'效果监控'},
  {label:'自动化',tab:'automation',heading:'自动化'},
  {label:'系统更新',tab:'updates',heading:'系统更新'},
]
test('Owner authentication, nine same-page areas and 27 responsive navigations without writes',async ({page,request})=>{
  test.setTimeout(150_000)
  const errors:string[]=[]
  const unsafePosts:string[]=[]
  const foreignHosts:string[]=[]
  page.on('pageerror',e=>errors.push(e.message))
  page.on('request',r=>{
    const u=new URL(r.url())
    if(!['127.0.0.1','localhost'].includes(u.hostname))
      foreignHosts.push(u.origin)
    if(r.method()!=='GET' && r.method()!=='HEAD'
      && !['/login'].includes(u.pathname))
      unsafePosts.push(r.method()+' '+u.pathname)
  })
  const anonymous=await request.get('/app?tab=automation',{maxRedirects:0,failOnStatusCode:false})
  expect(anonymous.status()).toBe(302)
  expect(anonymous.headers().location).toContain('/login')
  await page.goto('/login')
  await page.getByLabel('邮箱或管理员账号').fill('owner@isolated.example')
  await page.getByLabel('密码',{exact:true}).fill('Synthetic-SQLite-Owner-12345!')
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await expect(page).toHaveURL(/\/app(?:\?.*)?$/)
  await expect(page.getByRole('heading',{name:'运营概况',exact:true})).toBeVisible()
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:900})
    for(const {label,tab,heading} of tabs){
      await page.locator('.module-nav, .system-nav').getByRole('button',{name:label,exact:true}).click()
      await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible()
      await expect(page).toHaveURL(new RegExp('[?&]tab='+tab+'(?:&|$)'))
      expect(await page.evaluate(()=>document.documentElement.scrollWidth <=window.innerWidth+1),
        width+' document overflow at '+tab).toBe(true)
      expect(await page.evaluate(()=>document.body.scrollWidth<=window.innerWidth+1),
        width+' body overflow at '+tab).toBe(true)
      expect(await page.locator('main.work-main').count()).toBe(1)
      // The same-page navigation must survive a genuine server reload on
      // one representative sensitive module for each viewport.
      if(tab==='monitoring'){
        await page.reload()
        await expect(page.getByRole('heading',{name:'效果监控',exact:true})).toBeVisible()
      }
    }
    console.log('P08_V015_BUSINESS_NAV_'+width+'_9_TABS=PASS')
  }
  expect(unsafePosts,'No business HTTP writes from passive navigation').toEqual([])
  expect(foreignHosts,'No provider calls from passive workspace pages').toEqual([])
  expect(errors,'No uncaught browser JavaScript exceptions').toEqual([])
  console.log('P08_V015_BUSINESS_NAV_27_STATES_NO_PASSIVE_PROVIDER_WRITES=PASS')
})
