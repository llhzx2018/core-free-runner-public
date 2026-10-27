<?php
// Disposable fixtures only, before protected baseline. No Production content.
$layout=get_option('vf_theme_layout',[]);
foreach(['search'=>3,'blog_index'=>9] as $key=>$count){$layout['moduleSettings'][$key]['post_list']=array_merge($layout['moduleSettings'][$key]['post_list']??[],['override'=>true,'count'=>$count,'show_pagination'=>true,'sort'=>'title_asc']);}
update_option('vf_theme_layout',$layout);update_option('posts_per_page',3);
$out=[];$pairs=[];
foreach(['en','zh'] as $lang){
 $prefix=$lang==='zh'?'/zh':'';
 foreach(['post'=>10,'vf_guide'=>4,'vf_problem'=>4,'vf_glossary'=>2] as $type=>$count){
  for($i=1;$i<=$count;$i++){
   $title='Search205 '.sprintf('%02d',$i).' '.$type.' '.$lang;
   $id=wp_insert_post(['post_type'=>$type,'post_status'=>'publish','post_title'=>$title,'post_name'=>'search205-'.$type.'-'.$lang.'-'.$i,'post_excerpt'=>$lang==='zh'?'保留真实摘要与排查任务。':'A preserved authored excerpt for the search task.','post_content'=>'<p>Search205 preserved body '.$lang.' '.$type.' '.$i.'</p>'],true);
   if(is_wp_error($id))throw new RuntimeException('SEED_FAILED');pll_set_post_language($id,$lang);$pairs[$type][$i][$lang]=$id;
  }
 }
 $out[$lang]=['search'=>home_url($prefix.'/?s=Search205'),'entry'=>home_url($prefix.'/search/'),'blog'=>home_url($prefix.'/blog/?q=Search205&paged=2')];
}
foreach($pairs as $types)foreach($types as $pair)pll_save_post_translations($pair);
echo wp_json_encode($out);
