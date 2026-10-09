<?php
function gate($x,$msg){if(is_wp_error($x)){throw new Exception($msg.': '.$x->get_error_code());}if(!$x){throw new Exception($msg);}return $x;}
$phase=getenv('VF_PHASE');$root=WP_PLUGIN_DIR.'/vf-tool-m3u8';$plugin='vf-tool-m3u8/vf-tool-m3u8.php';
require_once ABSPATH.'wp-admin/includes/plugin.php';wp_set_current_user(1);
function foreign_snapshot(){
 global $wpdb;
 $tables=VF_M3U8_Update_State_V1::table_map();
 $outside=[];
 $outside['settings']=hash('sha256',serialize([get_option('vf_ops_preservation_sentinel'),get_option('vf_private_update_credential_v1'),get_option('vf_rank_meta_fixture'),get_option('vf_translation_fixture'),get_theme_mod('vf_v8_preservation_sentinel'),get_option('vf_runner_foreign_sentinel')]));
 $outside['posts']=hash('sha256',serialize($wpdb->get_results("SELECT ID,post_type,post_status,post_title,post_name,post_content FROM {$wpdb->posts} ORDER BY ID",ARRAY_A)));
 $outside['cron']=hash('sha256',serialize(get_option('cron')));
 $outside['foreign_capabilities']=hash('sha256',serialize($wpdb->get_results("SELECT * FROM ".$tables['capabilities']." WHERE provider_key <> 'vf.m3u8' ORDER BY id",ARRAY_A)));
 $mods=get_option('theme_mods_vf-tools-theme');$outside['theme_mods']=hash('sha256',serialize($mods));
 return $outside;
}
if($phase==='seed'){
 update_option('vf_m3u8_preservation_sentinel',['value'=>'keep-existing','nested'=>['mode'=>'user']],false);
 update_option('vf_runner_foreign_sentinel',['value'=>'keep-outside'],false);
 update_option('vf_private_update_credential_v1','runner-private-token',false);
 if(!wp_next_scheduled('vf_runner_foreign_cron')){wp_schedule_event(time()+86400,'daily','vf_runner_foreign_cron');}
 $state=gate(VF_M3U8_Update_State_V1::snapshot(),'owned baseline');
 gate(count($state['tables'])===14,'14 real schema tables');
 gate(VF_M3U8_Runtime_Authority_V1::verify(getenv('SOURCE_VERSION'),$root),'baseline runtime');
 update_option('vf_runner_owned_before',$state,false);update_option('vf_runner_foreign_before',foreign_snapshot(),false);
 echo wp_json_encode(['status'=>'PASS','version'=>VF_TOOL_M3U8_VERSION,'state'=>$state,'foreign'=>foreign_snapshot()]);return;
}
if($phase==='negative'){
 VF_M3U8_Update_Source_V1::clear_cache();update_option('vf_runner_corrupt_asset',true,false);
 $c=new VF_M3U8_Update_Client_V1(getenv('SOURCE_VERSION'));
 $r=$c->pre_download(false,'https://api.github.com/repos/llhzx2018/vf-tools-m3u8/releases/assets/590059',null,['type'=>'plugin','plugin'=>$plugin]);
 delete_option('vf_runner_corrupt_asset');
 gate(is_wp_error($r)&&$r->get_error_code()==='vf_m3u8_update_asset_sha256_mismatch','real corrupt asset guard');
 gate(VF_M3U8_Runtime_Authority_V1::verify(getenv('SOURCE_VERSION'),$root),'negative runtime unchanged');
 echo wp_json_encode(['status'=>'PASS','corrupt_asset_error'=>$r->get_error_code()]);return;
}
if($phase==='upgrade'||$phase==='reapply'){
 if($phase==='reapply'){
  $state=VF_M3U8_Update_State_V1::snapshot();$payload=VF_M3U8_Update_State_V1::capture_payload();$hashes=[];foreach($payload['options'] as $k=>$v)$hashes[$k]=hash('sha256',serialize($v));file_put_contents('/tmp/reapply-options.json',wp_json_encode($hashes));
  $baseline=get_option('vf_runner_owned_before');file_put_contents('/tmp/reapply-before.json',wp_json_encode(['state'=>$state,'options_hashes'=>$hashes,'equivalent_original'=>VF_M3U8_Update_State_V1::equivalent($baseline,$state)]));
 }

 VF_M3U8_Update_Source_V1::clear_cache();delete_site_transient('update_plugins');wp_update_plugins();
 $t=get_site_transient('update_plugins');gate(($t->response[$plugin]->new_version??'')===getenv('CANDIDATE_VERSION'),'native update discovery');
 require_once ABSPATH.'wp-admin/includes/class-wp-upgrader.php';
 $u=new Plugin_Upgrader(new Automatic_Upgrader_Skin());$r=$u->upgrade($plugin);
 gate(!is_wp_error($r)&&($r===true||is_array($r)),'native plugin upgrade');
 echo wp_json_encode(['status'=>'PASS','phase'=>$phase,'native'=>'Plugin_Upgrader::upgrade','trace'=>get_option('vf_runner_api_trace')]);return;
}
if($phase==='restore'){
 gate(VF_M3U8_Update_Recovery_V1::restore(),'real source and state recovery');
 echo wp_json_encode(['status'=>'PASS','native'=>'VF_M3U8_Update_Recovery_V1::restore']);return;
}
$expected=$phase==='rollback'?getenv('SOURCE_VERSION'):getenv('CANDIDATE_VERSION');
gate(VF_TOOL_M3U8_VERSION===$expected,'reload version');gate(is_plugin_active($plugin),'active after upgrade/recovery');
$state=gate(VF_M3U8_Update_State_V1::snapshot(),'state after');$before=get_option('vf_runner_owned_before');
if($phase==='candidate'){ $p=VF_M3U8_Update_State_V1::capture_payload();$h=[];foreach($p['options'] as $k=>$v)$h[$k]=hash('sha256',serialize($v));file_put_contents('/tmp/candidate-options.json',wp_json_encode($h)); }
if($phase==='reapply-readback'){ $p=VF_M3U8_Update_State_V1::capture_payload();$h=[];foreach($p['options'] as $k=>$v)$h[$k]=hash('sha256',serialize($v));file_put_contents('/tmp/reapply-after.json',wp_json_encode(['state'=>$state,'options_hashes'=>$h])); }
if(!VF_M3U8_Update_State_V1::equivalent($before,$state)){echo wp_json_encode(['status'=>'FAIL','phase'=>$phase,'before'=>$before,'after'=>$state,'production'=>'NOT_EXECUTED']);throw new Exception('owned state unchanged');}
gate(get_option('vf_runner_foreign_before')===foreign_snapshot(),'foreign state and cron unchanged');
gate(VF_M3U8_Runtime_Authority_V1::verify($expected,$root),'installed exact runtime');
$runtime=VF_M3U8_Runtime_Authority_V1::stored();
echo wp_json_encode(['status'=>'PASS','phase'=>$phase,'version'=>$expected,'state'=>$state,'runtime'=>$runtime,'foreign'=>foreign_snapshot(),'active'=>true,'production'=>'NOT_EXECUTED']);


