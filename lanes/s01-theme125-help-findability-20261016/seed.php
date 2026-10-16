<?php
$options=get_option('polylang',[]);$options['post_types']=['vf_guide','vf_problem','vf_glossary'];update_option('polylang',$options);
$out=[];
foreach(['en'=>13,'zh'=>5] as $language=>$total){
 $term=wp_insert_term($language==='en'?'Video Fixture':'视频示例','category',['slug'=>'video-fixture-'.$language,'description'=>$language==='en'?'Owner authored category description.':'作者填写的分类说明。']);
 $cat=is_wp_error($term)?get_term_by('slug','video-fixture-'.$language,'category')->term_id:$term['term_id'];pll_set_term_language($cat,$language);
 $tag=wp_insert_term('Atlas '.$language,'post_tag',['slug'=>'atlas-'.$language]);$tag=is_wp_error($tag)?get_term_by('slug','atlas-'.$language,'post_tag')->term_id:$tag['term_id'];pll_set_term_language($tag,$language);
 $empty=wp_insert_term('Empty '.$language,'category',['slug'=>'empty-'.$language]);$empty=is_wp_error($empty)?get_term_by('slug','empty-'.$language,'category')->term_id:$empty['term_id'];pll_set_term_language($empty,$language);
 $ids=[];
 for($i=1;$i<=$total;$i++){
  $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_title'=>'Searchwork Atlas '.strtoupper($language).' '.sprintf('%02d',$i).($i===1?' Needleword':''),'post_name'=>'searchwork-'.$language.'-'.$i,'post_content'=>'<h2>Original heading</h2><p>Original authored content '.$language.' '.$i.'</p>','post_excerpt'=>'Owner authored summary '.$language.' '.$i,'post_date'=>'2024-01-'.sprintf('%02d',$i).' 12:00:00','post_category'=>[$cat]]);pll_set_post_language($id,$language);if($i<=6)wp_set_post_tags($id,[$tag]);$ids[]=$id;
 }
 foreach(['draft','private'] as $status){$id=wp_insert_post(['post_type'=>'post','post_status'=>$status,'post_title'=>'Searchwork Atlas HIDDEN '.$language,'post_content'=>'Must never be a result']);pll_set_post_language($id,$language);}
 for($i=1;$i<=3;$i++){$id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_title'=>'Searchwork Atlas Guide '.strtoupper($language).' '.$i,'post_name'=>'atlas-guide-'.$language.'-'.$i,'post_content'=>'<p>Original guide content.</p>']);pll_set_post_language($id,$language);}
 for($i=1;$i<=2;$i++){$id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Snippetwork '.strtoupper($language).' '.$i,'post_name'=>'snippetwork-'.$language.'-'.$i,'post_content'=>$i===1?'[vf_m3u8_disabled secret=hide]':'<p>Readable prose &amp; more [vf_m3u8_disabled]</p>','post_excerpt'=>$i===1?'':'Authored public summary','post_date'=>'2024-02-03 12:00:00']);pll_set_post_language($id,$language);}
 $out[$language]=['category'=>get_category_link($cat),'tag'=>get_tag_link($tag),'empty'=>get_category_link($empty),'ids'=>$ids];
}
pll_save_term_translations(['en'=>get_term_by('slug','video-fixture-en','category')->term_id,'zh'=>get_term_by('slug','video-fixture-zh','category')->term_id]);
pll_save_post_translations(['en'=>$out['en']['ids'][0],'zh'=>$out['zh']['ids'][0]]);
$support_pairs=[];
foreach(['about','contact','privacy-policy','terms','acceptable-use','dmca'] as $route){
 $pair=[];
 foreach(['en','zh'] as $language){
  $body=$route==='contact'?'<p>Owner contact '.$language.'</p><a href="mailto:support@example.invalid">Owner contact email</a>':($route==='terms'?'':'<h2>Owner first section '.$language.'</h2><p>'.str_repeat('Owner published text '.$language.'. ',25).'</p><h2>Owner second section '.$language.'</h2><p>Owner final paragraph.</p>');
  $existing=$language==='en'?get_page_by_path($route,OBJECT,'page'):null;
  $record=['post_type'=>'page','post_status'=>'draft','post_name'=>$route,'post_title'=>'Owner '.ucwords(str_replace('-',' ',$route)).' '.$language,'post_content'=>$body];if($existing)$record['ID']=$existing->ID;
  $id=wp_insert_post($record,true);if(is_wp_error($id))throw new RuntimeException('SUPPORT_SEED_FAILED');pll_set_post_language($id,$language);$pair[$language]=(int)$id;
 }
 pll_save_post_translations($pair);
 foreach($pair as $language=>$id){wp_update_post(['ID'=>$id,'post_status'=>($route==='dmca'||($route==='acceptable-use'&&$language==='zh'))?'draft':'publish','post_name'=>$route]);if(get_post_field('post_name',$id)!==$route){global $wpdb;$wpdb->update($wpdb->posts,['post_name'=>$route],['ID'=>$id],['%s'],['%d']);clean_post_cache($id);}}
 if($route==='acceptable-use')foreach($pair as $id)update_post_meta($id,'_wp_page_template','page-legal.php');
 $support_pairs[$route]=$pair;
}
$layout=get_option('vf_theme_layout',[]);$layout['s01_authored_keep']='retained';update_option('vf_theme_layout',$layout);set_theme_mod('s01_authored_keep','retained');
$help=[];
foreach(['en','zh'] as $language){
 $help[$language]=[];
 foreach(['vf_problem'=>'problem','vf_glossary'=>'glossary'] as $type=>$kind){
  $ids=[];$urls=[];
  for($i=1;$i<=7;$i++){
   $id=wp_insert_post(['post_type'=>$type,'post_status'=>'publish','post_name'=>'helpwork-'.$kind.'-'.$language.'-'.$i,'post_title'=>'Helpwork '.ucfirst($kind).' '.strtoupper($language).' '.sprintf('%02d',$i).($kind==='problem'&&$i===7?' Beyondneedle':''),'post_excerpt'=>'Owner '.$kind.' summary '.$language.' '.$i,'post_content'=>'<h2>Owner diagnosis '.$language.'</h2><p>'.str_repeat('Owner help body '.$language.' retained. ',20).'</p><h2>Owner next step '.$language.'</h2><p>Original next-step explanation.</p>']);pll_set_post_language($id,$language);
   if($kind==='problem'){update_post_meta($id,'_vf_problem_symptom',$i%2?'access':'browser');update_post_meta($id,'_vf_problem_severity','degraded');}
   else {update_post_meta($id,'_vf_glossary_category',['playlist','access','playlist','access','security','delivery','playlist'][$i-1]);update_post_meta($id,'_vf_glossary_letter',['A','B','B','A','A','B','A'][$i-1]);update_post_meta($id,'_vf_glossary_aliases',$i===4?'Aliasneedle':'Owner alias '.$i);}
   $ids[]=$id;$urls[]=get_permalink($id);
  }
  $id=wp_insert_post(['post_type'=>$type,'post_status'=>'draft','post_title'=>'Helpwork HIDDEN '.$language,'post_content'=>'Never publish this body']);pll_set_post_language($id,$language);
  $help[$language][$kind]=['ids'=>$ids,'urls'=>$urls];
 }
}
foreach(['problem','glossary'] as $kind)foreach(range(0,6) as $i)pll_save_post_translations(['en'=>$help['en'][$kind]['ids'][$i],'zh'=>$help['zh'][$kind]['ids'][$i]]);
$pair=[];
foreach(['en','zh'] as $language){
 $existing=$language==='en'?get_page_by_path('faq',OBJECT,'page'):null;$body='';
 foreach(['Alpha','Beta'] as $group){$body.='<h2>Owner '.$group.' '.$language.'</h2>';foreach([1,2] as $number){$body.='<details><summary>Owner FAQ '.$language.' '.$group.' '.$number.'</summary><p>Owner answer '.$language.' '.$group.' '.$number.($group==='Beta'&&$number===2?' Uniqueanswer':'').' retained.</p></details>';}}
 $row=['post_type'=>'page','post_status'=>'draft','post_name'=>'faq','post_title'=>'Owner FAQ '.$language,'post_content'=>$body];if($existing)$row['ID']=$existing->ID;$id=wp_insert_post($row,true);if(is_wp_error($id))throw new RuntimeException('FAQ_SEED_FAILED');pll_set_post_language($id,$language);$pair[$language]=(int)$id;
}
pll_save_post_translations($pair);
foreach($pair as $language=>$id){wp_update_post(['ID'=>$id,'post_status'=>'publish','post_name'=>'faq']);if(get_post_field('post_name',$id)!=='faq'){global $wpdb;$wpdb->update($wpdb->posts,['post_name'=>'faq'],['ID'=>$id],['%s'],['%d']);clean_post_cache($id);}}

echo wp_json_encode(['status'=>'SEEDED','languages'=>$out,'help'=>$help]);
