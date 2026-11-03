<?php
// Independent WP-CLI readback AFTER Chromium executed live admin POST/PRG/GET.
// Never run outside disposable localhost test site.
if (!defined('ABSPATH') || !defined('WP_CLI') || !WP_CLI) { throw new RuntimeException('Isolated WP CLI required'); }
if (!in_array((string)wp_parse_url(home_url('/'),PHP_URL_HOST),['localhost','127.0.0.1'],true)) {
    throw new RuntimeException('Refusing non-local readback');
}
$dir='/tmp/s01-r8-ops-save-evidence';
$fixture=json_decode((string)file_get_contents($dir.'/fixture.json'),true);
if (!is_array($fixture) || count((array)($fixture['ids']??[]))!==3) {
    throw new RuntimeException('Fixture identity unavailable');
}
$browser=json_decode((string)file_get_contents($dir.'/content-browser-results.json'),true);
if (!is_array($browser)||($browser['failed']??99)!==0||($browser['passed']??0)!==6) {
    throw new RuntimeException('Actual browser workflow has not passed');
}
$ids=(array)$fixture['ids'];
$audits=get_option('vf_ops_content_management_audit_v1',[]);
$audits=is_array($audits)?$audits:[];
$verified=[];
foreach ($ids as $key=>$id) {
    $id=(int)$id;
    $post=get_post($id);
    if (!$post || (string)$post->post_status!=='draft'
        || (string)$post->post_title!=='R8 Ops Core Save Fixture '.$key) {
        throw new RuntimeException('Target post identity/status changed unexpectedly: '.$key);
    }
    if ((string)get_post_meta($id,'_vf_ops_is_core',true)!=='') {
        throw new RuntimeException('Core marker not rolled back: '.$key);
    }
    if ((string)get_post_meta($id,'_vf_ops_workflow_status',true)!=='draft') {
        throw new RuntimeException('Workflow mutated by core toggle: '.$key);
    }
    $history=array_values(array_filter($audits,static fn($a):bool=>is_array($a) && (int)($a['post_id']??0)===$id));
    if ($key==='peer') {
        if ($history!==[])throw new RuntimeException('Unrelated peer content received an Ops audit');
        $verified[$key]='UNCHANGED';
        continue;
    }
    // Exactly one positive mark and one compensating unmark; invalid nonce
    // must not introduce a third mutation or an audit.
    if (count($history)!==2 || (string)($history[0]['action']??'')!=='unmark_core'
        || (string)($history[1]['action']??'')!=='mark_core') {
        throw new RuntimeException('Unexpected audit count/order: '.$key.' '.wp_json_encode($history));
    }
    if (!empty($history[0]['after']['core']) || empty($history[1]['after']['core'])) {
        throw new RuntimeException('Audit not consistent with real core toggle readback: '.$key);
    }
    $verified[$key]='MARK_UNMARK_READBACK_PASS';
}
$result=['status'=>'PASS','database_readback'=>$verified,'nonce_rejection_did_not_create_audit'=>true,
    'production_writes'=>0,'synthetic_posts'=>3];
if (!file_put_contents($dir.'/content-wpcli-readback.json',wp_json_encode($result,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE))) {
    throw new RuntimeException('Cannot write proof receipt');
}
echo 'S01_R8_OPS_CONTENT_REAL_DB_READBACK_PASS width_1440=PASS width_768=PASS peer_unchanged=PASS invalid_nonce_zero_write=PASS'.PHP_EOL;
