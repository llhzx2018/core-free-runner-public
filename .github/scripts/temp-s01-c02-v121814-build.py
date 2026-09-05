from pathlib import Path
import subprocess, sys

BASE='bd2fb0f84a39cbbbdc0c4d999397c4c7c0f82f44'
EXPECTED_HEAD='428441a333c2314ca3c6dc0a453d36ef74421e53'

def sh(*args):
    return subprocess.check_output(args, text=True).strip()

def replace_once(path, old, new):
    p=Path(path); s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f'{path}: anchor count={n}')
    p.write_text(s.replace(old,new,1))

if sh('git','rev-parse','HEAD') != EXPECTED_HEAD:
    raise SystemExit('candidate head drift')
if sh('git','merge-base','HEAD',BASE) != BASE:
    raise SystemExit('candidate base drift')

replace_once(
    'includes/content-model/lifecycle-service.php',
    "$cleanup = vf_ops_lifecycle_cleanup_volatile_v121377(true);\n        $seoSchema = function_exists('vf_ops_seo_schema_install_v121439')",
    "$cleanup = vf_ops_lifecycle_cleanup_volatile_v121377(false);\n        $seoSchema = function_exists('vf_ops_seo_schema_install_v121439')"
)

create_method = r'''
    /**
     * V1.21.814: create an inspect-only job from a server-side source whose
     * bytes already match an independently persisted source SHA authority.
     * This is not a generic filesystem importer and never skips ZIP safety or
     * source inspection.
     */
    public static function create_inspection_from_trusted_source_v121814(string $trusted_path, string $source_name, string $expected_sha): string {
        if (!current_user_can('manage_options')) { throw new RuntimeException('权限不足，不能恢复静态源包。'); }
        $expected_sha = strtolower(trim($expected_sha));
        if (preg_match('/^[a-f0-9]{64}$/', $expected_sha) !== 1) { throw new RuntimeException('静态源包 SHA Authority 无效。'); }
        $trusted_path = trim($trusted_path);
        if ($trusted_path === '' || !is_file($trusted_path) || !is_readable($trusted_path) || is_link($trusted_path)) {
            throw new RuntimeException('受信静态源包不存在或不可读取。');
        }
        $actual_sha = strtolower((string)@hash_file('sha256', $trusted_path));
        if (preg_match('/^[a-f0-9]{64}$/', $actual_sha) !== 1 || !hash_equals($expected_sha, $actual_sha)) {
            throw new RuntimeException('受信静态源包与持久化 SHA Authority 不一致。');
        }
        VF_Ops_Release_Zip::assert_available();
        $job_id = function_exists('wp_generate_uuid4') ? wp_generate_uuid4() : uniqid('vf_source_recover_', true);
        $job_id = preg_replace('/[^a-z0-9_\-]/i', '', (string)$job_id);
        $job_dir = rtrim(self::upload_dir(), '/\\') . '/' . $job_id;
        if (!is_dir($job_dir) && (!function_exists('wp_mkdir_p') || !wp_mkdir_p($job_dir))) {
            throw new RuntimeException('恢复 inspection job 私有目录创建失败。');
        }
        $new_source = $job_dir . '/source.zip';
        if (!@copy($trusted_path, $new_source)) {
            @rmdir($job_dir);
            throw new RuntimeException('恢复静态源包复制失败。');
        }
        @chmod($new_source, 0600);
        $copied_sha = strtolower((string)@hash_file('sha256', $new_source));
        if (preg_match('/^[a-f0-9]{64}$/', $copied_sha) !== 1 || !hash_equals($expected_sha, $copied_sha)) {
            @unlink($new_source); @rmdir($job_dir);
            throw new RuntimeException('恢复静态源包复制后 SHA 回读不一致。');
        }
        try {
            $created = self::create_job_from_source_file($job_id, $new_source, $source_name, '', 'check_static_zip');
            $job = self::load($created);
            if (!$job || (string)($job['job_mode'] ?? '') !== 'inspect_only') { throw new RuntimeException('恢复 inspection job 回读失败。'); }
            $job['source_recovery_basis'] = 'simply_static_sha_exact_v121814';
            $job['source_recovery_expected_sha256'] = $expected_sha;
            self::save($job);
            return $created;
        } catch (Throwable $e) {
            if (is_file($new_source)) { @unlink($new_source); }
            @rmdir($job_dir);
            throw $e;
        }
    }

'''
p=Path('includes/release/async-job-parts/01-job-create-trait.php'); s=p.read_text()
anchor='    public static function create_candidate_from_inspection_v121761(string $inspection_job_id): string {'
if s.count(anchor)!=1: raise SystemExit('create trait anchor mismatch')
p.write_text(s.replace(anchor,create_method+anchor,1))

