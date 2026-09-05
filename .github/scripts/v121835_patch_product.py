from pathlib import Path

root = Path('ops')

def read(path):
    return (root / path).read_text()

def write(path, text):
    (root / path).write_text(text)

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, got {count}')
    return text.replace(old, new, 1)

# 1) Candidate Stage-4 helper finalization: backfill first, then generate helpers once.
p = Path('includes/release/builders/class-candidate-batch-builder.php')
s = read(p)
old = """        if (empty($state['helpers_written'])) {
            $dst = new ZipArchive();
            if (class_exists('VF_Ops_Release_Zip')) {
                VF_Ops_Release_Zip::open_for_append($dst, (string)$state['candidate_path'], '大包候选包 ZIP helper 写入');
            } else {
                $result = $dst->open((string)$state['candidate_path'], ZipArchive::CREATE);
                if ($result !== true) { throw new RuntimeException('大包候选包 helper 写入阶段无法打开 ZIP：ZipArchive open 返回 ' . (string)$result); }
            }
            $html = [];
            if (is_file((string)$state['zh_home_path'])) { $html['zh/home/index.html'] = (string)file_get_contents((string)$state['zh_home_path']); }
            if (class_exists('VF_Ops_Release_Candidate_Helper_Writer')) {
                VF_Ops_Release_Candidate_Helper_Writer::write_generated_files($dst, $written, $html, [], $candidateActions, (string)$context->get('target_base_url', ''), (string)$context->get('source_base_url', ''), (string)$context->get('file.name', 'static-source.zip'));
                if (class_exists('VF_Ops_Release_Candidate_Resource_Backfiller')) {
                    VF_Ops_Release_Candidate_Resource_Backfiller::backfill($dst, $written, $candidateActions);
                    VF_Ops_Release_Candidate_Resource_Backfiller::ensure_helpers($dst, $written, $candidateActions, (string)$context->get('target_base_url', ''), (string)$context->get('source_base_url', ''), (string)$context->get('file.name', 'static-source.zip'));
                }
            }
            if ($dst->close() !== true) { throw new RuntimeException('大包候选包 ZIP 关闭失败。'); }
            $state['helpers_written'] = true;
            self::write_json((string)$state['written_path'], $written);
            self::write_json((string)$state['actions_path'], $candidateActions);
        }
"""
new = """        if (empty($state['helpers_written'])) {
            $state['helper_phase'] = 'helper_zip_open';
            $job['large_build'] = $state;
            $dst = new ZipArchive();
            try {
                if (class_exists('VF_Ops_Release_Zip')) {
                    VF_Ops_Release_Zip::open_for_append($dst, (string)$state['candidate_path'], '大包候选包 ZIP helper 写入');
                } else {
                    $result = $dst->open((string)$state['candidate_path'], ZipArchive::CREATE);
                    if ($result !== true) { throw new RuntimeException('ZipArchive open 返回 ' . (string)$result); }
                }
            } catch (Throwable $e) {
                throw new RuntimeException('大包候选包 helper 阶段失败[helper_zip_open]：' . $e->getMessage());
            }
            $closed = false;
            try {
                // V1.21.835: backfill first. The previous flow generated the entire helper
                // set, backfilled assets, then generated the same helper set again. That
                // duplicate delete/add rewrite sits exactly in the proven 231/231 helper
                // boundary and is unnecessary. Generate helpers once after backfill so
                // candidate-actions/output counts already include all backfilled assets.
                $state['helper_phase'] = 'resource_backfill';
                $job['large_build'] = $state;
                if (class_exists('VF_Ops_Release_Candidate_Resource_Backfiller')) {
                    VF_Ops_Release_Candidate_Resource_Backfiller::backfill($dst, $written, $candidateActions);
                }

                $state['helper_phase'] = 'helper_write';
                $job['large_build'] = $state;
                $html = [];
                if (is_file((string)$state['zh_home_path'])) { $html['zh/home/index.html'] = (string)file_get_contents((string)$state['zh_home_path']); }
                if (class_exists('VF_Ops_Release_Candidate_Helper_Writer')) {
                    VF_Ops_Release_Candidate_Helper_Writer::write_generated_files($dst, $written, $html, [], $candidateActions, (string)$context->get('target_base_url', ''), (string)$context->get('source_base_url', ''), (string)$context->get('file.name', 'static-source.zip'));
                }

                $state['helper_phase'] = 'helper_zip_close';
                $job['large_build'] = $state;
                if ($dst->close() !== true) { throw new RuntimeException('close returned false'); }
                $closed = true;
            } catch (Throwable $e) {
                if (!$closed) { try { $dst->close(); } catch (Throwable $ignore) {} }
                throw new RuntimeException('大包候选包 helper 阶段失败[' . (string)$state['helper_phase'] . ']：' . $e->getMessage());
            }
            $state['helper_phase'] = 'done';
            $state['helpers_written'] = true;
            self::write_json((string)$state['written_path'], $written);
            self::write_json((string)$state['actions_path'], $candidateActions);
            $job['large_build'] = $state;
        }
"""
s = replace_once(s, old, new, 'helper finalize block')
write(p, s)

