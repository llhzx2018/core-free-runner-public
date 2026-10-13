<?php
/** Synthetic runner only: public-safe routing diagnostics, never Production. */
if (!defined('ABSPATH')) { exit; }
function s01_trace_embed(string $stage, array $more = []): void {
    $uri=(string)($_SERVER['REQUEST_URI'] ?? '');
    if (!str_contains($uri, 'm3u8-embed-generator')) { return; }
    $route=function_exists('vf_toolsite_static_request_path')?(string)vf_toolsite_static_request_path():'';
    $id=function_exists('get_queried_object_id')?(int)get_queried_object_id():0;
    $post=$id>0?get_post($id):null;
    error_log('S01_ROUTE_TRACE '.wp_json_encode(array_merge([
        'stage'=>$stage,'route'=>$route,'is_page'=>is_page(),
        'query_id'=>$id,'actual_slug'=>$post instanceof WP_Post?(string)$post->post_name:'',
        'actual_content_shortcode'=>$post instanceof WP_Post?has_shortcode((string)$post->post_content,'vf_m3u8_embed'):false,
        'provider_registered'=>shortcode_exists('vf_m3u8_embed'),
        'alias_core'=>function_exists('vf_theme_template_family_has_core_page')?vf_theme_template_family_has_core_page($route):null,
        'pub_render_loaded'=>function_exists('vf_theme_render_public_route_module_page'),
        'renderer_hit'=>(string)($GLOBALS['vf_toolsite_renderer_hit']??''),
    ],$more),JSON_UNESCAPED_SLASHES));
}
add_action('template_redirect',static function():void{s01_trace_embed('before_all_redirect');},-1000000);
add_action('template_redirect',static function():void{s01_trace_embed('after_redirect');},99999);
add_filter('template_include',static function($template){
    s01_trace_embed('template_include',['template'=>basename((string)$template)]);
    return $template;
},99999);
add_action('get_header',static function():void{
    $names=array_map(static fn($e)=>(string)($e['function']??''),debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS,12));
    s01_trace_embed('get_header',['callers'=>array_slice($names,0,11)]);
},1);
add_action('get_footer',static function():void{
    s01_trace_embed('get_footer');
},1);
add_action('shutdown',static function():void{s01_trace_embed('shutdown');},99);

