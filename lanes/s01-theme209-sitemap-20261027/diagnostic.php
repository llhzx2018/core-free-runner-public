<?php
// Synthetic fixture only, never copied into the Theme package or Production.
add_action('wp_footer',static function(){
 if(!str_contains($_SERVER['REQUEST_URI']??'','/sitemap/'))return;
 $lang=vf_toolsite_multilingual_request_language_code();$id=vf_theme_public_route_contract_find_exact_published_post_id_for_route_language('sitemap',$lang);$p=vf_toolsite_static_route_existing_post('sitemap');
 echo '<script type="application/json" id="sitemap-fixture-diagnostic">'.wp_json_encode(['language'=>$lang,'exact_id'=>$id,'exact_title'=>$id?get_post_field('post_title',$id,'raw'):'','existing_id'=>$p->ID??0,'queried_id'=>get_queried_object_id(),'compiled_title'=>vf_theme_template_family_core_page('sitemap')['title']??'']).'</script>';
},999);
