'use strict';
const {execFileSync}=require('child_process');
const cli=php=>execFileSync('docker',['exec','--user','www-data','vf-v8-'+process.env.GITHUB_RUN_ID+'-wp','php','/usr/local/bin/wp','eval',php,'--path=/var/www/html'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
const setSettings=changes=>cli('vf_theme_bootstrap_require_many(["services/renderer-config-service.php"]);$r=vf_tools_theme_renderer_defaults();$r=array_merge($r,json_decode('+JSON.stringify(JSON.stringify(changes))+',true));update_option(vf_tools_theme_renderer_option_key(),$r,false);');
const base='http://127.0.0.1:18880',url=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=render',fixture=base+'/?vf-render-fixture=1';
async function login(page){await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);}
async function sample(page){await page.goto(fixture+'&mode=STANDARD');await page.waitForLoadState('networkidle');return page.evaluate(()=>({duration:performance.getEntriesByType('navigation')[0].duration,requests:performance.getEntriesByType('resource').length,bytes:performance.getEntriesByType('resource').reduce((s,r)=>s+r.transferSize,0),nodes:document.querySelectorAll('*').length,executed:window.SYNTHETIC_RUNTIME_EXECUTED===true,optional:performance.getEntriesByType('resource').filter(r=>r.name.includes('vf-render-fixture.js')).length}));}
module.exports={cli,setSettings,base,url,fixture,login,sample};
