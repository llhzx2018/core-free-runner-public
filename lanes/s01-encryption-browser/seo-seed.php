<?php
global $wpdb;
$ids=$wpdb->get_col($wpdb->prepare("SELECT ID FROM {$wpdb->posts} WHERE post_type = %s AND post_status = %s AND post_name = %s",'page','publish','m3u8-encryption-detector'));
$rows=array_filter(array_map('get_post', $ids));
$found=[];
foreach($rows as $p){$lang=pll_get_post_language($p->ID);if(!in_array($lang,['en','zh'],true))continue;update_post_meta($p->ID,'rank_math_description',$lang==='zh'?'Synthetic Chinese encryption description for diagnostic.':'Synthetic English encryption description for diagnostic.');$found[$lang]=$p->ID;}
if(count($found)!==2)throw new RuntimeException('FIXTURE_PAIR_MISSING');echo wp_json_encode($found);
