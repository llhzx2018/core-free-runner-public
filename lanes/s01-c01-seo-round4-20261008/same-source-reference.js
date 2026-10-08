'use strict';
const fs=require('fs'),assert=require('assert/strict'),{chromium}=require('playwright');
const name=process.argv[2],common=require('./'+name+'-common');
(async()=>{
 if(name==='render')common.setSettings({});
 else common.cli(common.load+'update_option("permalink_structure","/%postname%/");$s=vf_theme_seo_defaults();foreach(["seo-front-one","seo-front-two"] as $slug){$post=get_page_by_path($slug);if(!$post)wp_insert_post(["post_type"=>"page","post_status"=>"publish","post_name"=>$slug,"post_title"=>"Synthetic frontend ".$slug,"post_content"=>"Actual isolated WordPress page."]);$s["virtualRoutePolicy"][]=["routeId"=>str_replace("-","_",$slug),"pageFamily"=>"content","pathPattern"=>$slug,"resolver"=>"vf_theme_url_resolver","canonicalPolicy"=>"self","hreflangPolicy"=>"paired","indexability"=>"index_follow","staticPathPolicy"=>"required"];}flush_rewrite_rules(true);update_option(vf_theme_seo_option_key(),$s,false);update_option("vf_seo_baseline_good",$s,false);');
 const b=await chromium.launch(),c=await b.newContext({viewport:{width:1440,height:1000}}),p=await c.newPage();await common.login(p);await common.sample(p);await common.sample(p);const samples=[];for(let i=0;i<5;i++)samples.push(await common.sample(p));
 fs.writeFileSync('proof/baseline.json',JSON.stringify({status:'SAME_SOURCE_REFERENCE_NOT_PREVIOUS_DEFECT',source_version:process.env.TARGET_VERSION,performance:{dataset:'same exact current source and synthetic fixture in one disposable database',samples}},null,2));
 if(name==='seo')common.cli(common.load+'$s=get_option(vf_theme_seo_option_key());$s["searchIndexability"]="legacy-noindex";update_option(vf_theme_seo_option_key(),$s,false);');
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
