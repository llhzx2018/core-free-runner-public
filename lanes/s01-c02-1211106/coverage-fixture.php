<?php
// Runs only inside the disposable database explicitly created by this lane.
if (getenv('S01_SLUG_ISOLATED') !== '1' || DB_NAME !== 'vf_ops_slug_coverage'
    || home_url() !== 'http://127.0.0.1:18106') {
    throw new RuntimeException('Synthetic coverage environment identity mismatch');
}
require_once WP_PLUGIN_DIR.'/vf-ops/includes/multilingual-slug-cleaner-service.php';
function s01_coverage_assert(bool $ok, string $name): void {
    if (!$ok) { throw new RuntimeException('Coverage gate failed: '.$name); }
    echo 'PASS '.$name."\n";
}
function s01_coverage_fingerprint(): string {
    global $wpdb;
    $rows=$wpdb->get_results("SELECT ID,post_type,post_status,post_name,post_title,post_content,post_modified FROM {$wpdb->posts} ORDER BY ID", ARRAY_A);
    $meta=$wpdb->get_results("SELECT post_id,meta_key,meta_value FROM {$wpdb->postmeta} ORDER BY meta_id", ARRAY_A);
    $terms=$wpdb->get_results("SELECT object_id,term_taxonomy_id,term_order FROM {$wpdb->term_relationships} ORDER BY object_id,term_taxonomy_id", ARRAY_A);
    return hash('sha256',wp_json_encode([$rows,$meta,$terms]));
}
function s01_coverage_scan(int $limit): array {
    global $wpdb;
    $before=s01_coverage_fingerprint();$writes=0;
    $observe=static function($sql) use (&$writes) {
        if (preg_match('/^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b/i',$sql)) { ++$writes; }
        return $sql;
    };
    $queryStart=$wpdb->num_queries;$started=microtime(true);
    add_filter('query',$observe,PHP_INT_MAX);
    try { $result=vf_ops_multilingual_slug_cleaner_scan($limit); }
    finally { remove_filter('query',$observe,PHP_INT_MAX); }
    $metrics=['limit'=>$limit,'scanned'=>$result['scanned_count'],'query_count'=>$wpdb->num_queries-$queryStart,
        'seconds'=>round(microtime(true)-$started,4),'sql_writes'=>$writes];
    s01_coverage_assert($writes===0 && s01_coverage_fingerprint()===$before,'native scan is zero-write and preserves content/meta/languages');
    s01_coverage_assert($result['scanned_count']<=max(50,min(3000,$limit)),'native scan respects inspected-object budget');
    echo 'SCAN_METRICS '.wp_json_encode($metrics)."\n";
    return $result;
}
function s01_coverage_add(int $number): int {
    $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Synthetic clean '.$number,
        'post_name'=>'s01-clean-'.dechex($number).'z','post_content'=>'SYNTHETIC COVERAGE CONTENT '.$number],true);
    if (is_wp_error($id) || !$id) { throw new RuntimeException('Synthetic post insert failed'); }
    pll_set_post_language((int)$id,'en');
    delete_post_meta((int)$id,'_vf_source_slug');
    return (int)$id;
}
$phase=(string)($args[0]??'coverage');
if ($phase==='issue') {
    $ids=(array)get_option('s01_slug_coverage_ids',[]);
    s01_coverage_assert(count($ids)===3001,'issue phase retains exact synthetic inventory');
    wp_update_post(['ID'=>$ids[0],'post_name'=>'s01-browser-collision-2']);
    update_option('s01_c02_isolated_package_content_control',['ids'=>array_slice($ids,0,3),'snapshot'=>[]],false);
    $control=get_option('s01_c02_isolated_package_content_control');
    $control['snapshot']=s01_browser_snapshot();update_option('s01_c02_isolated_package_content_control',$control,false);
    $scan=s01_coverage_scan(500);
    s01_coverage_assert($scan['issue_count']===1 && $scan['repairable_count']===1 && !$scan['scan_complete'],'native Pro issue phase has one bounded candidate');
    return;
}
wp_set_current_user((int)get_user_by('login','admin')->ID);
foreach ([['en_US','English','en'],['zh_CN','Chinese','zh']] as $language) {
    $r=new WP_REST_Request('POST','/pll/v1/languages');
    foreach (['locale','name','slug'] as $i=>$key) { $r->set_param($key,$language[$i]); }
    $response=rest_do_request($r);
    s01_coverage_assert($response->get_status()<400,'native licensed language creation');
}
$state=vf_ops_multilingual_slug_cleaner_polylang_state();
s01_coverage_assert(!empty($state['can_write_shared_slug']),'actual licensed Pro detected');
foreach (get_posts(['post_type'=>vf_ops_multilingual_slug_cleaner_post_types(),'post_status'=>'any','numberposts'=>-1,'fields'=>'ids','lang'=>'','suppress_filters'=>false]) as $id) {
    wp_delete_post((int)$id,true);
}
$ids=[];wp_defer_term_counting(true);
for ($i=1;$i<=50;++$i) { $ids[]=s01_coverage_add($i); }
$exact=s01_coverage_scan(50);
s01_coverage_assert($exact['status']==='PASS' && $exact['scan_complete'] && $exact['scanned_count']===50,'50/50 is complete clean PASS');
$ids[]=s01_coverage_add(51);wp_update_post(['ID'=>$ids[50],'post_name'=>'s01-unseen-collision-2']);
$partial=s01_coverage_scan(50);
s01_coverage_assert($partial['status']==='WARN' && !$partial['scan_complete'] && $partial['issue_count']===0,'51st native suffix cannot hide behind complete PASS');
$found=s01_coverage_scan(51);
s01_coverage_assert($found['scan_complete'] && $found['issue_count']===1 && $found['issues'][0]['id']===$ids[50],'larger bounded scan finds exact unseen native suffix');
wp_update_post(['ID'=>$ids[50],'post_name'=>'s01-clean-33z']);
for ($i=52;$i<=501;++$i) { $ids[]=s01_coverage_add($i); }
$partial500=s01_coverage_scan(500);
s01_coverage_assert($partial500['status']==='WARN' && !$partial500['scan_complete'] && $partial500['issue_count']===0,'501 clean native objects cannot yield full-page PASS');
for ($i=502;$i<=3001;++$i) { $ids[]=s01_coverage_add($i); }
wp_defer_term_counting(false);
$before=s01_coverage_fingerprint();$pageWrites=0;
global $wpdb;
$observe=static function($sql) use (&$pageWrites,$wpdb) {
    if (preg_match('/^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b/i',$sql)) {
        foreach ([$wpdb->posts,$wpdb->postmeta,$wpdb->term_relationships,$wpdb->term_taxonomy] as $table) {
            if (str_contains($sql,$table)) { ++$pageWrites;break; }
        }
    }
    return $sql;
};
add_filter('query',$observe,PHP_INT_MAX);
try { $bulk=vf_ops_multilingual_slug_cleaner_repair([],true); }
finally { remove_filter('query',$observe,PHP_INT_MAX); }
s01_coverage_assert($bulk['status']==='PARTIAL' && !$bulk['scanBefore']['scan_complete'] && $bulk['scanBefore']['scanned_count']===3000,'real licensed repair-all cannot claim complete beyond 3000');
s01_coverage_assert($pageWrites===0 && s01_coverage_fingerprint()===$before,'partial clean bulk preserves all native content/meta/translation rows');
// Receipt writing is tested above; keep historical summary out of UI scope.
delete_option(vf_ops_multilingual_slug_cleaner_option_key());
update_option('s01_slug_coverage_ids',$ids,false);
update_option('s01_c02_isolated_package_content_control',['ids'=>array_slice($ids,0,3),'snapshot'=>[]],false);
$control=get_option('s01_c02_isolated_package_content_control');
$control['snapshot']=s01_browser_snapshot();update_option('s01_c02_isolated_package_content_control',$control,false);
$editor=wp_insert_user(['user_login'=>'s01-synthetic-editor','user_pass'=>'S01-Synthetic-Editor-Only!',
    'user_email'=>'editor@example.invalid','role'=>'editor']);
s01_coverage_assert(!is_wp_error($editor),'native editor security fixture created');
echo 'S01_NATIVE_SLUG_COVERAGE_PASS '.wp_json_encode(['result'=>'PASS','candidate_sha'=>getenv('TARGET_SHA'),
    'version'=>VF_OPS_VERSION,'inventory'=>3001,'polylang_pro'=>'3.8.2','native_scan'=>'PASS','zero_page_writes'=>'PASS',
    'bulk_partial'=>'PASS','production_write'=>false])."\n";
