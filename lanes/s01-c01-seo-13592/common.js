'use strict';
const {execFileSync}=require('child_process');
const cli=php=>execFileSync('docker',['exec','--user','www-data','vf-v8-'+process.env.GITHUB_RUN_ID+'-wp','php','/usr/local/bin/wp','eval',php,'--path=/var/www/html'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
const load='vf_theme_bootstrap_require_many(["services/technical-seo-service.php"]);';
const state=()=>JSON.parse(cli(load+'echo wp_json_encode(vf_theme_seo_readback());'));
const setSettings=changes=>cli(load+'$s=vf_theme_seo_readback()["seo"];$s=array_replace($s,json_decode('+JSON.stringify(JSON.stringify(changes))+',true));update_option(vf_theme_seo_option_key(),$s,false);');
const base='http://127.0.0.1:18880',url=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=seo';
async function login(page){await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);}
async function sample(page){await page.goto(url);await page.waitForLoadState('networkidle');return page.evaluate(()=>({duration:performance.getEntriesByType('navigation')[0].duration,requests:performance.getEntriesByType('resource').length,bytes:performance.getEntriesByType('resource').reduce((s,r)=>s+r.transferSize,0),nodes:document.querySelectorAll('*').length}));}
module.exports={cli,load,state,setSettings,base,url,login,sample};
