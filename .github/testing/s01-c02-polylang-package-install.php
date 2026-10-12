<?php
// Synthetic WordPress only. No Production, database export, cookies or licensed files.
$phase = (string)($args[0] ?? '');
$controlKey = 's01_c02_isolated_package_content_control';
$plugin = WP_PLUGIN_DIR . '/vf-ops';
function s01_install_content_snapshot(array $ids): array {
    $rows = [];
    foreach ($ids as $id) {
        clean_post_cache((int)$id);
        $p = get_post((int)$id);
        if (!$p instanceof WP_Post) { throw new RuntimeException('Synthetic page missing'); }
        $map = pll_get_post_translations((int)$id);
        ksort($map, SORT_STRING);
        $rows[(int)$id] = [
            'status'=>$p->post_status, 'slug'=>$p->post_name,
            'title'=>$p->post_title, 'content'=>$p->post_content,
            'parent'=>(int)$p->post_parent,
            'language'=>pll_get_post_language((int)$id),
            'translations'=>$map,
            'canonical'=>get_post_meta((int)$id,'rank_math_canonical_url',true),
            'sentinel'=>get_post_meta((int)$id,'_s01_install_sentinel',true),
        ];
    }
    ksort($rows, SORT_NUMERIC);
    return $rows;
}
if ($phase === 'setup') {
    wp_set_current_user((int)get_user_by('login','admin')->ID);
    foreach ([['en_US','English','en'],['zh_CN','Chinese','zh']] as $language) {
        $r = new WP_REST_Request('POST','/pll/v1/languages');
        $r->set_param('locale',$language[0]);
        $r->set_param('name',$language[1]);
        $r->set_param('slug',$language[2]);
        $response = rest_do_request($r);
        if ($response->get_status()>=400) { throw new RuntimeException('Synthetic language setup failed'); }
    }
    $en=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Synthetic EN','post_name'=>'s01-install-en','post_content'=>'SYNTHETIC EN CONTENT']);
    $zh=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Synthetic ZH official','post_name'=>'s01-install-zh','post_content'=>'SYNTHETIC ZH CONTENT']);
    $old=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Synthetic ZH duplicate','post_name'=>'s01-install-zh-2','post_content'=>'SYNTHETIC OLD CONTENT']);
    foreach ([$en,$zh,$old] as $id) {
        if (is_wp_error($id) || (int)$id<=0) { throw new RuntimeException('Synthetic page creation failed'); }
        update_post_meta((int)$id,'_s01_install_sentinel','KEEP SYNTHETIC CONTENT');
        update_post_meta((int)$id,'rank_math_canonical_url',home_url('/synthetic-canonical-'.(int)$id.'/'));
    }
    pll_set_post_language((int)$en,'en');
    pll_set_post_language((int)$zh,'zh');
    pll_set_post_language((int)$old,'zh');
    pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$old]);
    $ids=[(int)$en,(int)$zh,(int)$old];
    update_option($controlKey,['ids'=>$ids,'snapshot'=>s01_install_content_snapshot($ids)],false);
    echo "S01_C02_PACKAGE_CONTENT_CONTROL_READY\n";
    return;
}
if (!in_array($phase,['baseline','candidate','rollback'],true)) {
    throw new RuntimeException('Unknown disposable package test phase');
}
require_once ABSPATH.'wp-admin/includes/plugin.php';
if (!is_plugin_active('vf-ops/vf-ops.php') || !defined('VF_OPS_VERSION')) {
    throw new RuntimeException('Exact full plugin is not active at expected test identity');
}
$contract=json_decode((string)file_get_contents('/tmp/s01-install-contract.json'),true,512,JSON_THROW_ON_ERROR);
$expected=(array)$contract[$phase==='candidate'?'candidate':'baseline'];
if (VF_OPS_VERSION!==(string)$expected['version']) { throw new RuntimeException('Installed package version differs from exact contract'); }
$files=(array)$expected['files'];
ksort($files,SORT_STRING);
$runtimeHash=hash_init('sha256');
foreach ($files as $rel=>$hash) {
    if ($rel==='' || str_starts_with($rel,'/') || in_array('..',explode('/',$rel),true)) {
        throw new RuntimeException('Unsafe installation contract path');
    }
    $path=$plugin.'/'.$rel;
    if (!is_file($path) || is_link($path) || !hash_equals($hash,hash_file('sha256',$path))) {
        throw new RuntimeException('Installed runtime differs from exact package: '.$rel);
    }
    hash_update($runtimeHash,$rel."\0".$hash."\n");
}
if (!hash_equals((string)$expected['runtime_fingerprint'],hash_final($runtimeHash))) {
    throw new RuntimeException('Installed runtime fingerprint differs');
}
$control=get_option($controlKey);
if (!is_array($control) || s01_install_content_snapshot($control['ids'])!==$control['snapshot']) {
    throw new RuntimeException('Install/replace/rollback changed synthetic page state, content, canonical or translations');
}
$summary=['phase'=>$phase,'runtime_files'=>count($files),'all_runtime_bytes_match'=>true,
    'synthetic_pages_preserved'=>3,'content_and_translation_preserved'=>true,'production'=>'NOT_EXECUTED',
    'same_version_package_test'=>$contract['candidate']['version']===$contract['baseline']['version'],'formal_update_discovery_tested'=>false];
