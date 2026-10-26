<?php
// Synthetic WordPress fixture, no Production data.
$layout=get_option('vf_theme_layout',[]);
$layout['modules']['faq_page']=['hero','faq','cta'];
$layout['templates']['faq_page']['hero']='show';
$layout['moduleSettings']['faq_page']['faq']=['override'=>true,'source'=>'current_page','title'=>'Frequently asked questions','description'=>'Find an answer by keyword, or browse playback, access and usage questions by category.','count'=>12,'mobile_count'=>8,'show_search'=>true,'show_category_nav'=>true,'show_result_count'=>true,'show_group_descriptions'=>true,'default_open'=>'first_group','accordion_mode'=>'single','sort'=>'manual'];
update_option('vf_theme_layout',$layout);
$out=[];$pairs=[];
foreach(['en','zh']as$lang){
 $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'faq','post_title'=>$lang==='zh'?'M3U8 / HLS 常见问题':'M3U8 / HLS Frequently Asked Questions','post_content'=>'<p>Owner FAQ page content remains intact.</p>','post_excerpt'=>'Owner FAQ description','post_date'=>'2026-10-20 10:00:00'],true);
 if(is_wp_error($id))throw new RuntimeException('FAQ_SEED_FAILED');
 pll_set_post_language($id,$lang);$pairs[$lang]=$id;
 update_post_meta($id,'rank_math_description','Owner FAQ SEO description '.$lang);
 $out[$lang]=home_url($lang==='zh'?'/zh/faq/':'/faq/');
}
pll_save_post_translations($pairs);
echo wp_json_encode($out);
