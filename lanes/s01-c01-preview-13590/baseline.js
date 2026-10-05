'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright'),{cli,load,url,login,sample}=require('./common');
(async()=>{
 const result=JSON.parse(cli(load+'$r=vf_theme_preview_workbench_create_job(["mode"=>"quick","revision"=>vf_theme_preview_revision()],1);$id=$r["job"]["runId"];$lock=vf_theme_acceptance_state_acquire_step($id,1);$p=vf_theme_preview_workbench_control($id,"pause",1,0);vf_theme_acceptance_state_release_step($id,$lock["token"]);vf_theme_preview_workbench_control($id,"stop",1,$p["job"]["controlEpoch"]);echo wp_json_encode(["control_while_batch_locked"=>$p["ok"]]);'));
 assert.equal(result.control_while_batch_locked,true,'baseline must reproduce lock bypass');
 const b=await chromium.launch(),c=await b.newContext({viewport:{width:1440,height:1000}}),p=await c.newPage();await login(p);await sample(p);await sample(p);const samples=[];for(let i=0;i<5;i++)samples.push(await sample(p));
 fs.writeFileSync('proof/baseline.json',JSON.stringify({status:'REPRODUCED',source_version:process.env.SOURCE_VERSION,control_bypasses_batch_lock:true,performance:{dataset:'same synthetic WordPress preview catalogue',warmups:2,samples}},null,2));await p.screenshot({path:'proof/preview-baseline-1440.png',fullPage:true});await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
