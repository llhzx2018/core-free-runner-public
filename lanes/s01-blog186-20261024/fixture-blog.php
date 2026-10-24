<?php
// Test-only option filters: request-local cases, never persisted.
add_filter('option_vf_theme_layout',static function($raw){
 $case=(string)($_GET['vf_blog_case']??'');if($case==='')return $raw;
 $raw=is_array($raw)?$raw:[];$settings=&$raw['moduleSettings']['blog_index']['post_list'];$settings['override']=true;
 if($case==='custom'){$settings['title']='Owner editorial heading';$settings['description']='Owner editorial description';$raw['moduleSettings']['blog_index']['cta']=['override'=>true,'title'=>'Owner continuation heading','description'=>'Owner continuation description'];}
 if($case==='title_only')$settings['title']='Owner title alone';
 if($case==='description_only')$settings['description']='Owner description alone';
 if($case==='settings'){$settings['sort']='title_asc';$settings['count']=3;$settings['show_image']=false;$settings['show_date']=false;$settings['show_read_time']=false;}
 return $raw;
},10000);
