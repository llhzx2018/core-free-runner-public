<?php
global $wpdb;
$state=[];
foreach(['vf_theme_seo','vf_m3u8_settings','vf_m3u8_ui_system','vf_m3u8_skin_seasonal','vf_tool_m3u8_seo_browser_acceptance'] as $key) { $state[$key]=get_option($key); }
foreach(['terms','term_taxonomy','term_relationships'] as $key) {
    $table=$wpdb->$key;
    $order=$key==='term_relationships'?'object_id,term_taxonomy_id':($key==='terms'?'term_id':'term_taxonomy_id');
    $state[$key]=$wpdb->get_results("SELECT * FROM {$table} ORDER BY {$order}",ARRAY_A);
}
$state['review']=$wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name LIKE 'vf_theme_frontend_review_%' ORDER BY option_name",ARRAY_A);
$out=[];foreach($state as $key=>$value)$out[$key]=hash('sha256',wp_json_encode($value));
echo wp_json_encode($out);
