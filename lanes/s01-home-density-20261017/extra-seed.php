<?php
// Synthetic published cases and language menus. Never used on Production.
require_once get_template_directory().'/inc/services/page-runtime-contract-service.php';
$cases=[];
foreach(['en','zh']as $lang){
 $prefix=$lang==='zh'?'/zh/':'/';
 foreach(vf_theme_page_runtime_contracts()as $key=>$contract){
  $url=home_url($prefix.ltrim($contract['path'],'/'));
  if($key==='search')$url=add_query_arg('s','Searchwork',home_url($prefix));
  if($key==='archive_list')$url=get_category_link(get_term_by('slug','video-fixture-'.$lang,'category')->term_id);
  if(in_array($key,['article_detail','guide_detail','problem_detail','glossary_detail','basic_page'],true)){
   $type=['article_detail'=>'post','guide_detail'=>'vf_guide','problem_detail'=>'vf_problem','glossary_detail'=>'vf_glossary','basic_page'=>'page'][$key];
   $args=['post_type'=>$type,'post_status'=>'publish','posts_per_page'=>1,'lang'=>$lang,'orderby'=>'ID','order'=>'ASC'];
   if($key==='basic_page')$args['name']='basicwork-'.$lang;
   $posts=get_posts($args);if(!$posts)throw new Exception('MISSING_SYNTHETIC_CASE');$url=get_permalink($posts[0]->ID);
  }
  $cases[$lang][$key]=$url;
 }
}
$options=get_option('polylang',[]);$menus=[];
foreach(['en','zh']as $lang){
 foreach(['header','mobile','footer_tools','footer_resources','footer_company','footer_partners']as $location){
  $menu=wp_create_nav_menu('Synthetic '.$location.' '.$lang);if(is_wp_error($menu))throw new Exception('MENU_SEED_FAILED');
  $items=match($location){
   'header','mobile'=>['tool_hub','guide_index','faq_page','about_page'],
   'footer_tools'=>['tool','tool_hub'],
   'footer_resources'=>['guide_index','problem_index','faq_page','glossary_index'],
   'footer_company'=>['about_page','contact_page','blog_index','html_sitemap'],default=>[],
  };
  foreach($items as $key)wp_update_nav_menu_item($menu,0,['menu-item-title'=>vf_theme_page_runtime_contracts()[$key]['label'],'menu-item-url'=>$cases[$lang][$key],'menu-item-status'=>'publish','menu-item-type'=>'custom']);
  $menus[$location][$lang]=(int)$menu;
 }
}
$options['nav_menus'][get_stylesheet()]=$menus;update_option('polylang',$options);
$locations=[];foreach($menus as $location=>$langs)$locations[$location]=$langs['en'];set_theme_mod('nav_menu_locations',$locations);
echo wp_json_encode(['cases'=>$cases,'menus'=>'SYNTHETIC_NATIVE_POLYLANG_MAP','production'=>'NOT_EXECUTED']);
