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

// Reproduce the live legacy post whose public route is a Problem, not a term.
foreach(['en','zh'] as $language){
 $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_name'=>'m3u8-cors-error-explained','post_title'=>'Wrong Explained Problem '.strtoupper($language),'post_excerpt'=>'Legacy troubleshooting record','post_content'=>'<p>Preserved legacy problem body.</p>']);pll_set_post_language($id,$language);update_post_meta($id,'_fixture_owned_problem',true);
 $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_name'=>'termwork-glossary-'.$language,'post_title'=>'Termwork Glossary '.strtoupper($language),'post_excerpt'=>'An authored glossary definition','post_content'=>'<p>Preserved glossary definition.</p>']);pll_set_post_language($id,$language);
}

$basic=[];
foreach(['en','zh'] as $language){
 foreach(['basicwork','basicempty','basiclong'] as $kind){
  $body=$kind==='basicempty'?'':($kind==='basicwork'?'<h2>Owner page heading</h2><p>Owner basic body '.$language.' retained.</p>':'<h2>Owner long section</h2><p>'.str_repeat('Owner long page text '.$language.'. ',250).'</p><h2>Owner table</h2><table><tr><th>Setting</th><th>Value</th></tr><tr><td>Address</td><td>https://example.invalid/'.str_repeat('long-public-path-',20).'</td></tr></table><pre><code>Owner preserved code</code></pre>');
  $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>$kind.'-'.$language,'post_title'=>'Owner '.ucfirst($kind).' '.strtoupper($language),'post_content'=>$body,'post_excerpt'=>$kind==='basicempty'?'':'Owner summary '.$language.' [vf_summary_probe] retained.']);pll_set_post_language($id,$language);if($kind!=='basicwork')update_post_meta($id,'_wp_page_template','page-basic.php');$basic[$language][$kind]=get_permalink($id);
 }
}
foreach(['en','zh'] as $language){for($n=1;$n<=7;$n++){$id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_name'=>'guidework-'.$language.'-'.$n,'post_title'=>'Guidework '.$language.' '.sprintf('%02d',$n).($n===7?' Beyondguide':''),'post_excerpt'=>'Owner guide summary '.$language.' '.$n,'post_content'=>'<h2>Owner guide steps</h2><p>Owner guide body retained.</p>']);pll_set_post_language($id,$language);update_post_meta($id,'_vf_guide_task',$n%2?'inspect':'play');update_post_meta($id,'_vf_guide_difficulty',$n===7?'advanced':'beginner');}}
$mount_cases=[];
foreach(['en','zh'] as $language){
 $cases=[];$pure=[];$preserved=[];
 foreach((require get_template_directory().'/inc/data/tool-contracts/m3u8.php')['tools'] as $tool){$cases['pure-'.$tool['slug']]=['body'=>"<!-- vf-m3u8:mount:start -->\n".$tool['shortcode']."\n<!-- vf-m3u8:mount:end -->",'pure'=>true];}
 foreach(['prose'=>'<p>Owner explanation retained.</p>[vf_m3u8_player]','attrs'=>'[vf_m3u8_player source="custom"]','multi'=>'[vf_m3u8_player][vf_m3u8_playlist_checker]','unknown'=>'[unknown_provider_tool]','suffix'=>'<p>Independent player-2 page.</p>','excerpt'=>'[vf_m3u8_player]'] as $key=>$body)$cases[$key]=['body'=>$body,'pure'=>false];
 foreach($cases as $key=>$case){$id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'mountwork-'.$key.'-'.$language,'post_title'=>'Mountwork '.$key.' '.$language,'post_content'=>$case['body'],'post_excerpt'=>$key==='excerpt'?'Owner distinct summary':'']);pll_set_post_language($id,$language);if($case['pure'])$pure[]=get_permalink($id);else $preserved[]=get_permalink($id);}
 $mount_cases[$language]=['pure'=>$pure,'preserved'=>$preserved];
}
$archive_cases=[];
$author=wp_insert_user(['user_login'=>'archive-owner','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Owner Atlas & Co']);
$other=wp_insert_user(['user_login'=>'archive-other','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Boundary Other']);
$empty_author=wp_insert_user(['user_login'=>'archive-empty','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Owner Empty']);
foreach(['en','zh'] as $language){
 $ids=[];$bydate=['2022-01-03'=>[],'2022-01-04'=>[],'2022-02-03'=>[],'2023-01-03'=>[],'2022-04-03'=>[]];
 for($n=1;$n<=12;$n++){
  $date=$n<=6?'2022-01-03':($n<=8?'2022-01-04':($n===9?'2022-02-03':($n===10?'2023-01-03':($n===11?'2022-01-03':'2022-04-03'))));
  $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_author'=>$n<=10?$author:$other,'post_name'=>'archivework-'.$language.'-'.$n,'post_title'=>'Archivework '.strtoupper($language).' '.sprintf('%02d',$n).($n%2?' Needlescope':''),'post_content'=>'<p>Original archive body '.$language.' '.$n.' retained.'.($n===1?' Bodyonlyneedle':'').'</p>','post_excerpt'=>'Owner archive summary '.$language.' '.$n,'post_date'=>$date.' 12:00:00']);pll_set_post_language($id,$language);$bydate[$date][]=$id;if($n<=10)$ids[]=$id;
 }
 foreach(['draft','private'] as $status){$id=wp_insert_post(['post_type'=>'post','post_status'=>$status,'post_author'=>$author,'post_title'=>'Archivework HIDDEN '.strtoupper($language),'post_content'=>'Must never be a public archive card','post_date'=>'2022-01-03 12:00:00']);pll_set_post_language($id,$language);}
 $id=wp_insert_post(['post_type'=>'post','post_status'=>'private','post_author'=>$author,'post_title'=>'Archivework HIDDEN PRIVATE ONLY '.strtoupper($language),'post_content'=>'Cannot establish a public date archive','post_date'=>'2020-01-03 12:00:00']);pll_set_post_language($id,$language);
 $home=pll_home_url($language);
 $author_url=(string)get_author_posts_url($author);$empty_url=(string)get_author_posts_url($empty_author);
 $author_path=wp_parse_url($author_url,PHP_URL_PATH);$empty_path=wp_parse_url($empty_url,PHP_URL_PATH);
 $author_url=rtrim($home,'/').'/'.ltrim(preg_replace('#^/zh/#','/',$author_path),'/');$empty_url=rtrim($home,'/').'/'.ltrim(preg_replace('#^/zh/#','/',$empty_path),'/');
 $archive_cases[$language]=['author'=>['url'=>$author_url,'ids'=>$ids,'name'=>'Owner Atlas & Co'], 'year'=>['url'=>rtrim($home,'/').'/2022/','ids'=>array_merge($bydate['2022-01-03'],$bydate['2022-01-04'],$bydate['2022-02-03'],$bydate['2022-04-03'])], 'month'=>['url'=>rtrim($home,'/').'/2022/01/','ids'=>array_merge($bydate['2022-01-03'],$bydate['2022-01-04'])], 'day'=>['url'=>rtrim($home,'/').'/2022/01/03/','ids'=>$bydate['2022-01-03']], 'empty_author'=>$empty_url];
 foreach(['author','year','month','day'] as $kind){$archive_cases[$language][$kind]['urls']=array_map('get_permalink',$archive_cases[$language][$kind]['ids']);}
}

