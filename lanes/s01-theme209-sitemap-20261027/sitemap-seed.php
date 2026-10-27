<?php
// Synthetic isolated data only, deliberately matching Production's shared slugs.
global $wpdb;
$ids=[];$titles=['en'=>'Media tools sitemap','zh'=>'媒体工具站点地图'];
foreach($titles as $lang=>$title){
 $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'sitemap','post_title'=>$title,'post_content'=>'','post_excerpt'=>'']);
 if(is_wp_error($id)||!$id)throw new RuntimeException('SITEMAP_SEED_FAILED');
 pll_set_post_language($id,$lang);$wpdb->update($wpdb->posts,['post_name'=>'sitemap'],['ID'=>$id]);clean_post_cache($id);$ids[$lang]=$id;
}
pll_save_post_translations($ids);
foreach(['en','zh'] as $lang){
 for($i=1;$i<=3;$i++){
  $title=$lang==='en'?($i===1?'A long practical HLS playlist diagnosis title with a continuous-stream-reference-that-must-wrap-without-clipping':'Authored playlist reference '.$i):($i===1?'用于验证目录长标题换行、分组间距与真实语言隔离的媒体播放列表排查记录':'播放列表参考记录'.$i);
  $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_name'=>'sitemap-reference-'.$lang.'-'.$i,'post_title'=>$title,'post_content'=>'<p>Authored sitemap reference.</p>','post_excerpt'=>'Authored summary preserved.']);pll_set_post_language($id,$lang);
  // Stable distinct timestamps keep unchanged modified-desc recommendations deterministic.
  $stamp='2026-10-20 10:00:0'.$i;
  $wpdb->update($wpdb->posts,['post_date'=>$stamp,'post_date_gmt'=>$stamp,'post_modified'=>$stamp,'post_modified_gmt'=>$stamp],['ID'=>$id]);clean_post_cache($id);
 }
}
$layout=get_option('vf_theme_layout',[]);$row=$layout['moduleSettings']['html_sitemap']['post_list']??[];
$row=array_merge($row,['override'=>true,'source'=>'public_routes','content_type'=>'public_routes','count'=>24,'mobile_count'=>8,'sitemap_columns'=>3,'show_sitemap_counts'=>true,'show_sitemap_updated'=>true,'show_sitemap_tools'=>true,'show_sitemap_guides'=>true,'show_sitemap_problems'=>true,'show_sitemap_glossary'=>true,'show_sitemap_articles'=>true,'show_sitemap_pages'=>true,'show_sitemap_company'=>true,'show_sitemap_legal'=>true,'show_sitemap_release_paths'=>true,'title'=>'','description'=>'']);
$layout['moduleSettings']['html_sitemap']['post_list']=$row;update_option('vf_theme_layout',$layout);wp_cache_flush();
echo wp_json_encode(['status'=>'PASS','ids'=>$ids,'titles'=>$titles,'production'=>'UNTOUCHED']);
