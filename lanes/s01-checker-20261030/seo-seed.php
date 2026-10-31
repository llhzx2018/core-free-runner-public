<?php
$ids=[]; global $wpdb;
$rows=$wpdb->get_col("SELECT ID FROM $wpdb->posts WHERE post_type='page' AND post_status='publish' AND post_content LIKE '%vf_m3u8_playlist_checker%'");
foreach($rows as $id){$lang=pll_get_post_language((int)$id);if(in_array($lang,['en','zh'],true)){$ids[$lang]=(int)$id;update_post_meta((int)$id,'rank_math_description',$lang==='zh'?'自定义中文检测页面描述。':'Custom English checker page description.');}}
if(count($ids)!==2)throw new RuntimeException('SEO_PAIR_MISSING: '.wp_json_encode(['rows'=>$rows,'ids'=>$ids]));
echo wp_json_encode(['status'=>'SEEDED','ids'=>$ids,'pages'=>array_map(function($id){return ['slug'=>get_post_field('post_name',$id),'url'=>get_permalink($id)];},$ids)]);
