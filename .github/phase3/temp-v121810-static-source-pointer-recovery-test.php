<?php
if (!defined('ABSPATH')) { define('ABSPATH', __DIR__ . '/'); }
if (!defined('VF_OPS_VERSION')) { define('VF_OPS_VERSION', '1.21.810'); }
$GLOBALS['vf_test_options_v121810'] = [];

function sanitize_key($key): string { return strtolower(preg_replace('/[^a-z0-9_\-]/i', '', (string)$key)); }
function sanitize_text_field($value): string { return trim((string)$value); }
function current_time($type='mysql') { return $type === 'mysql' ? '2026-09-04 21:30:00' : time(); }
function is_admin(): bool { return true; }
function current_user_can($cap): bool { return $cap === 'manage_options'; }
function get_option($key, $default=false) { return $GLOBALS['vf_test_options_v121810'][$key] ?? $default; }
function update_option($key, $value, $autoload=false): bool { $GLOBALS['vf_test_options_v121810'][$key] = $value; return true; }

final class VF_Test_WPDB_V121810 {
    public string $options = 'wp_options';
    public function esc_like($s): string { return addcslashes((string)$s, '_%\\'); }
    public function prepare($query, ...$args): string { return (string)$query; }
    public function get_col($query): array {
        $out = [];
        foreach (array_keys($GLOBALS['vf_test_options_v121810']) as $name) {
            if (str_starts_with($name, 'vf_ops_release_async_job_') && !str_starts_with($name, 'vf_ops_release_async_job_debug_')) { $out[] = $name; }
        }
        return array_reverse($out);
    }
}
$GLOBALS['wpdb'] = new VF_Test_WPDB_V121810();

require __DIR__ . '/../../includes/site-release/s01-static-boundary-reconciler.php';

function must_v121810(bool $ok, string $message): void { if (!$ok) { fwrite(STDERR, "FAIL: $message\n"); exit(1); } }
function reset_v121810(): void { $GLOBALS['vf_test_options_v121810'] = []; }
function job_key_v121810(string $id): string { return 'vf_ops_release_async_job_' . $id; }
function make_source_v121810(string $bytes): array {
    $dir = sys_get_temp_dir() . '/vf-v121810-' . bin2hex(random_bytes(5)); mkdir($dir, 0700, true);
    $path = $dir . '/source.zip'; file_put_contents($path, $bytes);
    return [$path, hash_file('sha256', $path), $dir];
}
function inspection_job_v121810(string $id, string $path): array {
    return ['id'=>$id,'job_mode'=>'inspect_only','status'=>'DONE','inspection_complete'=>true,'error'=>'','source_path'=>$path,'source_name'=>'source.zip','steps'=>[['status'=>'PASS'],['status'=>'PASS'],['status'=>'WARN']]];
}
function failed_candidate_v121810(string $id, string $sha='', string $lineage=''): array {
    return ['id'=>$id,'job_mode'=>'candidate','status'=>'FAIL','error'=>'candidate failure','source_path'=>'/missing/current/source.zip','source_name'=>'source.zip','source_inspection_sha256'=>$sha,'promoted_from_inspection_job'=>$lineage,'steps'=>[['status'=>'FAIL']]];
}
function set_record_v121810(string $active, string $sha=''): void {
    $GLOBALS['vf_test_options_v121810']['vf_toolsite_cf_static_release_records_v1'] = [
        'active_release_job'=>$active,'candidate_async_job'=>$active,'upload_mode'=>'candidate','status'=>'BLOCKED',
        'source_package_name'=>'source.zip','source_sha256'=>$sha,'source_package_sha256'=>$sha,
        'candidate_async_error'=>'candidate failure','candidate_path'=>'/missing/candidate.zip','candidate_package_name'=>'old-candidate.zip',
        'candidate_package_sha256'=>str_repeat('a',64),'sha256'=>str_repeat('a',64),'download_url'=>'x','generation_result'=>'FAIL',
    ];
}

