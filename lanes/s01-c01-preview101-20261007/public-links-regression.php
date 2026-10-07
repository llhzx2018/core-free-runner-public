<?php
// HTTP-only proof surface outside the catalog; never packaged in Theme.
add_action('template_redirect',static function(){
    if(!isset($_GET['vf_public_links_proof']))return;
    $source='<p><a href="/wp-admin/">Dashboard</a> <a href="http://127.0.0.1:18880/wp-admin/admin-post.php?a=1">Private action</a> <a href="/wp-%61dmin/">Encoded admin</a> <a href="admin-ajax.php">Ajax</a> <a href="javascript:alert(1)">Script</a> <a href="/tools/?q=one&amp;sort=title#list">Tools</a> <a href="https://example.org/guide?x=1&amp;y=2">External</a> <a href="#section">Section</a> <a href="mailto:reader@example.invalid">Email</a></p>';
    if(isset($_GET['feed'])) {$GLOBALS['wp_query']->is_feed=true;}
    status_header(200);header('Content-Type: application/json');
    echo wp_json_encode(['source_sha256'=>hash('sha256',$source),'filtered'=>vf_theme_public_content_link_targets_filter($source),'source'=>$source,'admin'=>is_admin(),'feed'=>is_feed()]);exit;
},-100);
