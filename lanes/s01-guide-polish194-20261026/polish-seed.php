<?php
// Give synthetic guides a real edited timestamp so visible-date formatting is exercised.
foreach(get_posts(['post_type'=>'vf_guide','post_status'=>'publish','numberposts'=>-1,'suppress_filters'=>true])as$post){
 if(!str_starts_with($post->post_name,'guide-desktop-'))continue;
 $result=wp_update_post(['ID'=>$post->ID,'post_excerpt'=>$post->post_excerpt],true);
 if(is_wp_error($result))throw new RuntimeException('POLISH_DATE_FIXTURE_FAILED');
 if(get_post_field('post_modified',$post->ID)===get_post_field('post_date',$post->ID))throw new RuntimeException('POLISH_DATE_FIXTURE_NO_EDIT');
}
