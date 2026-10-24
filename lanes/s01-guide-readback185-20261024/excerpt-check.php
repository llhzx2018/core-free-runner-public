<?php
if(!function_exists('vf_theme_guide_directory_excerpt'))require_once get_template_directory().'/inc/modules/module-post-list.php';
$GLOBALS['excerpt_callback_calls']=0;
add_shortcode('vf_excerpt_guard',static function(){ $GLOBALS['excerpt_callback_calls']++;return 'UNSAFE_CALLBACK'; });
$ids=get_posts(['post_type'=>'vf_guide','post_status'=>'publish','posts_per_page'=>-1,'suppress_filters'=>true,'fields'=>'ids']);$checks=[];
foreach($ids as$id){
 $saved=(string)get_post_field('post_excerpt',$id,'raw');$body=(string)get_post_field('post_content',$id,'raw');
 $got=vf_theme_guide_directory_excerpt($id,28);
 if(str_contains($saved,'KEEP_AUTHORED_END')&& !str_ends_with($got,'KEEP_AUTHORED_END'))throw new RuntimeException('AUTHORED_EXCERPT_LOST');
 if(str_contains($saved,'KEEP_SAFE_END')){if(str_contains($got,'<')||str_contains($got,'UNSAFE_CALLBACK')||str_contains($got,'UNSAFE_EXCERPT'))throw new RuntimeException('EXCERPT_UNSAFE');}
 if($saved===''&&str_contains($body,'中文自动摘要')){if(mb_strlen($got)<36||mb_strlen($got)>86)throw new RuntimeException('CJK_AUTO_BUDGET');}
 $checks[]=['id'=>(int)$id,'saved_preserved'=>$saved===''?'N_A':$got===vf_theme_post_list_excerpt_text($saved),'derived_only'=>$saved==='','length'=>mb_strlen($got)];
}
if($GLOBALS['excerpt_callback_calls']!==0)throw new RuntimeException('SHORTCODE_CALLBACK_EXECUTED');
echo wp_json_encode(['status'=>'PASS','cases'=>count($checks),'shortcode_calls'=>0,'checks'=>$checks])."\n";
