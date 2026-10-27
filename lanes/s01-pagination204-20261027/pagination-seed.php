<?php
// Disposable native content and settings before protected-state baseline only.
$layout=get_option('vf_theme_layout',[]);
foreach(['blog_index','guide_index','problem_index','archive_list','search'] as $key){
 $old=$layout['moduleSettings'][$key]['post_list']??[];
 $layout['moduleSettings'][$key]['post_list']=array_merge($old,['override'=>true,'count'=>3,'show_pagination'=>true,'sort'=>'title_asc']);
 if($key==='guide_index'||$key==='problem_index'){
  $layout['moduleSettings'][$key]['post_list']['source']='registered_type';
  $layout['moduleSettings'][$key]['post_list']['content_type']=$key==='guide_index'?'vf_guide':'vf_problem';
 }
}
update_option('vf_theme_layout',$layout);update_option('posts_per_page',3);
$out=[];
foreach(['en','zh'] as $lang){
 $zh=$lang==='zh';$prefix=$zh?'/zh':'';
 $term=wp_insert_term('Pagination204 '.$lang,'category',['slug'=>'pagination204-'.$lang]);
 if(is_wp_error($term))throw new RuntimeException('PAGINATION_TERM_FAILED');$term=(int)$term['term_id'];
 pll_set_term_language($term,$lang);
 $tag=wp_insert_term('Pagination204 '.$lang,'post_tag',['slug'=>'pagination204-'.$lang]);
 if(is_wp_error($tag))throw new RuntimeException('PAGINATION_TAG_FAILED');$tag=(int)$tag['term_id'];pll_set_term_language($tag,$lang);
 foreach(['post','vf_guide','vf_problem'] as $type){
  if(!post_type_exists($type))throw new RuntimeException('MISSING_NATIVE_TYPE_'.$type);
  for($i=1;$i<=24;$i++){
   $title='Pagination204 '.sprintf('%02d',$i).' '.$type.' '.$lang;
   $id=wp_insert_post(['post_type'=>$type,'post_status'=>'publish','post_name'=>'pagination204-'.$type.'-'.$lang.'-'.$i,'post_title'=>$title,'post_excerpt'=>$zh?'合成分页摘要，保留内容与来源。':'Synthetic pagination excerpt; preserve content and source.','post_content'=>'<p>Pagination204 authored body '.$lang.' '.$i.'.</p>','post_author'=>1,'post_date'=>'2026-10-15 10:00:00'],true);
   if(is_wp_error($id))throw new RuntimeException('PAGINATION_POST_FAILED');pll_set_post_language($id,$lang);
   if($type==='post'){wp_set_post_categories($id,[$term]);wp_set_post_terms($id,[$tag],'post_tag');}
  }
 }
 $out[$lang]=[
  'blog'=>home_url($prefix.'/blog/'),
  'guides'=>home_url($prefix.'/guides/'),
  'problems'=>home_url($prefix.'/problems/'),
  'glossary'=>home_url($prefix.'/glossary/?glossary_case=inline-legacy'),
  'category'=>get_term_link($term,'category'),
  'tag'=>get_term_link($tag,'post_tag'),
  'author'=>home_url($prefix.'/author/admin/'),
  'date'=>home_url($prefix.'/2026/10/'),
  'search'=>add_query_arg(['s'=>'Pagination204'],home_url($prefix.'/')),
 ];
}
echo wp_json_encode($out);