run_method = r'''
    /**
     * V1.21.814: execute exactly one stage of a recovered inspect-only job
     * through the same per-job execution lock used by the AJAX worker.
     */
    public static function run_recovery_inspection_stage_v121814(string $job_id, string $expected_sha): array {
        $job_id = preg_replace('/[^a-z0-9_\-]/i', '', $job_id);
        $expected_sha = strtolower(trim($expected_sha));
        if ($job_id === '' || preg_match('/^[a-f0-9]{64}$/', $expected_sha) !== 1) {
            return ['status'=>'FAIL','code'=>'RECOVERY_JOB_IDENTITY_INVALID'];
        }
        $job = self::load($job_id);
        if (!$job || (string)($job['job_mode'] ?? '') !== 'inspect_only') {
            return ['status'=>'FAIL','code'=>'RECOVERY_JOB_NOT_INSPECTION'];
        }
        $source = trim((string)($job['source_path'] ?? ''));
        $actual_sha = $source !== '' && is_file($source) && is_readable($source) ? strtolower((string)@hash_file('sha256', $source)) : '';
        if (preg_match('/^[a-f0-9]{64}$/', $actual_sha) !== 1 || !hash_equals($expected_sha, $actual_sha)) {
            return ['status'=>'FAIL','code'=>'RECOVERY_SOURCE_SHA_MISMATCH'];
        }
        $status = strtoupper((string)($job['status'] ?? ''));
        if ($status === 'DONE') {
            return ['status'=>'DONE','code'=>'RECOVERY_INSPECTION_DONE','inspection_complete'=>!empty($job['inspection_complete'])];
        }
        if (self::is_terminal_status_v121351($status, true)) {
            return ['status'=>'FAIL','code'=>'RECOVERY_INSPECTION_TERMINAL'];
        }
        $lock = self::acquire_run_lock_v121305($job_id, $job);
        if (empty($lock['acquired'])) { return ['status'=>'BUSY','code'=>'RECOVERY_WORKER_BUSY']; }
        try {
            $fresh = self::load($job_id);
            if ($fresh) { $job = $fresh; }
            $source = trim((string)($job['source_path'] ?? ''));
            $actual_sha = $source !== '' && is_file($source) && is_readable($source) ? strtolower((string)@hash_file('sha256', $source)) : '';
            if (preg_match('/^[a-f0-9]{64}$/', $actual_sha) !== 1 || !hash_equals($expected_sha, $actual_sha)) {
                return ['status'=>'FAIL','code'=>'RECOVERY_SOURCE_SHA_CHANGED'];
            }
            $job = self::run_next_stage($job);
            $job = self::normalize_ready_running_job($job);
            self::save($job);
            $job = self::load($job_id) ?: $job;
            self::sync_record($job);
            return [
                'status'=>strtoupper((string)($job['status'] ?? 'FAIL')),
                'code'=>'RECOVERY_STAGE_COMPLETE',
                'inspection_complete'=>!empty($job['inspection_complete']),
                'current_stage'=>max(0,(int)($job['current_stage'] ?? 0)),
            ];
        } catch (Throwable $e) {
            $job['status'] = 'FAIL';
            $job['error'] = 'Static Source Recovery V2 inspection stage failed.';
            $job['next'] = 'Recovery remains fail-closed.';
            self::save($job);
            self::sync_record($job);
            return ['status'=>'FAIL','code'=>'RECOVERY_STAGE_EXCEPTION'];
        } finally {
            if (!empty($lock['token'])) { self::release_run_lock_v121305($job_id, (string)$lock['token'], 's01_source_recovery_v2'); }
        }
    }

'''
p=Path('includes/release/async-job-parts/03-job-state-trait.php'); s=p.read_text()
anchor='    public static function ajax_status(): void {'
if s.count(anchor)!=1: raise SystemExit('state trait anchor mismatch')
p.write_text(s.replace(anchor,run_method+anchor,1))

