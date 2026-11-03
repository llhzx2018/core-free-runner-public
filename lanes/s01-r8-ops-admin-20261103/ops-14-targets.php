<?php
// WordPress WP-CLI eval-file only: a private-source, localhost-only route
// projection. It has no mutations and does not expose auth/nonce/credentials.
if (!defined('ABSPATH') || !defined('WP_CLI') || !WP_CLI) { throw new RuntimeException('WP CLI context required'); }
$base=(string)home_url('/');
$host=(string)wp_parse_url($base,PHP_URL_HOST);
if (!in_array($host,['127.0.0.1','localhost'],true)) { throw new RuntimeException('Refusing non-local Ops browser fixture'); }
if (!function_exists('vf_ops_v13_route_contract_v121391')) {
    require_once WP_PLUGIN_DIR.'/vf-tools-ops/includes/admin-v13/route-contract.php';
}
$routes=vf_ops_v13_route_contract_v121391();
if (count($routes)!==13) { throw new RuntimeException('Ops route denominator changed: '.count($routes)); }
if (!function_exists('vf_ops_v13_route_url_v121391')) { throw new RuntimeException('Missing Ops route URL owner'); }
$out=[];
foreach ($routes as $key=>$meta) {
    $key=(string)$key;
    $url=(string)vf_ops_v13_route_url_v121391($key);
    $parts=wp_parse_url($url);
    $query=[];
    parse_str((string)($parts['query']??''),$query);
    if (($parts['host']??'')!==$host || ($query['page']??'')!==(string)($meta['page']??'')) {
        throw new RuntimeException('Ops canonical local target mismatch '.$key);
    }
    $out[]=[
        'key'=>$key,
        'url'=>$url,
        'page'=>(string)$meta['page'],
        'label'=>(string)($meta['label']??$key),
        'capability'=>(string)($meta['capability']??'manage_options'),
        'sensitive'=>in_array($key,['publish_zip','system_plugins','system_recovery','integrations'],true),
    ];
}
$toolsUrl=function_exists('vf_ops_s01_tool_workbench_url_v1')
    ? (string)vf_ops_s01_tool_workbench_url_v1()
    : (string)admin_url('admin.php?page=vf-toolsite-tools');
$toolsParts=wp_parse_url($toolsUrl);$toolsQuery=[];
parse_str((string)($toolsParts['query']??''),$toolsQuery);
if (($toolsParts['host']??'')!==$host || ($toolsQuery['page']??'')!=='vf-toolsite-tools') {
    throw new RuntimeException('Ops tool workbench route does not resolve locally');
}
$out[]=['key'=>'tools','url'=>$toolsUrl,'page'=>'vf-toolsite-tools',
        'label'=>'工具工作台','capability'=>'manage_options','sensitive'=>false];
if (count($out)!==14 || count(array_unique(array_column($out,'key')))!==14) {
    throw new RuntimeException('Ops 14-surface contract drift');
}
$dir='/tmp/s01-r8-ops-admin-evidence';
if(!is_dir($dir)&&!mkdir($dir,0755,true)&&!is_dir($dir))throw new RuntimeException('Evidence path unavailable');
if(!file_put_contents($dir.'/ops-targets.json',wp_json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_PRETTY_PRINT))){
    throw new RuntimeException('Cannot write local Ops browser targets');
}
echo 'S01_R8_OPS_CANONICAL_ADMIN_TARGETS_PASS total='.count($out).' sensitive=4'.PHP_EOL;
