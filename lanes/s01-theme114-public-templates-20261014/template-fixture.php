<?php
// Isolated synthetic WordPress only. This file is never part of the theme ZIP.
add_action('template_redirect', static function(): void {
    if (!isset($_GET['vf_template_fixture'])) { return; }
    $kind = sanitize_key((string)$_GET['vf_template_fixture']);
    if (!function_exists('vf_theme_available_contexts') || !in_array($kind, vf_theme_available_contexts(), true)) {
        status_header(404); exit;
    }
    $post = $kind === 'tool' ? get_page_by_path('m3u8-browser-stream-test', OBJECT, 'page') : get_page_by_path('s01-template-'.$kind, OBJECT, 'post');
    if (!$post instanceof WP_Post) { status_header(500); echo 'SYNTHETIC_FIXTURE_MISSING'; exit; }
    global $wp_query;
    $wp_query->is_404 = false;
    $wp_query->is_search = false;
    $wp_query->is_archive = false;
    $wp_query->is_home = false;
    $wp_query->is_page = false;
    $wp_query->is_single = true;
    $wp_query->is_singular = true;
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
    $route=$routes[$kind] ?? 's01-template-'.$kind;
    $context=['route'=>$route,'family'=>vf_theme_template_family_for_route($route),'title'=>$post->post_title,'description'=>'Synthetic template summary: browser tasks and reading content.','module_key'=>$kind==='tool'?'browser_stream_test':'','field_data'=>['title'=>$post->post_title,'description'=>'Synthetic template summary: browser tasks and reading content.','module_key'=>$kind==='tool'?'browser_stream_test':'']];
    status_header(200);
    get_header();
    echo '<div data-vf-fixture-context="'.esc_attr($kind).'">';
    vf_theme_render_module_stack($context,$kind);
    echo '</div>';
    get_footer();
    exit;
}, -100);