# 2) Privacy-safe classifier for helper sub-phases.
p = Path('includes/site-release/s01-static-candidate-build-failure-readback-v121830.php')
s = read(p)
old = """    if ($contains('大包候选包写入失败')) { return 'candidate_zip_entry_write_failed'; }
    if ($contains('大包候选包 ZIP 关闭失败')) { return 'candidate_zip_close_failed'; }
    if ($contains('大包候选包 helper 写入阶段无法打开 ZIP')) { return 'candidate_helper_zip_open_failed'; }
"""
new = """    if ($contains('大包候选包写入失败')) { return 'candidate_zip_entry_write_failed'; }
    if ($contains('大包候选包 ZIP 关闭失败')) { return 'candidate_zip_close_failed'; }
    if ($contains('大包候选包 helper 阶段失败[helper_zip_open]')) { return 'candidate_helper_zip_open_failed'; }
    if ($contains('大包候选包 helper 阶段失败[resource_backfill]')) { return 'candidate_helper_backfill_failed'; }
    if ($contains('大包候选包 helper 阶段失败[helper_write]') || $contains('候选包 helper 写入失败')) { return 'candidate_helper_write_failed'; }
    if ($contains('大包候选包 helper 阶段失败[helper_zip_close]')) { return 'candidate_helper_zip_close_failed'; }
    if ($contains('大包候选包 helper 写入阶段无法打开 ZIP')) { return 'candidate_helper_zip_open_failed'; }
"""
s = replace_once(s, old, new, 'helper failure classifier')
write(p, s)

