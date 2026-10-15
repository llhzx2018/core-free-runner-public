<?php
// Isolated synthetic runtime only; excluded from the Theme package.
add_action('init',static function(): void {
 foreach(['vf_guide'=>'guides','vf_problem'=>'problems','vf_glossary'=>'glossary'] as $type=>$slug){register_post_type($type,['public'=>true,'show_ui'=>true,'label'=>$type,'supports'=>['title','editor','excerpt'],'rewrite'=>['slug'=>$slug,'with_front'=>false]]);}
},0);
add_filter('pll_get_post_types',static function(array $types): array {foreach(['vf_guide','vf_problem','vf_glossary'] as $type){$types[$type]=$type;}return $types;});
$layout_fixture=static function($raw){
 if(!isset($_GET['vf_fixture_count'])&&!isset($_GET['vf_fixture_sort'])&&!isset($_GET['vf_fixture_recovery']))return $raw;
 $raw=is_array($raw)?$raw:[];
 foreach(['search','blog_index','archive_list'] as $context){
  $raw['moduleSettings'][$context]['post_list']['override']=true;
  if(isset($_GET['vf_fixture_count']))$raw['moduleSettings'][$context]['post_list']['count']=3;
  if(isset($_GET['vf_fixture_sort']))$raw['moduleSettings'][$context]['post_list']['sort']='title_asc';
 }
 if(isset($_GET['vf_fixture_recovery'])){$raw['moduleSettings']['archive_list']['system_recovery']['override']=true;$raw['moduleSettings']['archive_list']['system_recovery']['title']='Owner Recovery Heading';$raw['moduleSettings']['archive_list']['system_recovery']['description']='Owner Recovery Description';}
 return $raw;
};
add_filter('option_vf_theme_layout',$layout_fixture,9999);
add_filter('default_option_vf_theme_layout',$layout_fixture,9999);

add_action('wp_footer',static function(): void {global $wp_query;$state=function_exists('vf_theme_directory_request_state')?vf_theme_directory_request_state('archive_list'):[];echo '<!-- search-archive-diag:'.wp_json_encode(['uri'=>$_SERVER['REQUEST_URI']??'','s'=>$wp_query->get('s'),'paged'=>$wp_query->get('paged'),'found'=>(int)$wp_query->found_posts,'post_count'=>(int)$wp_query->post_count,'is_archive'=>is_archive(),'is_search'=>is_search(),'directory'=>$state,'titles'=>wp_list_pluck((array)$wp_query->posts,'post_title')]).' -->';});
