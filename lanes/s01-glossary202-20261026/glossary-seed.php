<?php
// Isolated synthetic content only. No Production content or review writes.
$layout=get_option('vf_theme_layout',[]);
$layout['modules']['glossary_index']=['hero','post_list','cta'];
$layout['templates']['glossary_index']['hero']='show';
$layout['moduleSettings']['glossary_index']['post_list']=['override'=>true,'source'=>'semantic_fallback','title'=>'Glossary terms','description'=>'Understand manifest, segment, playlist, CORS, AES-128, live/VOD and related terms.','count'=>12,'mobile_count'=>8,'sort'=>'title_asc','show_search'=>true,'show_pagination'=>true,'show_glossary_filters'=>true,'show_glossary_letter_index'=>true,'show_directory_navigation'=>false];
update_option('vf_theme_layout',$layout);
$cat=wp_insert_term('Glossary','category',['slug'=>'glossary']);$catid=is_wp_error($cat)?$cat->get_error_data()['term_id']:$cat['term_id'];
$out=[];$pairs=[];
foreach(['en','zh']as$lang){
 $pages=get_posts(['post_type'=>'page','name'=>'glossary','lang'=>$lang,'numberposts'=>1]);
 $id=$pages?(int)$pages[0]->ID:wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'glossary','post_title'=>$lang==='zh'?'M3U8 / HLS 术语表':'M3U8 / HLS Glossary','post_content'=>'<p>Owner glossary index content.</p>']);
 pll_set_post_language($id,$lang);$pairs[$lang]=$id;update_post_meta($id,'rank_math_description','Owner glossary SEO '.$lang);
 $out[$lang]=home_url($lang==='zh'?'/zh/glossary/':'/glossary/');
 for($i=0;$i<30;$i++){
  $letter=$i<14?'A':($i<16?'Z':'#');$title=$letter==='#'?($lang==='zh'?'分片术语':'特殊术语'):($letter.' '.($lang==='zh'?'术语':'Term').' '.sprintf('%02d',$i));
  $post=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_name'=>'glossary-sample-'.$lang.'-'.$i,'post_title'=>$title,'post_excerpt'=>($lang==='zh'?'清晰的术语解释，保留原有内容。':'A practical definition retained from authored content.'),'post_content'=>'<p>Authored glossary definition '.$i.' '.$lang.'.</p>','post_category'=>[(int)$catid],'post_date'=>'2026-10-20 10:00:00']);
  pll_set_post_language($post,$lang);update_post_meta($post,'_vf_glossary_category',$i%2?'security':'playlist');
  if($letter!=='#')update_post_meta($post,'_vf_glossary_letter',$letter);
  update_post_meta($post,'_vf_glossary_aliases',$i===15?'NeedleOutsideFirstPage':'Alias '.sprintf('%02d',$i));
 }
}
pll_save_post_translations($pairs);
foreach (['en','zh'] as $lang) { $raw=json_decode(file_get_contents('/tmp/glossary-original-'.$lang.'.json'),true);wp_update_post(['ID'=>$pairs[$lang],'post_content'=>$raw['post_content'],'post_excerpt'=>$raw['post_excerpt']]); }
echo wp_json_encode($out);
