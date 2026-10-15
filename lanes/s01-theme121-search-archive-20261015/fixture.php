<?php
// Isolated synthetic runtime only; excluded from the Theme package.
add_action('init',static function(): void {
 foreach(['vf_guide'=>'guides','vf_problem'=>'problems','vf_glossary'=>'glossary'] as $type=>$slug){register_post_type($type,['public'=>true,'show_ui'=>true,'label'=>$type,'supports'=>['title','editor','excerpt'],'rewrite'=>['slug'=>$slug,'with_front'=>false]]);}
},0);
add_filter('pll_get_post_types',static function(array $types): array {foreach(['vf_guide','vf_problem','vf_glossary'] as $type){$types[$type]=$type;}return $types;});
$layout_fixture=static function($raw){
 if(!isset($_GET['vf_fixture_count'])&&!isset($_GET['vf_fixture_sort']))return $raw;
 $raw=is_array($raw)?$raw:[];
 foreach(['search','blog_index','archive_list'] as $context){
  $raw['moduleSettings'][$context]['post_list']['override']=true;
  if(isset($_GET['vf_fixture_count']))$raw['moduleSettings'][$context]['post_list']['count']=3;
  if(isset($_GET['vf_fixture_sort']))$raw['moduleSettings'][$context]['post_list']['sort']='title_asc';
 }
 return $raw;
};
add_filter('option_vf_theme_layout',$layout_fixture,9999);
add_filter('default_option_vf_theme_layout',$layout_fixture,9999);