$dirs=[];
try {
    reset_v121810();
    [$p,$sha,$d]=make_source_v121810('trusted-source-one'); $dirs[]=$d;
    set_record_v121810('cand-1',$sha);
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('cand-1')]=failed_candidate_v121810('cand-1',$sha,'inspect-1');
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('inspect-1')]=inspection_job_v121810('inspect-1',$p);
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='SOURCE_POINTER_RECOVERED' && ($r['basis']??'')==='candidate_lineage','lineage recovery');
    $record=get_option('vf_toolsite_cf_static_release_records_v1',[]);
    must_v121810(($record['active_release_job']??'')==='inspect-1' && ($record['candidate_async_job']??'')==='inspect-1','pointer readback');
    must_v121810(($record['upload_mode']??'')==='inspect_only' && ($record['status']??'')==='PARTIAL','inspection state');
    must_v121810(($record['source_sha256']??'')===$sha && ($record['sha256']??'')==='','source hash preserved / candidate hash cleared');
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='CURRENT_SOURCE_AVAILABLE','idempotent current source');

    reset_v121810();
    [$p2,$sha2,$d2]=make_source_v121810('trusted-source-two'); $dirs[]=$d2;
    set_record_v121810('cand-2',$sha2);
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('cand-2')]=failed_candidate_v121810('cand-2','');
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('inspect-2')]=inspection_job_v121810('inspect-2',$p2);
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='SOURCE_POINTER_RECOVERED' && ($r['basis']??'')==='bounded_unique_hash_match','unique fallback recovery');

    reset_v121810();
    [$pa,$shaa,$da]=make_source_v121810('same-source'); $dirs[]=$da;
    [$pb,$shab,$db]=make_source_v121810('same-source'); $dirs[]=$db;
    must_v121810($shaa===$shab,'fixture hash');
    set_record_v121810('cand-3',$shaa);
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('cand-3')]=failed_candidate_v121810('cand-3','');
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('inspect-a')]=inspection_job_v121810('inspect-a',$pa);
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('inspect-b')]=inspection_job_v121810('inspect-b',$pb);
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='AMBIGUOUS_TRUSTED_INSPECTION_SOURCE' && ($r['matchedCount']??0)===2,'ambiguous sources block');
    must_v121810((get_option('vf_toolsite_cf_static_release_records_v1',[])['active_release_job']??'')==='cand-3','ambiguous pointer unchanged');

    reset_v121810();
    [$px,$shax,$dx]=make_source_v121810('trusted-source-x'); $dirs[]=$dx;
    set_record_v121810('cand-4',str_repeat('b',64));
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('cand-4')]=failed_candidate_v121810('cand-4','', 'inspect-x');
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('inspect-x')]=inspection_job_v121810('inspect-x',$px);
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='NO_TRUSTED_INSPECTION_SOURCE','hash mismatch blocks');

    reset_v121810(); set_record_v121810('cand-5','');
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('cand-5')]=failed_candidate_v121810('cand-5','');
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='SOURCE_HASH_AUTHORITY_MISSING','missing hash authority blocks');

    reset_v121810();
    [$pf,$shaf,$df]=make_source_v121810('trusted-source-fail'); $dirs[]=$df;
    set_record_v121810('cand-6',$shaf);
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('cand-6')]=failed_candidate_v121810('cand-6',$shaf,'inspect-fail');
    $bad=inspection_job_v121810('inspect-fail',$pf); $bad['steps'][]=['status'=>'FAIL'];
    $GLOBALS['vf_test_options_v121810'][job_key_v121810('inspect-fail')]=$bad;
    $r=vf_ops_s01_static_source_pointer_recover_v121810();
    must_v121810(($r['code']??'')==='NO_TRUSTED_INSPECTION_SOURCE','failed inspection blocks');

    echo "PASS_V121810_STATIC_SOURCE_POINTER_RECOVERY\n";
} finally {
    foreach($dirs as $dir){ foreach(glob($dir.'/*')?:[] as $file){@unlink($file);} @rmdir($dir); }
}
