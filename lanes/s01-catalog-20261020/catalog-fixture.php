<?php
// Request-local synthetic settings only, never shipped or stored.
$catalog_count=static function($raw){
 if(($_GET['vf_catalog_review']??'')!=='1')return $raw;
 $raw=is_array($raw)?$raw:[];
 foreach(['blog_index','guide_index','problem_index','glossary_index','archive_list','search'] as $context){
  $raw['moduleSettings'][$context]['post_list']['override']=true;
  $raw['moduleSettings'][$context]['post_list']['count']=3;
 }
 return $raw;
};
add_filter('option_vf_theme_layout',$catalog_count,10002);
add_filter('default_option_vf_theme_layout',$catalog_count,10002);