# 3) Small orchestration bridge: only re-arm the already-proven 1.21.834 worker
# after the previous fresh Candidate proves it reached the helper boundary.
module = r'''<?php
if (!defined('ABSPATH')) { exit; }

/**
 * S01 V1.21.835: Helper Finalize Closure.
 *
 * Reuses the already-proven V1.21.834 retry worker instead of introducing a
 * third Candidate worker. It only re-arms that worker after the V1.21.834
 * fresh Candidate is terminal at Stage 4 with offset==total, Completeness PASS,
 * helpers not written, and an unclassified build error. The old Candidate job
 * remains immutable and addressable; only the completed orchestration pointer
 * is archived/re-armed for one distinct fresh Candidate.
 */
function vf_ops_s01_static_helper_finalize_option_v121835(): string {
    return 'vf_ops_s01_static_helper_finalize_state_v121835';
}
function vf_ops_s01_static_helper_finalize_state_v121835(): array {
    $row = get_option(vf_ops_s01_static_helper_finalize_option_v121835(), []);
    return is_array($row) ? $row : [];
}
function vf_ops_s01_static_helper_finalize_store_v121835(array $state): array {
    $safe = [
        'schemaVersion'=>'1.0.0',
        'pluginVersion'=>defined('VF_OPS_VERSION') ? (string)VF_OPS_VERSION : '',
        'activated'=>!empty($state['activated']),
        'status'=>sanitize_key((string)($state['status'] ?? '')),
        'code'=>sanitize_key((string)($state['code'] ?? '')),
        'oldCandidateJobId'=>preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['oldCandidateJobId'] ?? '')),
        'candidateJobId'=>preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['candidateJobId'] ?? '')),
        'oldOffset'=>max(0,(int)($state['oldOffset'] ?? 0)),
        'oldTotal'=>max(0,(int)($state['oldTotal'] ?? 0)),
        'updatedAt'=>function_exists('current_time') ? (string)current_time('mysql') : gmdate('Y-m-d H:i:s'),
    ];
    update_option(vf_ops_s01_static_helper_finalize_option_v121835(), $safe, false);
    $readback = vf_ops_s01_static_helper_finalize_state_v121835();
    return $readback === $safe ? $safe : [];
}
function vf_ops_s01_static_helper_finalize_runtime_v121835(): bool {
    return function_exists('vf_ops_s01_static_zero_write_retry_runtime_v121834')
        && vf_ops_s01_static_zero_write_retry_runtime_v121834()
        && function_exists('vf_ops_s01_static_zero_write_retry_state_v121834')
        && function_exists('vf_ops_s01_static_zero_write_retry_option_v121834')
        && function_exists('vf_ops_s01_static_zero_write_retry_hook_v121834')
        && function_exists('vf_ops_s01_static_zero_write_retry_start_v121834')
        && class_exists('VF_Ops_Release_Async_Job');
}
function vf_ops_s01_static_helper_finalize_activate_v121835(): array {
    if (!function_exists('is_admin') || !is_admin()) { return ['status'=>'NOT_RUN','code'=>'ADMIN_CONTEXT_REQUIRED']; }
    if (!function_exists('current_user_can') || !current_user_can('manage_options')) { return ['status'=>'NOT_RUN','code'=>'MANAGE_OPTIONS_REQUIRED']; }
    $existing = vf_ops_s01_static_helper_finalize_state_v121835();
    if (!empty($existing['activated'])) { return ['status'=>(string)($existing['status'] ?? 'running'),'code'=>(string)($existing['code'] ?? 'HELPER_FINALIZE_ALREADY_ACTIVATED')]; }
    if (!vf_ops_s01_static_helper_finalize_runtime_v121835()) {
        vf_ops_s01_static_helper_finalize_store_v121835(['activated'=>true,'status'=>'blocked','code'=>'HELPER_FINALIZE_RUNTIME_NOT_READY']);
        return ['status'=>'BLOCKED','code'=>'HELPER_FINALIZE_RUNTIME_NOT_READY'];
    }

    $prior = (array)vf_ops_s01_static_zero_write_retry_state_v121834();
    $oldId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($prior['candidateJobId'] ?? ''));
    if ($oldId === '') {
        vf_ops_s01_static_helper_finalize_store_v121835(['activated'=>true,'status'=>'blocked','code'=>'HELPER_FINALIZE_PRIOR_CANDIDATE_MISSING']);
        return ['status'=>'BLOCKED','code'=>'HELPER_FINALIZE_PRIOR_CANDIDATE_MISSING'];
    }
    $old = VF_Ops_Release_Async_Job::load($oldId);
    if (!$old || (string)($old['job_mode'] ?? '') !== 'candidate') {
        vf_ops_s01_static_helper_finalize_store_v121835(['activated'=>true,'status'=>'blocked','code'=>'HELPER_FINALIZE_PRIOR_CANDIDATE_INVALID']);
        return ['status'=>'BLOCKED','code'=>'HELPER_FINALIZE_PRIOR_CANDIDATE_INVALID'];
    }
    $terminal = ['FAIL','FAILED','BLOCKED','ERROR','CANCELLED','TIMEOUT'];
    $oldStatus = strtoupper((string)($old['status'] ?? ''));
    $build = is_array($old['large_build'] ?? null) ? (array)$old['large_build'] : [];
    $offset = max(0,(int)($build['offset'] ?? 0));
    $total = max(0,(int)($build['total'] ?? 0));
    $completeness = is_array($build['completeness'] ?? null) ? (array)$build['completeness'] : [];
    $completenessStatus = strtoupper((string)($completeness['status'] ?? ''));
    $failureClass = function_exists('vf_ops_s01_static_candidate_build_failure_classify_v121830')
        ? vf_ops_s01_static_candidate_build_failure_classify_v121830((string)($old['error'] ?? '')) : '';
    if (!in_array($oldStatus,$terminal,true) || (int)($old['current_stage'] ?? 0) !== 4
        || empty($build['initialized']) || $total <= 0 || $offset < $total
        || $completenessStatus !== 'PASS' || !empty($build['helpers_written'])
        || $failureClass !== 'candidate_build_unclassified') {
        vf_ops_s01_static_helper_finalize_store_v121835([
            'activated'=>true,'status'=>'blocked','code'=>'HELPER_FINALIZE_BOUNDARY_NOT_PROVEN',
            'oldCandidateJobId'=>$oldId,'oldOffset'=>$offset,'oldTotal'=>$total,
        ]);
        return ['status'=>'BLOCKED','code'=>'HELPER_FINALIZE_BOUNDARY_NOT_PROVEN'];
    }

    // Archive only the orchestration pointer. The prior Candidate job itself is
    // untouched. Clear any stale one-shot hook before the proven worker is re-armed.
    if (function_exists('wp_clear_scheduled_hook')) { wp_clear_scheduled_hook(vf_ops_s01_static_zero_write_retry_hook_v121834()); }
    delete_option(vf_ops_s01_static_zero_write_retry_option_v121834());
    $started = (array)vf_ops_s01_static_zero_write_retry_start_v121834();
    $fresh = (array)vf_ops_s01_static_zero_write_retry_state_v121834();
    $newId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($fresh['candidateJobId'] ?? ''));
    if ((string)($started['status'] ?? '') !== 'RUNNING' || $newId === '' || hash_equals($oldId,$newId)) {
        vf_ops_s01_static_helper_finalize_store_v121835([
            'activated'=>true,'status'=>'blocked','code'=>'HELPER_FINALIZE_FRESH_CANDIDATE_NOT_CREATED',
            'oldCandidateJobId'=>$oldId,'candidateJobId'=>$newId,'oldOffset'=>$offset,'oldTotal'=>$total,
        ]);
        return ['status'=>'BLOCKED','code'=>'HELPER_FINALIZE_FRESH_CANDIDATE_NOT_CREATED'];
    }
    vf_ops_s01_static_helper_finalize_store_v121835([
        'activated'=>true,'status'=>'running','code'=>'HELPER_FINALIZE_FRESH_CANDIDATE_CREATED',
        'oldCandidateJobId'=>$oldId,'candidateJobId'=>$newId,'oldOffset'=>$offset,'oldTotal'=>$total,
    ]);
    return ['status'=>'RUNNING','code'=>'HELPER_FINALIZE_FRESH_CANDIDATE_CREATED'];
}
function vf_ops_s01_static_helper_finalize_snapshot_v121835(): array {
    $state = vf_ops_s01_static_helper_finalize_state_v121835();
    $out = [
        'sourceRecoveryHelperFinalizeStatus'=>sanitize_key((string)($state['status'] ?? 'not_run')),
        'sourceRecoveryHelperFinalizeCode'=>sanitize_key((string)($state['code'] ?? '')),
        'sourceRecoveryHelperFinalizeOldBuildOffset'=>max(0,(int)($state['oldOffset'] ?? 0)),
        'sourceRecoveryHelperFinalizeOldBuildTotal'=>max(0,(int)($state['oldTotal'] ?? 0)),
        'sourceRecoveryHelperFinalizeCandidateStatus'=>'',
        'sourceRecoveryHelperFinalizeCandidateCurrentStage'=>0,
        'sourceRecoveryHelperFinalizeCandidateAuditFailureCount'=>0,
        'sourceRecoveryHelperFinalizeCandidateFailureClass'=>'',
        'sourceRecoveryHelperFinalizeCandidateBuildOffset'=>0,
        'sourceRecoveryHelperFinalizeCandidateBuildTotal'=>0,
        'sourceRecoveryHelperFinalizeCandidateHelperPhase'=>'',
        'sourceRecoveryHelperFinalizeCandidateHelpersWritten'=>false,
    ];
    if (!vf_ops_s01_static_helper_finalize_runtime_v121835()) { return $out; }
    $candidateId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['candidateJobId'] ?? ''));
    if ($candidateId === '') { return $out; }
    $job = VF_Ops_Release_Async_Job::load($candidateId);
    if (!$job || (string)($job['job_mode'] ?? '') !== 'candidate') { return $out; }
    $audit = is_array($job['candidate_audit'] ?? null) ? (array)$job['candidate_audit'] : [];
    $build = is_array($job['large_build'] ?? null) ? (array)$job['large_build'] : [];
    $status = strtolower(sanitize_key((string)($job['status'] ?? '')));
    $stage = max(0,min(7,(int)($job['current_stage'] ?? 0)));
    $out['sourceRecoveryHelperFinalizeCandidateStatus'] = $status;
    $out['sourceRecoveryHelperFinalizeCandidateCurrentStage'] = $stage;
    $out['sourceRecoveryHelperFinalizeCandidateAuditFailureCount'] = count((array)($audit['failures'] ?? []));
    $out['sourceRecoveryHelperFinalizeCandidateBuildOffset'] = max(0,(int)($build['offset'] ?? 0));
    $out['sourceRecoveryHelperFinalizeCandidateBuildTotal'] = max(0,(int)($build['total'] ?? 0));
    $out['sourceRecoveryHelperFinalizeCandidateHelperPhase'] = sanitize_key((string)($build['helper_phase'] ?? ''));
    $out['sourceRecoveryHelperFinalizeCandidateHelpersWritten'] = !empty($build['helpers_written']);
    if ($stage === 4 && function_exists('vf_ops_s01_static_candidate_build_failure_classify_v121830')) {
        $out['sourceRecoveryHelperFinalizeCandidateFailureClass'] = vf_ops_s01_static_candidate_build_failure_classify_v121830((string)($job['error'] ?? ''));
    }
    if (in_array(strtoupper((string)($job['status'] ?? '')), ['DONE','FAIL','FAILED','BLOCKED','ERROR','CANCELLED','TIMEOUT'], true)) {
        $out['sourceRecoveryHelperFinalizeStatus'] = $status;
        $out['sourceRecoveryHelperFinalizeCode'] = 'helper_finalize_candidate_terminal';
    }
    return $out;
}
function vf_ops_s01_static_helper_finalize_rest_v121835($response, $server, $request) {
    $route = is_object($request) && method_exists($request, 'get_route') ? (string)$request->get_route() : '';
    if ($route !== '/vf-ops/v1/s01-static-candidate-readiness') { return $response; }
    if (!is_object($response) || !method_exists($response,'get_data') || !method_exists($response,'set_data')) { return $response; }
    $data = $response->get_data();
    if (!is_array($data)) { return $response; }
    $response->set_data(array_merge($data, vf_ops_s01_static_helper_finalize_snapshot_v121835()));
    return $response;
}
if (function_exists('add_action')) {
    add_action('admin_init', 'vf_ops_s01_static_helper_finalize_activate_v121835', 33);
}
if (function_exists('add_filter')) {
    add_filter('rest_post_dispatch', 'vf_ops_s01_static_helper_finalize_rest_v121835', 33, 3);
}
'''
write(Path('includes/site-release/s01-static-helper-finalize-retry-v121835.php'), module)

