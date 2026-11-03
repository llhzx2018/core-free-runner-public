<?php
// Executed only inside the disposable local WordPress/MariaDB test site.
// Never use outside the isolated Runner. No production data is read or written.
if (!defined('ABSPATH') || !defined('WP_CLI') || !WP_CLI) {
    throw new RuntimeException('This content fixture requires isolated WP CLI');
}
$origin=(string)home_url('/');
if (!in_array((string)wp_parse_url($origin, PHP_URL_HOST), ['localhost','127.0.0.1'], true)) {
    throw new RuntimeException('Refusing non-local WordPress');
}
$ids=[];
foreach (['1440','768','peer'] as $suffix) {
    $name='R8 Ops Core Save Fixture '.$suffix;
    $id=wp_insert_post([
        'post_type'=>'post','post_status'=>'draft','post_author'=>1,
        'post_title'=>$name,'post_name'=>'s01-r8-ops-core-'.$suffix,
        'post_content'=>'Temporary isolated WordPress fixture for genuine reversible Ops admin form actions.'
    ], true);
    if (is_wp_error($id) || (int)$id <= 0) {
        throw new RuntimeException('Cannot create Ops content fixture '.$suffix);
    }
    $ids[$suffix]=(int)$id;
    update_post_meta((int)$id, '_vf_ops_workflow_status','draft');
    delete_post_meta((int)$id, '_vf_ops_is_core');
}
$targetDir='/tmp/s01-r8-ops-save-evidence';
if (!is_dir($targetDir) && !mkdir($targetDir, 0755, true) && !is_dir($targetDir)) {
    throw new RuntimeException('Cannot create isolated test evidence directory');
}
$json=wp_json_encode(['ids'=>$ids,'search'=>'R8 Ops Core Save Fixture'], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
if (!$json || !file_put_contents($targetDir.'/fixture.json', $json)) {
    throw new RuntimeException('Cannot emit isolated content fixture IDs');
}
echo 'S01_R8_OPS_CONTENT_FIXTURE_PASS posts='.count($ids).' workflow=draft core=none'.PHP_EOL;
