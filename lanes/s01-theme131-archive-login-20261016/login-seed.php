<?php
$author=wp_insert_user(['user_login'=>'private-mixed-author','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Private Mix Owner']);
$only=wp_insert_user(['user_login'=>'private-only-author','user_pass'=>wp_generate_password(),'role'=>'author','display_name'=>'Private Only Owner']);$out=[];
foreach(['en','zh'] as $language){$public=[];
 for($n=1;$n<=10;$n++){$id=wp_insert_post(['post_type'=>'post','post_status'=>$n<=3?'publish':'private','post_author'=>$author,'post_name'=>'privacy-mixed-'.$language.'-'.$n,'post_title'=>'Privacy fixture '.$n,'post_content'=>'Original owner article body '.$n,'post_excerpt'=>'Original owner excerpt '.$n,'post_date'=>($n<=3?'2024-01-04':'2024-01-03').' 12:00:00']);pll_set_post_language($id,$language);if($n<=3)$public[]=$id;}
 foreach(['private','draft'] as $status){$id=wp_insert_post(['post_type'=>'post','post_status'=>$status,'post_author'=>$only,'post_name'=>'privacy-only-'.$language.'-'.$status,'post_title'=>'Hidden private or draft source','post_content'=>'Retained body','post_date'=>'2024-02-03 12:00:00']);pll_set_post_language($id,$language);}
 $home=pll_home_url($language);$url=static function($id)use($home){return rtrim($home,'/').'/'.ltrim(preg_replace('#^/zh/#','/',wp_parse_url(get_author_posts_url($id),PHP_URL_PATH)),'/');};$out[$language]=['url'=>$url($author),'only'=>$url($only),'public_urls'=>array_map('get_permalink',$public)];
}
echo wp_json_encode($out);