# 4) Version/bootstrap.
write(Path('VERSION'), '1.21.835\n')
p = Path('vf-ops.php')
s = read(p)
s = replace_once(s, ' * Version: 1.21.834\n', ' * Version: 1.21.835\n', 'header version')
s = replace_once(s, "define('VF_OPS_VERSION', '1.21.834')", "define('VF_OPS_VERSION', '1.21.835')", 'runtime version')
s = replace_once(s, "define('VF_OPS_ROUND', 'STATIC-CANDIDATE-ZERO-WRITE-BATCH-CLOSURE-V1')", "define('VF_OPS_ROUND', 'STATIC-CANDIDATE-HELPER-FINALIZE-CLOSURE-V1')", 'round')
s = replace_once(s,
    "require_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-zero-write-batch-retry-v121834.php';\n",
    "require_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-zero-write-batch-retry-v121834.php';\nrequire_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-helper-finalize-retry-v121835.php';\n",
    'bootstrap include')
write(p, s)

# 5) Focused machine contract.
phase = r'''<?php
$root = dirname(__DIR__, 2);
$need = static function(bool $ok, string $label): void { if (!$ok) { fwrite(STDERR, "FAIL:$label\n"); exit(1); } };
$builder = file_get_contents($root . '/includes/release/builders/class-candidate-batch-builder.php');
$classifier = file_get_contents($root . '/includes/site-release/s01-static-candidate-build-failure-readback-v121830.php');
$bridge = file_get_contents($root . '/includes/site-release/s01-static-helper-finalize-retry-v121835.php');
$bootstrap = file_get_contents($root . '/vf-ops.php');
$need(trim(file_get_contents($root . '/VERSION')) === '1.21.835', 'version');
$need(strpos($bootstrap, "Version: 1.21.835") !== false && strpos($bootstrap, "STATIC-CANDIDATE-HELPER-FINALIZE-CLOSURE-V1") !== false, 'bootstrap-version');
$need(strpos($builder, "$state['helper_phase'] = 'resource_backfill';") !== false, 'phase-backfill');
$need(strpos($builder, "$state['helper_phase'] = 'helper_write';") !== false, 'phase-helper-write');
$need(strpos($builder, 'VF_Ops_Release_Candidate_Resource_Backfiller::ensure_helpers') === false, 'no-duplicate-helper-rewrite');
$backfill = strpos($builder, 'VF_Ops_Release_Candidate_Resource_Backfiller::backfill');
$helper = strpos($builder, 'VF_Ops_Release_Candidate_Helper_Writer::write_generated_files');
$need($backfill !== false && $helper !== false && $backfill < $helper, 'backfill-before-helper');
$need(strpos($classifier, 'candidate_helper_backfill_failed') !== false && strpos($classifier, 'candidate_helper_write_failed') !== false && strpos($classifier, 'candidate_helper_zip_close_failed') !== false, 'classifier');
foreach (['offset < $total', "$completenessStatus !== 'PASS'", "!empty($build['helpers_written'])", 'candidate_build_unclassified', 'delete_option(vf_ops_s01_static_zero_write_retry_option_v121834())', 'vf_ops_s01_static_zero_write_retry_start_v121834()'] as $token) {
    $need(strpos($bridge, $token) !== false, 'bridge:' . $token);
}
foreach (['wp_insert_post','wp_update_post','$wpdb->query','TRUNCATE','DROP TABLE','candidatePackageReady=true','finalOnlinePass=YES'] as $forbidden) {
    $need(strpos($bridge, $forbidden) === false, 'forbidden:' . $forbidden);
}
echo "PASS_V121835_HELPER_FINALIZE_CLOSURE\n";
'''
write(Path('.github/phase3/v121835-helper-finalize-closure.php'), phase)
