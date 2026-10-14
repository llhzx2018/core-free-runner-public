<?php
// Isolated synthetic WordPress only. This file is never part of the theme ZIP.
add_action('template_redirect', static function(): void {
    if (!isset($_GET['vf_template_fixture'])) { return; }
    if (function_exists('vf_theme_public_runtime_require_template_stack')) {
        vf_theme_public_runtime_require_template_stack();
    }
    $kind = sanitize_key((string)$_GET['vf_template_fixture']);
    if (!function_exists('vf_theme_available_contexts') || !in_array($kind, vf_theme_available_contexts(), true)) {
        status_header(404); exit;
    }
    $lang=str_starts_with((string)($_SERVER['REQUEST_URI']??''),'/zh/')?'zh':'en';
    $post=get_page_by_path('s01-template-'.$kind.'-'.$lang,OBJECT,'post');
    $variant=sanitize_key((string)($_GET['reading_variant']??'short'));
    $width=sanitize_key((string)($_GET['reading_width']??'focused'));
    add_filter('option_vf_theme_layout',static function($layout) use($variant,$width,$kind) {
        foreach(['articleReading','guideReading'] as $key) {
            $layout[$key]['reading_width']=$width;
            if($variant==='off')$layout[$key]['tocPosition']='off';
        }
        if($variant==='disabled')$layout['toc']['enabled']=false;
        if($variant==='context-off')$layout['toc']['contexts'][$kind]=false;
        if($variant==='levels-off')$layout['toc']['levels']=['h2'=>false,'h3'=>false];
        return $layout;
    });
    if($post instanceof WP_Post){
        $post=clone $post;
        if($variant==='long')$post->post_content.='<p>'.str_repeat('More content with real readable words. ',40).'</p>';
        if($variant==='legacy')$post->post_content.='<div class="ez-toc-container">Existing table of contents</div>';
    }
    if (!$post instanceof WP_Post) { status_header(500); echo 'SYNTHETIC_FIXTURE_MISSING'; exit; }
    global $wp_query;
    $wp_query->is_404 = false;
    $wp_query->is_search = false;
    $wp_query->is_archive = false;
    $wp_query->is_home = false;
    $wp_query->is_page = false;
    $wp_query->is_single = true;
    $wp_query->is_singular = true;
    $wp_query->posts=[$post]; $wp_query->post_count=1; $wp_query->current_post=-1;
    $wp_query->post=$post; $wp_query->in_the_loop=false;
    $wp_query->queried_object = $post;
    $wp_query->queried_object_id = (int)$post->ID;
    $GLOBALS['post']=$post;
    setup_postdata($post);
    add_filter('body_class', static function(array $classes) use ($kind): array {
        $classes=array_values(array_filter($classes,static fn($c)=>!str_starts_with($c,'vf-page-family-context--')));
        $classes[]='vf-page-family-context--'.$kind;
        return $classes;
    }, 999);
    $routes=['home'=>'','tool'=>'m3u8-browser-stream-test','tool_hub'=>'tools','blog_index'=>'blog','guide_index'=>'guides','problem_index'=>'problems','archive_list'=>'archive','glossary_index'=>'glossary','html_sitemap'=>'sitemap','faq_page'=>'faq','legal'=>'privacy-policy','contact_page'=>'contact','about_page'=>'about','search'=>'search','not_found'=>'404'];
    $route=['guide_detail'=>'guides/s01-reading-fixture','article_detail'=>'blog/s01-reading-fixture','problem_detail'=>'problems/s01-reading-fixture','glossary_detail'=>'glossary/s01-reading-fixture'][$kind] ?? ($routes[$kind] ?? 's01-template-'.$kind);
    $GLOBALS['vf_toolsite_render_route']=$route;
    $context=['route'=>$route,'family'=>vf_theme_template_family_for_route($route),'title'=>$post->post_title,'description'=>'Synthetic template summary: browser tasks and reading content.','module_key'=>$kind==='tool'?'browser_stream_test':'','field_data'=>['title'=>$post->post_title,'description'=>'Synthetic template summary: browser tasks and reading content.','module_key'=>$kind==='tool'?'browser_stream_test':'']];
    status_header(200);
    get_header();
    $wp_query->posts=[$post]; $wp_query->post_count=1; $wp_query->post=$post; $wp_query->rewind_posts(); $GLOBALS['post']=$post;
    $probe=['current_post'=>$wp_query->current_post,'post_count'=>$wp_query->post_count,'raw_bytes'=>strlen($post->post_content),'filtered_bytes'=>strlen((string)apply_filters('the_content',$post->post_content)),'get_content_bytes'=>strlen((string)get_the_content(null,false,$post))];
    echo '<div data-vf-fixture-context="'.esc_attr($kind).'">';
    vf_theme_render_module_stack($context,$kind);
    $probe['after_current_post']=$wp_query->current_post;
    echo '<script type="application/json" id="s01-reading-query-probe">'.wp_json_encode($probe).'</script>';
    echo '</div>';
    get_footer();
    exit;
}, -1000003);
