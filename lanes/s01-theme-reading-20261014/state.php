<?php
$posts=get_posts(['post_type'=>'post','post_status'=>'publish','posts_per_page'=>-1,'suppress_filters'=>true,'orderby'=>'ID','order'=>'ASC']);
$text=[]; foreach($posts as $p) { $text[$p->ID]=$p->post_content; }
echo wp_json_encode(['layout_sha256'=>hash('sha256',serialize(get_option('vf_theme_layout'))),'content_sha256'=>hash('sha256',serialize($text)),'provider_version'=>VF_TOOL_M3U8_VERSION]);
