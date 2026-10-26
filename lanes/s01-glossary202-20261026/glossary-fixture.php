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
add_filter('posts_pre_query',static function($posts,$query){
 $case=(string)($_GET['glossary_case']??'');
 if(!str_starts_with($case,'inline-')||$query->is_main_query())return $posts;
 // Limit the synthetic empty pool to this renderer's query; do not alter URL/locale probes.
 $frames=debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS);
 if(!in_array('vf_theme_render_context_query_posts',array_column($frames,'function'),true))return $posts;
 $query->found_posts=0;$query->max_num_pages=1;return [];
},20000,2);
// Nonpersistent object-cache fixture only; no database or content write.
add_action('template_redirect',static function(){
 $case=(string)($_GET['glossary_case']??'');if(!in_array($case,['inline-prepared','inline-unsafe'],true))return;
 $lang=str_starts_with((string)($_SERVER['REQUEST_URI']??''),'/zh/')?'zh':'en';
 $id=(int)vf_theme_public_route_contract_find_exact_published_post_id_for_route_language('glossary',$lang);$post=get_post($id);if(!$post)return;
 $copy=clone $post;$copy->post_content=(string)file_get_contents('/tmp/glossary-prepared-'.$lang.'.html');
 if($case==='inline-unsafe')$copy->post_content.='<dl><dt><img src="x" onerror="window.GLOSSARY_XSS=1">Shadow</dt><dd><script>window.GLOSSARY_XSS=1</script><p>Safe definition</p><a href="javascript:window.GLOSSARY_XSS=1">Unsafe target</a></dd><dt>中文名</dt><dd>非拉丁首字母定义。</dd></dl>';
 wp_cache_set($id,$copy,'posts');
},1);

// Bounded read-only diagnostics emitted only in isolated inline cases.
add_action('wp_footer',static function(){
 if(!str_starts_with((string)($_GET['glossary_case']??''),'inline-'))return;
 $lang=str_starts_with((string)($_SERVER['REQUEST_URI']??''),'/zh/')?'zh':'en';
 $route=function_exists('vf_toolsite_static_request_path')?vf_toolsite_static_request_path():'missing';
 $id=(int)vf_theme_public_route_contract_find_exact_published_post_id_for_route_language('glossary',$lang);
 $info=['route'=>$route,'language'=>vf_theme_public_language(),'queried'=>get_queried_object_id(),'exact'=>$id,'post_language'=>$id?pll_get_post_language($id):'','bytes'=>strlen((string)get_post_field('post_content',$id)),'pool'=>$GLOBALS['vf_theme_glossary_has_entries']??null,'inline_total'=>$GLOBALS['vf_theme_glossary_inline_total']??null,'parsed'=>function_exists('vf_theme_glossary_page_terms')?count(vf_theme_glossary_page_terms()):null,'plan'=>vf_theme_post_list_query_plan('glossary_index')];
 echo '<pre id="glossary-test-diagnostics" hidden>'.esc_html(wp_json_encode($info)).'</pre>';
},9999);
