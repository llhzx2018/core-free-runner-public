<?php
$posts=get_posts(['post_type'=>get_post_types(['public'=>true]),'post_status'=>'publish','posts_per_page'=>-1,'suppress_filters'=>true,'orderby'=>'ID','order'=>'ASC']);
$text=[]; foreach($posts as $p) { $text[$p->ID]=$p->post_content; }
echo wp_json_encode(['layout_sha256'=>hash('sha256',serialize(get_option('vf_theme_layout'))),'content_sha256'=>hash('sha256',serialize($text)),'provider_version'=>VF_TOOL_M3U8_VERSION,'theme_mods_sha256'=>hash('sha256',serialize(get_theme_mods())),'mounts_sha256'=>hash('sha256',serialize(vf_m3u8_mounts_data(true)))]);
