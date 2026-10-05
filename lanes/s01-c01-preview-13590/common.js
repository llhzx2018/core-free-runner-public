'use strict';
const {execFileSync}=require('child_process');
const fs=require('fs');let sequence=0;
const cli=php=>{
 const file='/tmp/vf-preview-'+process.pid+'-'+(++sequence)+'.php',container='vf-v8-'+process.env.GITHUB_RUN_ID+'-wp';
 fs.writeFileSync(file,'<?php\n'+php,{mode:0o600});
 try {
  execFileSync('docker',['cp',file,container+':'+file],{stdio:'pipe'});
  execFileSync('docker',['exec',container,'chown','www-data:www-data',file],{stdio:'pipe'});
  return execFileSync('docker',['exec','--user','www-data',container,'php','/usr/local/bin/wp','eval-file',file,'--path=/var/www/html'],{encoding:'utf8',stdio:['ignore','pipe','pipe'],maxBuffer:8*1024*1024});
 } finally { fs.unlinkSync(file);execFileSync('docker',['exec',container,'rm','-f',file],{stdio:'pipe'}); }
};
const loadOld='vf_theme_bootstrap_require_many(["services/technical-seo-service.php"]);';
const load='wp_set_current_user(1);vf_theme_bootstrap_require_many(require get_template_directory()+"/inc/bootstrap/manifests/admin-tabs/preview.php");'.replace('get_template_directory()+','get_template_directory().');
const state=()=>JSON.parse(cli(load+'$latest=vf_theme_acceptance_state_latest_job();$job=vf_theme_preview_workbench_load_job((string)($latest["runId"]??""));if(!$job){throw new Exception("current job unavailable");}echo wp_json_encode(vf_theme_preview_workbench_public_state($job));'));
const base='http://vf-ui.test:18880',url=base+'/wp-admin/themes.php?page=vf-theme-modules&tab=preview';
async function login(page){await page.goto(base+'/wp-login.php');await page.locator('#user_login').fill('admin');await page.locator('#user_pass').fill('Synthetic-Only-Update-54!');await Promise.all([page.waitForURL(/wp-admin/),page.locator('#wp-submit').click()]);}
async function sample(page){await page.goto(url);await page.waitForLoadState('networkidle');return page.evaluate(()=>({duration:performance.getEntriesByType('navigation')[0].duration,requests:performance.getEntriesByType('resource').length,bytes:performance.getEntriesByType('resource').reduce((s,r)=>s+r.transferSize,0),nodes:document.querySelectorAll('*').length}));}
module.exports={cli,load,state,base,url,login,sample};