if ($phase==='candidate') {
    if (!function_exists('vf_ops_multilingual_slug_cleaner_handle_post')) {
        require_once $plugin.'/includes/multilingual-slug-cleaner/01-service-actions.php';
    }
    $admin=(int)get_user_by('login','admin')->ID;
    $editor=wp_insert_user(['user_login'=>'s01-synthetic-editor','user_pass'=>wp_generate_password(32,true),
        'user_email'=>'editor@example.invalid','role'=>'editor']);
    if (is_wp_error($editor)) { throw new RuntimeException('Synthetic editor setup failed'); }
    $oldPost=$_POST;
    $oldGet=$_GET;
    $oldMethod=$_SERVER['REQUEST_METHOD']??null;
    $cases=0;
    $queryWrites=0;
    $observe=static function($query) use (&$queryWrites) {
        if (preg_match('/^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b/i',$query)) { ++$queryWrites; }
        return $query;
    };
    $exercise=static function(array $post,string $expectedStatus,int $actor,bool $getOnly=false) use (&$cases,&$queryWrites,$observe,$control) {
        wp_set_current_user($actor);
        $_POST=$post;
        $_GET=$getOnly?['vf_ops_multilingual_slug_cleaner_action'=>'repair_all']:[];
        $_SERVER['REQUEST_METHOD']=$getOnly?'GET':'POST';
        $queryWrites=0;
        add_filter('query',$observe,PHP_INT_MAX);
        try { $result=vf_ops_multilingual_slug_cleaner_handle_post(); }
        finally { remove_filter('query',$observe,PHP_INT_MAX); }
        $actual=$result===null?'NULL':(string)($result['status']??'');
        if ($actual!==$expectedStatus || $queryWrites!==0) {
            throw new RuntimeException('Actual endpoint rejection was not zero-write: '.$expectedStatus.' / '.$actual);
        }
        if (s01_install_content_snapshot($control['ids'])!==$control['snapshot']) {
            throw new RuntimeException('Rejected actual endpoint changed synthetic page data');
        }
        ++$cases;
    };
    try {
        $exercise([],'NULL',$admin,true);
        wp_set_current_user((int)$editor);
        $exercise(['vf_ops_multilingual_slug_cleaner_action'=>'repair_all',
            '_wpnonce'=>wp_create_nonce('vf_ops_multilingual_slug_cleaner_action'),
            'vf_ops_confirm_multilingual_write'=>'1'],'FAIL',(int)$editor);
        wp_set_current_user($admin);
        $exercise(['vf_ops_multilingual_slug_cleaner_action'=>'repair_selected',
            '_wpnonce'=>'invalid-synthetic-nonce','vf_ops_confirm_multilingual_write'=>'1',
            'post_ids'=>[$control['ids'][2]]],'FAIL',$admin);
        $exercise(['vf_ops_multilingual_slug_cleaner_action'=>'repair_all',
            'vf_ops_confirm_multilingual_write'=>'1'],'FAIL',$admin);
        foreach (['repair_selected','repair_all','trash_archived_duplicates','rollback_last_batch'] as $action) {
            $exercise(['vf_ops_multilingual_slug_cleaner_action'=>$action,
                '_wpnonce'=>wp_create_nonce('vf_ops_multilingual_slug_cleaner_action'),
                'post_ids'=>[$control['ids'][2]]],'BLOCKED',$admin);
        }
        foreach (['0','true','yes'] as $invalidConfirmation) {
            $exercise(['vf_ops_multilingual_slug_cleaner_action'=>'repair_all',
                '_wpnonce'=>wp_create_nonce('vf_ops_multilingual_slug_cleaner_action'),
                'vf_ops_confirm_multilingual_write'=>$invalidConfirmation],'BLOCKED',$admin);
        }
        // Fully authorized POST must still stop on actual free Polylang.
        $_GET=[];
        $_POST=['vf_ops_multilingual_slug_cleaner_action'=>'repair_selected',
            '_wpnonce'=>wp_create_nonce('vf_ops_multilingual_slug_cleaner_action'),
            'vf_ops_confirm_multilingual_write'=>'1','post_ids'=>[$control['ids'][2]]];
        $_SERVER['REQUEST_METHOD']='POST';
        $noPro=vf_ops_multilingual_slug_cleaner_handle_post();
        if (($noPro['status']??'')!=='BLOCKED'
            || s01_install_content_snapshot($control['ids'])!==$control['snapshot']) {
            throw new RuntimeException('Full installed plugin did not block no-Pro mutation');
        }
        $scan=vf_ops_multilingual_slug_cleaner_scan(100);
        foreach ((array)($scan['issues']??[]) as $issue) {
            if (($issue['repair_mode']??'')==='archive_duplicate_redirect'
                && (!empty($issue['repairable']) || ($issue['stage']??'')==='READY_ARCHIVE_DUPLICATE')) {
                throw new RuntimeException('Actual free-plugin scan falsely advertises duplicate archival readiness');
            }
        }
        // Actual PHP rendering; not browser UX PASS.
        if (!function_exists('vf_ops_render_multilingual_slug_cleaner_tab')) {
            require_once $plugin.'/includes/multilingual-slug-cleaner/02-view.php';
        }
        ob_start();
        try { vf_ops_render_multilingual_slug_cleaner_tab(); $html=(string)ob_get_contents(); }
        finally { ob_end_clean(); }
        foreach (['只导出规则不会自动安装','旧地址是否已真实返回正确的 301','翻译关系'] as $text) {
            if (!str_contains($html,$text)) { throw new RuntimeException('Installed PHP safety explanation missing'); }
        }
        $summary['endpoint_rejection_cases']=$cases;
        $summary['rejected_endpoint_sql_writes']=0;
        $summary['authorized_no_pro_is_blocked']=true;
        $summary['actual_php_safety_prompts']=true;
        $summary['browser_ui_pass']=false;
        echo 'S01_C02_REAL_ENDPOINT_SECURITY_PASS '.wp_json_encode($summary)."\n";
    } finally {
        $_POST=$oldPost; $_GET=$oldGet;
        if ($oldMethod===null) { unset($_SERVER['REQUEST_METHOD']); }
        else { $_SERVER['REQUEST_METHOD']=$oldMethod; }
        wp_set_current_user($admin);
    }
}
echo 'S01_C02_PACKAGE_LIFECYCLE_PHASE_PASS '.wp_json_encode($summary)."\n";
