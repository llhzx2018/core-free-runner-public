<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(require get_template_directory().'/inc/bootstrap/manifests/admin-tabs/recovery.php');
$defaults=vf_theme_recovery_default_stores();
foreach(['brand'=>'vf_theme_brand','tokens'=>'vf_theme_tokens','layout'=>'vf_theme_layout','renderer'=>'vf_tools_theme_renderer','ads'=>'vf_theme_ads','seo'=>'vf_theme_seo'] as $key=>$option) update_option($option,$defaults[$key],false);
update_option('vf_theme_recovery',['retention'=>10,'importMode'=>'strict'],false);
delete_option(vf_theme_revision_store_key());
delete_option(vf_tools_theme_post_restore_preview_key());
delete_option(vf_theme_recovery_last_operation_key());
$s=theme_navigation_readback();$n=$s['navigation'];
foreach(array_keys(vf_theme_navigation_menu_field_map()) as $i=>$field){
    $name='Synthetic '.$field;$existing=wp_get_nav_menu_object($name);$id=$existing?(int)$existing->term_id:wp_create_nav_menu($name);
    if(is_wp_error($id))throw new Exception('synthetic menu seed failed');
    if(!wp_get_nav_menu_items($id))wp_update_nav_menu_item($id,0,['menu-item-title'=>'Synthetic link '.$i,'menu-item-url'=>home_url('/'),'menu-item-status'=>'publish']);
    $n[$field]=$id;
}
$r=theme_navigation_save($n,$s['revision'],1,$s['navigation']);
if(empty($r['ok']))throw new Exception('synthetic navigation seed failed: '.wp_json_encode($r));
update_option('permalink_structure','/%postname%/');
foreach(['integration-page','seo-front-one','seo-front-two'] as $slug)if(!get_page_by_path($slug))wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>$slug,'post_title'=>'Synthetic '.$slug,'post_content'=>'Synthetic ordinary WordPress content for bounded Theme checks.']);
flush_rewrite_rules(true);
foreach(['vf_ops_preservation_sentinel'=>['keep'=>'ops'],'vf_m3u8_preservation_sentinel'=>['keep'=>'provider'],'vf_private_update_credential_v1'=>'runner-private-token','vf_rank_meta_fixture'=>['title'=>'other-owner-keep'],'vf_translation_fixture'=>['en'=>1,'zh'=>2]] as $key=>$value)update_option($key,$value,false);
set_theme_mod('vf_v8_preservation_sentinel','keep-me');
echo wp_json_encode(['status'=>'PASS','environment'=>'SYNTHETIC_DISPOSABLE_WORDPRESS','consumer_ok'=>vf_theme_recovery_runtime_verification()['ok']??false]);

