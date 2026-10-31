<?php
$ids=[]; global $wpdb;
$rows=$wpdb->get_col("SELECT ID FROM $wpdb->posts WHERE post_type='page' AND post_status='publish' AND post_content LIKE '%vf_m3u8_playlist_checker%'");
foreach($rows as $id){$wpdb->update($wpdb->posts,['post_name'=>'m3u8-playlist-checker'],['ID'=>(int)$id],['%s'],['%d']);clean_post_cache((int)$id);$lang=pll_get_post_language((int)$id);if(in_array($lang,['en','zh'],true)){$ids[$lang]=(int)$id;update_post_meta((int)$id,'rank_math_description',$lang==='zh'?'自定义中文检测页面描述。':'Custom English checker page description.');}}
if(count($ids)!==2)throw new RuntimeException('SEO_PAIR_MISSING: '.wp_json_encode(['rows'=>$rows,'ids'=>$ids]));
$control=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'seo-control-en','post_title'=>'SEO control','post_content'=>'Synthetic control'],true);if(is_wp_error($control))throw new RuntimeException('CONTROL_SEED_FAILED');pll_set_post_language($control,'en');update_post_meta($control,'rank_math_description','Synthetic ordinary control page description.');
echo wp_json_encode(['status'=>'SEEDED','ids'=>$ids,'pages'=>array_map(function($id){return ['slug'=>get_post_field('post_name',$id),'url'=>get_permalink($id)];},$ids)]);
