<?php
// Throwaway WordPress only. Use the existing Provider mount transaction.
if(!function_exists('vf_m3u8_save_mount_transaction'))throw new RuntimeException('MOUNT_API_MISSING');
$bindings=[];
foreach(vf_m3u8_mounts_tool_registry() as $tool=>$def){
 $route=trim((string)($def['public_route']??''),'/');if($tool==='segment-list-viewer')$route='m3u8-segment-viewer';$shortcode=(string)($def['shortcode']??'');if(!$route||!$shortcode)throw new RuntimeException('BAD_MOUNT_FIXTURE');
 $pair=[];
 foreach(['en','zh'] as $lang){
  $id=wp_insert_post(['post_type'=>'page','post_status'=>'draft','post_name'=>$route,'post_title'=>($lang==='zh'?'中文 ':'').'M3U8 '.(string)($def['label']??$tool),'post_content'=>'['.$shortcode.']'],true);if(is_wp_error($id))throw new RuntimeException('MOUNT_INSERT_FAILED');pll_set_post_language($id,$lang);$pair[$lang]=(int)$id;
 }
 pll_save_post_translations($pair);
 foreach($pair as $lang=>$id){
  wp_update_post(['ID'=>$id,'post_status'=>'publish','post_name'=>$route]);
  // Polylang Free in this isolated harness cannot share translated slugs.
  // Mirror the already-established Pro same-slug fixture; never Production.
  if(get_post_field('post_name',$id)!==$route){global $wpdb;$wpdb->update($wpdb->posts,['post_name'=>$route],['ID'=>$id],['%s'],['%d']);clean_post_cache($id);}
  if(get_post_field('post_name',$id)!==$route)throw new RuntimeException('MOUNT_SLUG_MISMATCH');
  $bindings[]=['toolId'=>$tool,'language'=>$lang,'pageId'=>$id];
 }
}
$before=vf_m3u8_mounts_data();$result=vf_m3u8_save_mount_transaction($bindings,'shortcode',(int)$before['revision'],1);if(($result['status']??'')!=='PASS'||($result['stages']['verify']??'')!=='PASS')throw new RuntimeException('MOUNT_VERIFY_FAILED:'.wp_json_encode($result['issues']??[]));
echo wp_json_encode(['status'=>'PASS','bindings'=>count(vf_m3u8_mounts_data(true)['bindings']),'production'=>'NOT_EXECUTED']);