$mixed_author=wp_insert_user(['user_login'=>'archive-mixed','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Mixed Owner']);
$shell_author=wp_insert_user(['user_login'=>'archive-shells','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Shell Owner']);
$markers=['Redirecting...', 'HTTP-EQUIV="refresh"', "http-equiv='refresh'", 'LoCaTiOn . HREF = target'];
foreach(['en','zh'] as $language){
 $home=pll_home_url($language);$shell_ids=[];
 // More than one candidate batch, interleaved with real public records.
 for($n=1;$n<=107;$n++){
  $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_author'=>$author,'post_name'=>'archive-shell-'.$language.'-'.$n,'post_title'=>'Retained shell '.$n,'post_content'=>$markers[$n%4].' Needlescope','post_excerpt'=>'Retained original shell excerpt','post_date'=>'2022-01-03 12:00:00']);pll_set_post_language($id,$language);$shell_ids[]=$id;
 }
 // A broad SQL hint is never an exclusion verdict.
 $benign=(int)$archive_cases[$language]['author']['ids'][1];
 wp_update_post(['ID'=>$benign,'post_content'=>'A redirect policy describes http-headers and location documentation. Original article retained.']);
 foreach(['category','post_tag'] as $tax){
  $name=($tax==='category'?'Archive category ':'Archive tag ').strtoupper($language);
  $term=wp_insert_term($name,$tax,['slug'=>'archive-'.($tax==='category'?'category':'tag').'-'.$language]);
  $term_id=(int)$term['term_id'];pll_set_term_language($term_id,$language);
  foreach(array_merge($archive_cases[$language]['author']['ids'],$shell_ids) as $id)wp_set_object_terms((int)$id,[$term_id],$tax,true);
  $kind=$tax==='category'?'category':'tag';$archive_cases[$language][$kind]=['url'=>get_term_link($term_id,$tax),'ids'=>$archive_cases[$language]['author']['ids'],'urls'=>$archive_cases[$language]['author']['urls']];
 }
 $mixed=[];
 for($n=1;$n<=10;$n++){
  $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_author'=>$mixed_author,'post_name'=>'archive-mixed-'.$language.'-'.$n,'post_title'=>'Mixed archive '.$n,'post_content'=>$n<=3?'A complete public article.':$markers[$n%4],'post_excerpt'=>'Original authored excerpt','post_date'=>($n<=3?'2021-01-04':'2021-01-03').' 12:00:00']);pll_set_post_language($id,$language);if($n<=3)$mixed[]=$id;
 }
 $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_author'=>$shell_author,'post_name'=>'archive-shell-only-'.$language,'post_title'=>'Retained shell-only author','post_content'=>'Redirecting...','post_date'=>'2019-01-03 12:00:00']);pll_set_post_language($id,$language);
 $author_path=wp_parse_url(get_author_posts_url($mixed_author),PHP_URL_PATH);$only_path=wp_parse_url(get_author_posts_url($shell_author),PHP_URL_PATH);
 $archive_cases[$language]['mixed']=['url'=>rtrim($home,'/').'/'.ltrim(preg_replace('#^/zh/#','/',$author_path),'/'),'ids'=>$mixed,'urls'=>array_map('get_permalink',$mixed)];
 $archive_cases[$language]['only_shells']=rtrim($home,'/').'/'.ltrim(preg_replace('#^/zh/#','/',$only_path),'/');
 $archive_cases[$language]['retained_shell_ids']=$shell_ids;
}

echo wp_json_encode(['status'=>'SEEDED','languages'=>$out,'help'=>$help,'basic'=>$basic,'mount_cases'=>$mount_cases,'archives'=>$archive_cases]);
