<?php
// Throwaway fixture only: ensure two distinct language members share the public slug.
global $wpdb;
$ids=$wpdb->get_col($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE post_type=%s AND post_status=%s AND post_name=%s",'page','publish','iptv-manager'));
$pair=[];
foreach($ids as $id){$lang=pll_get_post_language((int)$id);if(in_array($lang,['en','zh'],true)&&!isset($pair[$lang]))$pair[$lang]=(int)$id;}
foreach(['en','zh'] as $lang){
 if(isset($pair[$lang]))continue;
 $id=wp_insert_post(['post_type'=>'page','post_status'=>'draft','post_name'=>'seo-fixture-encryption-'.$lang,'post_title'=>'Fixture Encryption '.$lang,'post_content'=>'[vf_iptv_manager]'],true);
 if(is_wp_error($id))throw new RuntimeException('fixture insert');
 pll_set_post_language($id,$lang);wp_update_post(['ID'=>$id,'post_status'=>'publish']);
 $wpdb->update($wpdb->posts,['post_name'=>'iptv-manager'],['ID'=>$id],['%s'],['%d']);clean_post_cache($id);
 $pair[$lang]=(int)$id;
}
pll_save_post_translations($pair);
foreach($pair as $lang=>$id)update_post_meta($id,'rank_math_description',$lang==='zh'?'Synthetic Chinese encryption description for diagnostic.':'Synthetic English encryption description for diagnostic.');
if(count($pair)!==2||$pair['en']===$pair['zh'])throw new RuntimeException('fixture pair invalid');
$control=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'seo-control-en','post_title'=>'SEO Control','post_content'=>'Control content'],true);
if(is_wp_error($control))throw new RuntimeException('control creation');
pll_set_post_language($control,'en');update_post_meta($control,'rank_math_description','Synthetic ordinary control page description.');
echo wp_json_encode(['pair'=>$pair,'original_count'=>count($ids)]);
