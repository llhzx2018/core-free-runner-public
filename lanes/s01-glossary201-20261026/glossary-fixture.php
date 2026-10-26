<?php
// Request-local isolated cases; never shipped in the Theme or persisted.
add_filter('option_vf_theme_layout',static function($raw){
 $case=(string)($_GET['glossary_case']??'');if($case==='')return $raw;
 if($case==='hero-off')$raw['templates']['glossary_index']['hero']='hide';
 if($case==='hero-later')$raw['modules']['glossary_index']=['post_list','hero','cta'];
 if($case==='custom'){
  $raw['moduleSettings']['glossary_index']['post_list']=array_merge($raw['moduleSettings']['glossary_index']['post_list'],['title'=>'Owner custom glossary heading','description'=>'Owner custom glossary introduction']);
  $raw['moduleSettings']['glossary_index']['cta']=['override'=>true,'title'=>'Owner custom next step','description'=>'Owner custom helpful action'];
 }
 if($case==='empty')$raw['moduleSettings']['glossary_index']['post_list']['source']='registered_type';
 if($case==='flags'){
  $raw['moduleSettings']['glossary_index']['post_list']['show_search']=false;
  $raw['moduleSettings']['glossary_index']['post_list']['show_glossary_filters']=false;
  $raw['moduleSettings']['glossary_index']['post_list']['show_glossary_letter_index']=false;
 }
 return $raw;
},20000);
