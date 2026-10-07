<?php
// Only the disposable Runner database; no production content or Ops store.
wp_set_current_user(1);
$rows=[];
foreach (['guides/how-to-check-if-m3u8-is-encrypted','problems/m3u8-403-forbidden-fix','tool-notes/m3u8-player'] as $route) {
    $parent=0; $path='';
    foreach(explode('/',$route) as $slug) {
        $path=trim($path.'/'.$slug,'/'); $post=get_page_by_path($path);
        if (!$post) {
            $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_parent'=>$parent,'post_name'=>$slug,'post_title'=>'Isolated content: '.ucwords(str_replace('-',' ',$slug)),'post_content'=>'<p>This is a clearly marked disposable WordPress content record for Theme route and SEO checks. It is not production editorial content.</p><h2>Bounded route checks</h2><p>Verify the published object, canonical URL, title, description and language output without inventing a translated record.</p><h2>Next step</h2><p>Use the real installed tool only with authorized inputs. <a href="/tools/">Browse tools</a>.</p>'],true);
            if(is_wp_error($id))throw new Exception($id->get_error_message());
        } else {$id=(int)$post->ID;}
        $parent=$id;
    }
    $rows[]=['id'=>$id,'route'=>$route,'permalink'=>get_permalink($id),'post_status'=>get_post_status($id)];
}
flush_rewrite_rules(true);
echo wp_json_encode(['scope'=>'ISOLATED_WORDPRESS_OWNED_CONTENT_ONLY','rows'=>$rows,'provider'=>'ACTUAL_FORMAL_C03_1.25.57','production'=>'NOT_EXECUTED'],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);
