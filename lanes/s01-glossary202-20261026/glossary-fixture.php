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

// Force the real zero-independent-entry case without changing stored content.
add_action('pre_get_posts',static function($query){
 $case=(string)($_GET['glossary_case']??'');
 if(!str_starts_with($case,'inline-')||$query->is_main_query())return;
 if((array)$query->get('post_type')===['post','page']&&(int)$query->get('posts_per_page')===-1&&$query->get('fields')==='ids')$query->set('post__in',[0]);
});
// Nonpersistent object-cache fixture only; no database or content write.
add_action('template_redirect',static function(){
 $case=(string)($_GET['glossary_case']??'');if(!in_array($case,['inline-prepared','inline-unsafe'],true))return;
 $id=(int)get_queried_object_id();$post=get_post($id);if(!$post)return;
 $lang=function_exists('pll_get_post_language')?(string)pll_get_post_language($id,'slug'):'en';
 $copy=clone $post;$copy->post_content=(string)file_get_contents('/tmp/glossary-prepared-'.$lang.'.html');
 if($case==='inline-unsafe')$copy->post_content.='<dl><dt><img src="x" onerror="window.GLOSSARY_XSS=1">Shadow</dt><dd><script>window.GLOSSARY_XSS=1</script><p>Safe definition</p><a href="javascript:window.GLOSSARY_XSS=1">Unsafe target</a></dd><dt>中文名</dt><dd>非拉丁首字母定义。</dd></dl>';
 wp_cache_set($id,$copy,'posts');
},1);
