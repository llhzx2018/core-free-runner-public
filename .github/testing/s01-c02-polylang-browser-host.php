<?php
// Disposable test host only. No new product route and no guard implementation.
function s01_browser_control(): array {
    $control=get_option('s01_c02_isolated_package_content_control');
    if (!is_array($control)) { throw new RuntimeException('Synthetic control missing'); }
    return $control;
}
function s01_browser_snapshot(): array {
    $control=s01_browser_control();
    $rows=[];
    foreach ((array)$control['ids'] as $id) {
        clean_post_cache((int)$id);
        $p=get_post((int)$id);
        if (!$p instanceof WP_Post) { throw new RuntimeException('Synthetic content missing'); }
        $map=pll_get_post_translations((int)$id);ksort($map,SORT_STRING);
        $rows[(int)$id]=['status'=>$p->post_status,'slug'=>$p->post_name,'title'=>$p->post_title,
            'content'=>$p->post_content,'parent'=>(int)$p->post_parent,
            'language'=>pll_get_post_language((int)$id),'translations'=>$map,
            'canonical'=>get_post_meta((int)$id,'rank_math_canonical_url',true),
            'sentinel'=>get_post_meta((int)$id,'_s01_install_sentinel',true)];
    }
    ksort($rows,SORT_NUMERIC);
    return $rows;
}
function s01_browser_source(): void {
    if (!function_exists('vf_ops_multilingual_slug_cleaner_handle_post')) {
        require_once WP_PLUGIN_DIR.'/vf-ops/includes/multilingual-slug-cleaner-service.php';
    }
    if (!function_exists('vf_ops_render_multilingual_slug_cleaner_tab')) {
        require_once WP_PLUGIN_DIR.'/vf-ops/includes/multilingual-slug-cleaner/02-view.php';
    }
}
add_action('admin_menu',static function() {
    add_management_page('Synthetic language guard host','Synthetic language guard host','manage_options',
        's01-language-guard-fixture',static function() {
            s01_browser_source();
            $writes=0;
            $observe=static function($sql) use (&$writes) {
                if (preg_match('/^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b/i',$sql)) { ++$writes; }
                return $sql;
            };
            add_filter('query',$observe,PHP_INT_MAX);
            ob_start();
            try { vf_ops_render_multilingual_slug_cleaner_tab(); $body=(string)ob_get_contents(); }
            finally { ob_end_clean();remove_filter('query',$observe,PHP_INT_MAX); }
            $preserved=s01_browser_snapshot()===s01_browser_control()['snapshot'];
            echo '<div class="wrap"><h1>语言清理安全提示 · 隔离组件验收</h1>';
            echo '<p>测试承载页；原始视图、样式及处理器来自完整安装的精确候选。</p>';
            echo '<div class="vf-ops-admin vf-ops-admin-shell" data-vf-ops-tab="content_languages" data-vf-ops-asset-mode="current">'.$body.'</div>';
            echo '<div id="s01-browser-control" data-preserved="'.($preserved?'1':'0').'" data-render-writes="'.(int)$writes.'"></div></div>';
        });
});
add_action('admin_enqueue_scripts',static function($hook) {
    if ($hook!=='tools_page_s01-language-guard-fixture') { return; }
    foreach (['current/admin-current-maintenance.css','current/pages/content_languages.css'] as $index=>$path) {
        wp_enqueue_style('s01-isolated-component-'.$index,
            plugins_url('assets/css/'.$path,WP_PLUGIN_DIR.'/vf-ops/vf-ops.php'),[],null);
    }
});
add_action('admin_post_s01_language_guard_fixture',static function() {
    // Native WordPress authentication already selected this authenticated hook.
    // Envelope prevents unrelated product controllers from consuming the test
    // request before the real handler is invoked. It contains no mock guard.
    if ((string)($_GET['phase']??'')==='nonce') {
        wp_send_json(['nonce'=>wp_create_nonce('vf_ops_multilingual_slug_cleaner_action')]);
    }
    s01_browser_source();
    $saved=$_POST;
    $_POST=is_array($saved['s01_payload']??null)?$saved['s01_payload']:[];
    $writes=0;$pageWrites=0;
    $observe=static function($sql) use (&$writes,&$pageWrites) {
        if (preg_match('/^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b/i',$sql)) {
            ++$writes;
            global $wpdb;
            foreach ([$wpdb->posts,$wpdb->postmeta,$wpdb->term_relationships,$wpdb->term_taxonomy] as $table) {
                if (str_contains($sql,$table)) { ++$pageWrites;break; }
            }
        }
        return $sql;
    };
    add_filter('query',$observe,PHP_INT_MAX);
    try { $result=vf_ops_multilingual_slug_cleaner_handle_post(); }
    finally { remove_filter('query',$observe,PHP_INT_MAX);$_POST=$saved; }
    wp_send_json(['status'=>$result===null?'NULL':(string)($result['status']??''),
        'sql_writes'=>$writes,'page_write_queries'=>$pageWrites,
        'content_preserved'=>s01_browser_snapshot()===s01_browser_control()['snapshot'],
        'production_mutated'=>false]);
});
