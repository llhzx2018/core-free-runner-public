<?php
// Isolated synthetic runtime only; excluded from the Theme package.
add_action('init',static function(): void {
 foreach(['vf_guide'=>'guides','vf_problem'=>'problems','vf_glossary'=>'glossary'] as $type=>$slug){register_post_type($type,['public'=>true,'show_ui'=>true,'label'=>$type,'supports'=>['title','editor','excerpt'],'rewrite'=>['slug'=>$slug,'with_front'=>false]]);}
},0);
add_filter('pll_get_post_types',static function(array $types): array {foreach(['vf_guide','vf_problem','vf_glossary'] as $type){$types[$type]=$type;}return $types;});
$layout_fixture=static function($raw){
 if(!isset($_GET['vf_fixture_count'])&&!isset($_GET['vf_fixture_sort'])&&!isset($_GET['vf_fixture_recovery'])&&!isset($_GET['vf_fixture_copy'])&&!isset($_GET['vf_fixture_support']))return $raw;
 $raw=is_array($raw)?$raw:[];
 foreach(['search','blog_index','archive_list'] as $context){
  $raw['moduleSettings'][$context]['post_list']['override']=true;
  if(isset($_GET['vf_fixture_count']))$raw['moduleSettings'][$context]['post_list']['count']=3;
  if(isset($_GET['vf_fixture_sort']))$raw['moduleSettings'][$context]['post_list']['sort']='title_asc';
 }
 if(isset($_GET['vf_fixture_recovery'])){$raw['moduleSettings']['archive_list']['system_recovery']['override']=true;$raw['moduleSettings']['archive_list']['system_recovery']['title']='Owner Recovery Heading';$raw['moduleSettings']['archive_list']['system_recovery']['description']='Owner Recovery Description';}
 if(isset($_GET['vf_fixture_copy'])){$raw['moduleSettings']['blog_index']['post_list']['override']=true;$raw['moduleSettings']['blog_index']['post_list']['description']=['legacy_en'=>'A clean article list for long-tail SEO content.','legacy_zh'=>'用于长尾 SEO 内容的清晰文章列表。','custom'=>'Owner public description 2026'][$_GET['vf_fixture_copy']]??'';}
 if(($_GET['vf_fixture_support']??'')==='hide'){
 foreach(['about_page','contact_page','legal'] as $context){$raw['moduleSettings'][$context]['content_block']['override']=true;}
 foreach(['show_wordpress_content','show_principles','show_mission','show_privacy','show_use_cases','show_scope','show_route_links','show_contact_link'] as $key)$raw['moduleSettings']['about_page']['content_block'][$key]=false;
 foreach(['show_wordpress_content','show_no_channel_state','show_checklist','show_feedback_types'] as $key)$raw['moduleSettings']['contact_page']['content_block'][$key]=false;
 foreach(['show_document_navigation','show_section_toc','show_wordpress_content','show_missing_content_state','show_scope_summary','show_last_updated'] as $key)$raw['moduleSettings']['legal']['content_block'][$key]=false;
 }
 return $raw;
};
add_filter('option_vf_theme_layout',$layout_fixture,9999);
add_filter('default_option_vf_theme_layout',$layout_fixture,9999);

add_action('wp_footer',static function(): void {global $wp_query;$state=function_exists('vf_theme_directory_request_state')?vf_theme_directory_request_state('archive_list'):[];echo '<!-- search-archive-diag:'.wp_json_encode(['uri'=>$_SERVER['REQUEST_URI']??'','s'=>$wp_query->get('s'),'paged'=>$wp_query->get('paged'),'found'=>(int)$wp_query->found_posts,'post_count'=>(int)$wp_query->post_count,'is_archive'=>is_archive(),'is_search'=>is_search(),'directory'=>$state,'titles'=>wp_list_pluck((array)$wp_query->posts,'post_title')]).' -->';});

add_filter('the_content',static function($html){return (($_GET['vf_fixture_support']??'')==='empty')?'':$html;},99999);
