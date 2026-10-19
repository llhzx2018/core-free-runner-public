<?php
// Isolated synthetic runtime only; excluded from the Theme package.
add_action('init',static function(): void {
 foreach(['vf_guide'=>'guides','vf_problem'=>'problems','vf_glossary'=>'glossary'] as $type=>$slug){register_post_type($type,['public'=>true,'show_ui'=>true,'label'=>$type,'supports'=>['title','editor','excerpt'],'rewrite'=>['slug'=>$slug,'with_front'=>false]]);}
},0);
add_filter('pll_get_post_types',static function(array $types): array {foreach(['vf_guide','vf_problem','vf_glossary'] as $type){$types[$type]=$type;}return $types;});
$layout_fixture=static function($raw){
 if(!isset($_GET['vf_fixture_count'])&&!isset($_GET['vf_fixture_sort'])&&!isset($_GET['vf_fixture_recovery'])&&!isset($_GET['vf_fixture_copy'])&&!isset($_GET['vf_fixture_support'])&&!isset($_GET['vf_fixture_help'])&&!isset($_GET['vf_fixture_pages']))return $raw;
 $raw=is_array($raw)?$raw:[];
 foreach(['search','blog_index','archive_list'] as $context){
  $raw['moduleSettings'][$context]['post_list']['override']=true;
  if(isset($_GET['vf_fixture_count']))$raw['moduleSettings'][$context]['post_list']['count']=3;$raw['moduleSettings']['archive_list']['post_list']['mobile_count']=1;
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
 if(isset($_GET['vf_fixture_help'])){
 foreach(['problem_index','glossary_index'] as $context){$raw['moduleSettings'][$context]['post_list']['override']=true;$raw['moduleSettings'][$context]['post_list']['count']=3;$raw['moduleSettings'][$context]['post_list']['sort']='title_asc';}
 foreach(['problem_index','glossary_index'] as $context)$raw['moduleSettings'][$context]['post_list']['mobile_count']=1;
 $mode=(string)$_GET['vf_fixture_help'];$raw['moduleSettings']['faq_page']['faq']['override']=true;
 if($mode==='legacy'){$raw['moduleSettings']['faq_page']['faq']['description']='把 FAQ 做成正式页面，不要变成重复的页脚模块。';$raw['moduleSettings']['problem_index']['post_list']['description']='把错误解释做成真正的问题修复中心。';}
 if($mode==='help_custom')foreach(['problem_index','glossary_index'] as $context){$raw['moduleSettings'][$context]['post_list']['title']='Owner help catalogue title';$raw['moduleSettings'][$context]['post_list']['description']='Owner help catalogue description';}
 if($mode==='semantic'){$raw['moduleSettings']['glossary_index']['post_list']['source']='semantic_fallback';$raw['moduleSettings']['glossary_index']['post_list']['count']=9;}
 if($mode==='faq_multi'){$raw['moduleSettings']['faq_page']['faq']['accordion_mode']='multiple';$raw['moduleSettings']['faq_page']['faq']['default_open']='none';}
 if($mode==='faq_hide')foreach(['show_search','show_category_nav','show_result_count'] as $key)$raw['moduleSettings']['faq_page']['faq'][$key]=false;
 if($mode==='faq_custom'){$raw['moduleSettings']['faq_page']['faq']['title']='Owner custom help title';$raw['moduleSettings']['faq_page']['faq']['description']='Owner custom help description';}
 }
 if(isset($_GET['vf_fixture_pages'])){
  $mode=(string)$_GET['vf_fixture_pages'];
  $raw['moduleSettings']['html_sitemap']['post_list']['override']=true;
  $raw['moduleSettings']['html_sitemap']['post_list']['count']=24;
  $raw['moduleSettings']['html_sitemap']['post_list']['mobile_count']=1;
  $raw['moduleSettings']['html_sitemap']['post_list']['title']=$mode==='custom'?'Owner sitemap title':'最新内容';
  $raw['moduleSettings']['html_sitemap']['post_list']['description']=$mode==='custom'?'Owner sitemap description':'Keep the sitemap useful for users, not just crawlers.';
  $raw['moduleSettings']['basic_page']['content_block']['override']=true;
  $raw['moduleSettings']['basic_page']['content_block']['show_page_routes']=$mode!=='hide';
  $raw['moduleSettings']['basic_page']['content_block']['show_page_summary']=$mode!=='hide';
  if($mode==='default')$raw['moduleSettings']['basic_page']['content_block']['show_wordpress_content']=false;
  if($mode==='hide'){$raw['moduleSettings']['basic_page']['content_block']['show_empty_state']=false;$raw['moduleSettings']['basic_page']['content_block']['show_wordpress_content']=false;}
  if($mode==='basic_custom'){foreach(['cta','tool_grid'] as $module)$raw['moduleSettings']['basic_page'][$module]['override']=true;$raw['moduleSettings']['basic_page']['cta']['title']='Owner custom continuation';$raw['moduleSettings']['basic_page']['cta']['description']='Owner custom continuation description';$raw['moduleSettings']['basic_page']['tool_grid']['description']='Owner custom related tools description';}
  if($mode==='guide'){$raw['moduleSettings']['guide_index']['post_list']['override']=true;$raw['moduleSettings']['guide_index']['post_list']['count']=3;$raw['moduleSettings']['guide_index']['post_list']['mobile_count']=1;$raw['moduleSettings']['guide_index']['post_list']['sort']='title_asc';}
  if($mode==='no_tools')$raw['moduleSettings']['html_sitemap']['post_list']['show_sitemap_tools']=false;
  if($mode==='no_paths')$raw['moduleSettings']['html_sitemap']['post_list']['show_sitemap_release_paths']=false;
 }
 return $raw;
};
add_filter('option_vf_theme_layout',$layout_fixture,9999);
add_filter('default_option_vf_theme_layout',$layout_fixture,9999);

add_action('wp_footer',static function(): void {global $wp_query;$state=function_exists('vf_theme_directory_request_state')?vf_theme_directory_request_state('archive_list'):[];echo '<!-- search-archive-diag:'.wp_json_encode(['uri'=>$_SERVER['REQUEST_URI']??'','s'=>$wp_query->get('s'),'paged'=>$wp_query->get('paged'),'found'=>(int)$wp_query->found_posts,'post_count'=>(int)$wp_query->post_count,'is_archive'=>is_archive(),'is_search'=>is_search(),'directory'=>$state,'titles'=>wp_list_pluck((array)$wp_query->posts,'post_title'),'queried_id'=>get_queried_object_id(),'queried_lang'=>function_exists('pll_get_post_language')?pll_get_post_language(get_queried_object_id(),'slug'):'','public_lang'=>function_exists('vf_theme_public_language')?vf_theme_public_language():'','support_id'=>function_exists('vf_theme_support_page_current_post_id')?vf_theme_support_page_current_post_id():0,'query_owner'=>function_exists('vf_toolsite_apply_static_route_query_context')?basename((new ReflectionFunction('vf_toolsite_apply_static_route_query_context'))->getFileName()):'']).' -->';});

add_filter('the_content',static function($html){return (($_GET['vf_fixture_support']??'')==='empty')?'':$html;},99999);

add_filter('post_link',static function($url,$post){if(get_post_meta($post->ID,'_fixture_owned_problem',true)){return home_url('/'.(function_exists('pll_get_post_language')&&pll_get_post_language($post->ID,'slug')==='zh'?'zh/':'').'problems/m3u8-cors-error-explained/');}return $url;},30,2);

add_shortcode('vf_summary_probe',static function(){update_option('vf_summary_probe_executed',true);return 'EXECUTED_SUMMARY_PROBE';});
// Exercise the actual default-body branch under the real Theme stack.
add_action('template_redirect',static function(){
 if(($_GET['vf_fixture_pages']??'')!=='default'||!is_page())return;
 if(function_exists('vf_theme_public_runtime_require_template_stack'))vf_theme_public_runtime_require_template_stack();
 get_header();vf_theme_render_module_stack(['route'=>'basicwork','family'=>'basic-page-template','title'=>get_the_title(),'field_data'=>['title'=>get_the_title(),'body'=>'Owner fallback body retained.']],'basic_page');get_footer();exit;
},0);

add_filter('posts_results', static function($posts,$query){if($query->get('vf_theme_archive_shell_probe')===true){$GLOBALS['archive_probe_batches'][]=['rows'=>count($posts),'offset'=>(int)$query->get('offset')];}return $posts;},10,2);
add_action('wp_footer',static function(){echo '<!-- archive-probe-batches:'.wp_json_encode($GLOBALS['archive_probe_batches']??[]).' -->';});
