<?php
// Isolated CLI main-query checks only; no stored setting changes.
add_filter('option_vf_theme_layout',static function($raw){
 if(getenv('S01_BLOG_NATIVE_QUERY')!=='1')return $raw;
 $raw=is_array($raw)?$raw:[];$raw['moduleSettings']['blog_index']['post_list']['override']=true;$raw['moduleSettings']['blog_index']['post_list']['source']='current_query';$raw['moduleSettings']['blog_index']['post_list']['count']=9;
 return $raw;
},10000);
