<?php
$rows=get_posts(['post_type'=>'page','post_status'=>'publish','name'=>'m3u8-encryption-detector','posts_per_page'=>-1,'suppress_filters'=>true]);
$found=[];
foreach($rows as $p){$lang=pll_get_post_language($p->ID);if(!in_array($lang,['en','zh'],true))continue;update_post_meta($p->ID,'rank_math_description',$lang==='zh'?'Synthetic Chinese encryption description for diagnostic.':'Synthetic English encryption description for diagnostic.');$found[$lang]=$p->ID;}
if(count($found)!==2)throw new RuntimeException('FIXTURE_PAIR_MISSING');echo wp_json_encode($found);