p=Path('includes/site-release/s01-static-candidate-readiness.php'); s=p.read_text()
old="    $manualSourceUploadRequired = $seoCandidateReady\n        && $runtimeReady\n        && !$candidateReady\n        && !$sourceAvailable\n        && !in_array($jobStatus, ['RUNNING','PAUSED'], true);\n\n    $nextBoundary = 'SEO_CANDIDATE_NOT_READY';"
new="    $manualSourceUploadRequired = $seoCandidateReady\n        && $runtimeReady\n        && !$candidateReady\n        && !$sourceAvailable\n        && !in_array($jobStatus, ['RUNNING','PAUSED'], true);\n    $sourceRecovery = function_exists('vf_ops_s01_static_source_recovery_v2_marker_v121814')\n        ? (array)vf_ops_s01_static_source_recovery_v2_marker_v121814() : [];\n    $sourceRecoveryCurrent = $sourceRecovery && defined('VF_OPS_VERSION')\n        && hash_equals((string)VF_OPS_VERSION, (string)($sourceRecovery['pluginVersion'] ?? ''));\n\n    $nextBoundary = 'SEO_CANDIDATE_NOT_READY';"
if s.count(old)!=1: raise SystemExit('readiness model anchor mismatch')
s=s.replace(old,new,1)
old="        'manualSourceUploadRequired'=>$manualSourceUploadRequired,\n        'nextBoundary'=>$nextBoundary,\n        'finalOnlinePass'=>'NO',"
new="        'manualSourceUploadRequired'=>$manualSourceUploadRequired,\n        'nextBoundary'=>$nextBoundary,\n        'sourceRecoveryStatus'=>$sourceRecoveryCurrent ? sanitize_key((string)($sourceRecovery['status'] ?? '')) : 'not_verified',\n        'sourceRecoveryCode'=>$sourceRecoveryCurrent ? sanitize_key((string)($sourceRecovery['code'] ?? '')) : '',\n        'sourceRecoveryBasis'=>$sourceRecoveryCurrent ? sanitize_key((string)($sourceRecovery['basis'] ?? '')) : '',\n        'sourceRecoveryMatchedCount'=>$sourceRecoveryCurrent ? max(0,(int)($sourceRecovery['matchedCount'] ?? 0)) : 0,\n        'sourceRecoveryZipCandidateCount'=>$sourceRecoveryCurrent ? max(0,(int)($sourceRecovery['zipCandidateCount'] ?? 0)) : 0,\n        'sourceRecoveryHashAuthorityPresent'=>$sourceRecoveryCurrent && !empty($sourceRecovery['sourceHashAuthorityPresent']),\n        'sourceRecoveryDirectoryAvailable'=>$sourceRecoveryCurrent && !empty($sourceRecovery['sourceDirectoryAvailable']),\n        'sourceRecoveryWorkerStatus'=>$sourceRecoveryCurrent ? sanitize_key((string)($sourceRecovery['workerStatus'] ?? '')) : '',\n        'sourceRecoveryMarkerCurrent'=>(bool)$sourceRecoveryCurrent,\n        'finalOnlinePass'=>'NO',"
if s.count(old)!=1: raise SystemExit('readiness return anchor mismatch')
p.write_text(s.replace(old,new,1))

p=Path('includes/site-release/s01-static-source-recovery-v2.php'); s=p.read_text()
old="    $state = vf_ops_s01_static_source_recovery_v2_state_v121814();\n    $jobId = preg_replace('/[^a-z0-9_\\-]/i', '', (string)($state['jobId'] ?? ''));"
new="    $record = vf_ops_s01_static_source_recovery_v2_record_v121814();\n    $activeId = preg_replace('/[^a-z0-9_\\-]/i', '', (string)($record['active_release_job'] ?? $record['candidate_async_job'] ?? ''));\n    if ($activeId !== '') {\n        $activeJob = VF_Ops_Release_Async_Job::load($activeId);\n        $activeSource = is_array($activeJob) ? trim((string)($activeJob['source_path'] ?? '')) : '';\n        if ($activeSource !== '' && is_file($activeSource) && is_readable($activeSource)) {\n            vf_ops_s01_static_source_recovery_v2_store_marker_v121814('current','CURRENT_SOURCE_AVAILABLE','current_active_job',1,0,true,true,'');\n            return ['status'=>'PASS','code'=>'CURRENT_SOURCE_AVAILABLE'];\n        }\n    }\n\n    $state = vf_ops_s01_static_source_recovery_v2_state_v121814();\n    $jobId = preg_replace('/[^a-z0-9_\\-]/i', '', (string)($state['jobId'] ?? ''));"
if s.count(old)!=1: raise SystemExit('current source anchor mismatch')
s=s.replace(old,new,1)
s=s.replace("vf_ops_s01_static_source_recovery_v2_store_marker_v121814('blocked','STATIC_RUNTIME_NOT_READY','','0',0,false,false,'failed');","vf_ops_s01_static_source_recovery_v2_store_marker_v121814('blocked','STATIC_RUNTIME_NOT_READY','',0,0,false,false,'failed');",1)
p.write_text(s)

Path('VERSION').write_text('1.21.814\n')
p=Path('vf-ops.php'); s=p.read_text()
for old,new in [
    (' * Version: 1.21.813',' * Version: 1.21.814'),
    ("define('VF_OPS_VERSION', '1.21.813')","define('VF_OPS_VERSION', '1.21.814')"),
    ("define('VF_OPS_ROUND', 'M3U8-AUTHORITY-REBIND-GUARD-V1')","define('VF_OPS_ROUND', 'STATIC-SOURCE-RECOVERY-V2')"),
]:
    if s.count(old)!=1: raise SystemExit(f'vf-ops identity anchor mismatch: {old}')
    s=s.replace(old,new,1)
anchor="require_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-boundary-reconciler.php';"
if s.count(anchor)!=1: raise SystemExit('vf-ops service anchor mismatch')
s=s.replace(anchor,anchor+"\nrequire_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-source-recovery-v2.php';",1)
p.write_text(s)

print('PATCH_V121814_OK')
