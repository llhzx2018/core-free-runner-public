from pathlib import Path
from textwrap import dedent

root = Path('ops')


def read(path: str) -> str:
    return (root / path).read_text()


def write(path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def rep(content: str, old: str, new: str, label: str) -> str:
    count = content.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, got {count}')
    return content.replace(old, new, 1)


# V1.21.834: lazily open Candidate ZIP only when this batch has a real write.
p = 'includes/release/builders/class-candidate-batch-builder.php'
s = read(p)
s = rep(
    s,
    """        $dst = new ZipArchive();
        try {
            if (class_exists('VF_Ops_Release_Zip')) {
                VF_Ops_Release_Zip::open_for_append($dst, (string)$state['candidate_path'], '大包候选包 ZIP');
            } else {
                $result = $dst->open((string)$state['candidate_path'], ZipArchive::CREATE);
                if ($result !== true) { throw new RuntimeException('ZipArchive open 返回 ' . (string)$result); }
            }
        } catch (Throwable $e) {
            $src->close();
            throw new RuntimeException('大包候选包文件打开失败：' . $e->getMessage());
        }
        $start = (int)$state['offset'];
""",
    """        // V1.21.834: a tail batch can legitimately resolve to zero new output files.
        // Do not open/close the Candidate ZIP until the first real write is known.
        $dst = null;
        $dstOpened = false;
        $start = (int)$state['offset'];
""",
    'remove eager append open',
)
s = rep(
    s,
    """            if (!$write) { continue; }
            if ($dst->addFromString($outName, (string)$content) !== true) {
                $dst->close();
                $src->close();
                throw new RuntimeException('大包候选包写入失败：' . $outName);
            }
""",
    """            if (!$write) { continue; }
            if (!$dstOpened) {
                $dst = new ZipArchive();
                try {
                    if (class_exists('VF_Ops_Release_Zip')) {
                        VF_Ops_Release_Zip::open_for_append($dst, (string)$state['candidate_path'], '大包候选包 ZIP');
                    } else {
                        $result = $dst->open((string)$state['candidate_path'], ZipArchive::CREATE);
                        if ($result !== true) { throw new RuntimeException('ZipArchive open 返回 ' . (string)$result); }
                    }
                    $dstOpened = true;
                } catch (Throwable $e) {
                    try { $src->close(); } catch (Throwable $ignore) {}
                    throw new RuntimeException('大包候选包文件打开失败：' . $e->getMessage());
                }
            }
            if (!($dst instanceof ZipArchive) || $dst->addFromString($outName, (string)$content) !== true) {
                if ($dst instanceof ZipArchive) { try { $dst->close(); } catch (Throwable $ignore) {} }
                try { $src->close(); } catch (Throwable $ignore) {}
                throw new RuntimeException('大包候选包写入失败：' . $outName);
            }
""",
    'lazy append write',
)
s = rep(
    s,
    """        }
        $dst->close();
        $src->close();
        $state['offset'] = max($start, $cursor);
""",
    """        }
        if ($dstOpened && $dst instanceof ZipArchive) {
            try {
                if ($dst->close() !== true) { throw new RuntimeException('close returned false'); }
            } catch (Throwable $e) {
                try { $src->close(); } catch (Throwable $ignore) {}
                throw new RuntimeException('大包候选包 ZIP 关闭失败。');
            }
        }
        $src->close();
        $state['offset'] = max($start, $cursor);
""",
    'validated batch close',
)
s = rep(
    s,
    """            $dst->close();
            $initialActions = self::initial_actions($context);
""",
    """            if ($dst->close() !== true) {
                $src->close();
                throw new RuntimeException('大包候选包 ZIP 关闭失败。');
            }
            $initialActions = self::initial_actions($context);
""",
    'validated initialization close',
)
s = rep(
    s,
    """            $dst->close();
            $state['helpers_written'] = true;
""",
    """            if ($dst->close() !== true) { throw new RuntimeException('大包候选包 ZIP 关闭失败。'); }
            $state['helpers_written'] = true;
""",
    'validated helper close',
)
write(p, s)


# Extend privacy-safe failure classification for the normalized close boundary.
p = 'includes/site-release/s01-static-candidate-build-failure-readback-v121830.php'
s = read(p)
s = rep(
    s,
    """    if ($contains('大包候选包写入失败')) { return 'candidate_zip_entry_write_failed'; }
    if ($contains('大包候选包 helper 写入阶段无法打开 ZIP')) { return 'candidate_helper_zip_open_failed'; }
""",
    """    if ($contains('大包候选包写入失败')) { return 'candidate_zip_entry_write_failed'; }
    if ($contains('大包候选包 ZIP 关闭失败')) { return 'candidate_zip_close_failed'; }
    if ($contains('大包候选包 helper 写入阶段无法打开 ZIP')) { return 'candidate_helper_zip_open_failed'; }
""",
    'close classifier',
)
write(p, s)


retry = dedent(r'''\
<?php
if (!defined('ABSPATH')) { exit; }

/**
 * S01 V1.21.834: one-time fail-closed retry after the zero-write batch fix.
 * Reuses the already-trusted DONE inspect-only Source. Never mutates Source,
 * never resets the old terminal Candidate and never relaxes Final Audit.
 */
function vf_ops_s01_static_zero_write_retry_option_v121834(): string {
    return 'vf_ops_s01_static_zero_write_retry_state_v121834';
}
function vf_ops_s01_static_zero_write_retry_hook_v121834(): string {
    return 'vf_ops_s01_static_zero_write_retry_worker_v121834';
}
function vf_ops_s01_static_zero_write_retry_state_v121834(): array {
    $row = get_option(vf_ops_s01_static_zero_write_retry_option_v121834(), []);
    return is_array($row) ? $row : [];
}
function vf_ops_s01_static_zero_write_retry_store_v121834(array $state): array {
    $safe = [
        'schemaVersion'=>'1.0.0',
        'pluginVersion'=>defined('VF_OPS_VERSION') ? (string)VF_OPS_VERSION : '',
        'status'=>sanitize_key((string)($state['status'] ?? '')),
        'code'=>sanitize_key((string)($state['code'] ?? '')),
        'inspectionJobId'=>preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['inspectionJobId'] ?? '')),
        'oldCandidateJobId'=>preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['oldCandidateJobId'] ?? '')),
        'candidateJobId'=>preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['candidateJobId'] ?? '')),
        'expectedSha'=>preg_match('/^[a-f0-9]{64}$/i', (string)($state['expectedSha'] ?? '')) ? strtolower((string)$state['expectedSha']) : '',
        'attempts'=>max(0, min(240, (int)($state['attempts'] ?? 0))),
        'updatedAt'=>function_exists('current_time') ? (string)current_time('mysql') : gmdate('Y-m-d H:i:s'),
    ];
    update_option(vf_ops_s01_static_zero_write_retry_option_v121834(), $safe, false);
    $readback = vf_ops_s01_static_zero_write_retry_state_v121834();
    return $readback === $safe ? $safe : [];
}
function vf_ops_s01_static_zero_write_retry_schedule_v121834(int $delay = 3): bool {
    if (!function_exists('wp_next_scheduled') || !function_exists('wp_schedule_single_event')) { return false; }
    $hook = vf_ops_s01_static_zero_write_retry_hook_v121834();
    if (wp_next_scheduled($hook) !== false) { return true; }
    return (bool)wp_schedule_single_event(time() + max(1, min(30, $delay)), $hook);
}
function vf_ops_s01_static_zero_write_retry_runtime_v121834(): bool {
    if (!function_exists('vf_ops_s01_static_recovery_continuation_runtime_v121829') || !vf_ops_s01_static_recovery_continuation_runtime_v121829()) { return false; }
    return class_exists('VF_Ops_Release_Async_Job')
        && method_exists('VF_Ops_Release_Async_Job', 'sync_record')
        && method_exists('VF_Ops_Release_Async_Job', 'run_next_stage')
        && function_exists('vf_ops_s01_static_recovery_continuation_inspection_v121829')
        && function_exists('vf_ops_s01_static_recovery_continuation_state_v121829')
        && function_exists('vf_ops_s01_static_source_recovery_v2_record_v121814')
        && function_exists('vf_ops_publish_release_prepare_candidate_v121771');
}
function vf_ops_s01_static_zero_write_retry_eligible_v121834(): array {
    if (!vf_ops_s01_static_zero_write_retry_runtime_v121834()) { return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_RUNTIME_NOT_READY']; }
    $inspection = (array)vf_ops_s01_static_recovery_continuation_inspection_v121829();
    if (empty($inspection['ok'])) { return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_INSPECTION_NOT_CURRENT']; }
    $inspectionId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($inspection['jobId'] ?? ''));
    $expectedSha = strtolower((string)($inspection['expectedSha'] ?? ''));
    $legacy = (array)vf_ops_s01_static_recovery_continuation_state_v121829();
    $oldId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($legacy['candidateJobId'] ?? ''));
    if ($inspectionId === '' || $oldId === '' || preg_match('/^[a-f0-9]{64}$/', $expectedSha) !== 1) {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_IDENTITY_MISSING'];
    }
    $old = VF_Ops_Release_Async_Job::load($oldId);
    if (!$old || (string)($old['job_mode'] ?? '') !== 'candidate' || (string)($old['promoted_from_inspection_job'] ?? '') !== $inspectionId) {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_OLD_CANDIDATE_MISMATCH'];
    }
    $status = strtoupper((string)($old['status'] ?? ''));
    if (!in_array($status, ['FAIL','FAILED','BLOCKED','ERROR','CANCELLED','TIMEOUT'], true) || (int)($old['current_stage'] ?? 0) !== 4) {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_OLD_CANDIDATE_NOT_STAGE4_FAIL'];
    }
    if (!function_exists('vf_ops_s01_static_candidate_build_failure_classify_v121830') || vf_ops_s01_static_candidate_build_failure_classify_v121830((string)($old['error'] ?? '')) !== 'candidate_build_unclassified') {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_FAILURE_CLASS_CHANGED'];
    }
    $build = is_array($old['large_build'] ?? null) ? (array)$old['large_build'] : [];
    $offset = max(0, (int)($build['offset'] ?? 0));
    $total = max(0, (int)($build['total'] ?? 0));
    if (empty($build['initialized']) || $total <= 0 || $offset >= $total) {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_BUILD_STATE_NOT_ELIGIBLE'];
    }
    if (!function_exists('vf_ops_s01_static_candidate_exact_process_probe_snapshot_v121833')) {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_EXACT_PROBE_MISSING'];
    }
    $probe = (array)vf_ops_s01_static_candidate_exact_process_probe_snapshot_v121833();
    if ((string)($probe['sourceRecoveryCandidateExactProcessProbeStatus'] ?? '') !== 'pass'
        || (int)($probe['sourceRecoveryCandidateExactProcessProbeCheckedCount'] ?? 0) <= 0
        || (int)($probe['sourceRecoveryCandidateExactProcessProbeShadowWrittenDelta'] ?? -1) !== 0
        || (string)($probe['sourceRecoveryCandidateExactProcessProbeCompletenessStatus'] ?? '') !== 'pass'
        || (int)($probe['sourceRecoveryCandidateExactProcessProbeCompletenessReasonCount'] ?? -1) !== 0) {
        return ['ok'=>false,'code'=>'ZERO_WRITE_RETRY_EXACT_PROBE_NOT_ELIGIBLE'];
    }
    return ['ok'=>true,'code'=>'ZERO_WRITE_RETRY_ELIGIBLE','inspection'=>$inspection,'oldId'=>$oldId,'expectedSha'=>$expectedSha];
}
function vf_ops_s01_static_zero_write_retry_start_v121834(): array {
    if (!function_exists('is_admin') || !is_admin()) { return ['status'=>'NOT_RUN','code'=>'ADMIN_CONTEXT_REQUIRED']; }
    if (!function_exists('current_user_can') || !current_user_can('manage_options')) { return ['status'=>'NOT_RUN','code'=>'MANAGE_OPTIONS_REQUIRED']; }
    $existing = vf_ops_s01_static_zero_write_retry_state_v121834();
    $existingId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($existing['candidateJobId'] ?? ''));
    if ($existingId !== '' && vf_ops_s01_static_zero_write_retry_runtime_v121834()) {
        $candidate = VF_Ops_Release_Async_Job::load($existingId);
        if ($candidate && (string)($candidate['job_mode'] ?? '') === 'candidate') {
            $status = strtoupper((string)($candidate['status'] ?? ''));
            if (!in_array($status, ['DONE','FAIL','FAILED','BLOCKED','ERROR','CANCELLED','TIMEOUT'], true)) {
                vf_ops_s01_static_zero_write_retry_schedule_v121834(2);
                return ['status'=>'RUNNING','code'=>'ZERO_WRITE_RETRY_ALREADY_RUNNING'];
            }
            return ['status'=>'PASS','code'=>'ZERO_WRITE_RETRY_ALREADY_TERMINAL'];
        }
    }
    $eligible = vf_ops_s01_static_zero_write_retry_eligible_v121834();
    if (empty($eligible['ok'])) { return ['status'=>'NOT_RUN','code'=>(string)($eligible['code'] ?? 'ZERO_WRITE_RETRY_NOT_ELIGIBLE')]; }
    $inspection = (array)$eligible['inspection'];
    $inspectionId = (string)($inspection['jobId'] ?? '');
    $expectedSha = (string)$eligible['expectedSha'];
    $oldId = (string)$eligible['oldId'];
    VF_Ops_Release_Async_Job::sync_record((array)$inspection['job']);
    $record = (array)vf_ops_s01_static_source_recovery_v2_record_v121814();
    $activeId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($record['active_release_job'] ?? ''));
    if ($activeId === '' || !hash_equals($inspectionId, $activeId)) {
        return ['status'=>'BLOCKED','code'=>'ZERO_WRITE_RETRY_INSPECTION_REBIND_MISMATCH'];
    }
    $prepared = (array)vf_ops_publish_release_prepare_candidate_v121771($inspectionId);
    if ((string)($prepared['status'] ?? 'FAIL') !== 'PASS') {
        vf_ops_s01_static_zero_write_retry_store_v121834([
            'status'=>'blocked','code'=>(string)($prepared['code'] ?? 'ZERO_WRITE_RETRY_PREPARE_FAILED'),
            'inspectionJobId'=>$inspectionId,'oldCandidateJobId'=>$oldId,'expectedSha'=>$expectedSha,'attempts'=>0,
        ]);
        return ['status'=>'BLOCKED','code'=>(string)($prepared['code'] ?? 'ZERO_WRITE_RETRY_PREPARE_FAILED')];
    }
    $candidateId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($prepared['job'] ?? ''));
    $candidate = $candidateId !== '' ? VF_Ops_Release_Async_Job::load($candidateId) : [];
    if ($candidateId === '' || hash_equals($oldId, $candidateId) || !$candidate
        || (string)($candidate['job_mode'] ?? '') !== 'candidate'
        || (string)($candidate['promoted_from_inspection_job'] ?? '') !== $inspectionId) {
        return ['status'=>'BLOCKED','code'=>'ZERO_WRITE_RETRY_FRESH_CANDIDATE_MISMATCH'];
    }
    $source = trim((string)($candidate['source_path'] ?? ''));
    $actualSha = $source !== '' && is_file($source) && is_readable($source) && !is_link($source) ? strtolower((string)@hash_file('sha256', $source)) : '';
    if (preg_match('/^[a-f0-9]{64}$/', $actualSha) !== 1 || !hash_equals($expectedSha, $actualSha)) {
        return ['status'=>'BLOCKED','code'=>'ZERO_WRITE_RETRY_SOURCE_MISMATCH'];
    }
    vf_ops_s01_static_zero_write_retry_store_v121834([
        'status'=>'running','code'=>'ZERO_WRITE_RETRY_CANDIDATE_CREATED','inspectionJobId'=>$inspectionId,
        'oldCandidateJobId'=>$oldId,'candidateJobId'=>$candidateId,'expectedSha'=>$expectedSha,'attempts'=>0,
    ]);
    vf_ops_s01_static_zero_write_retry_schedule_v121834(2);
    return ['status'=>'RUNNING','code'=>'ZERO_WRITE_RETRY_CANDIDATE_CREATED'];
}
function vf_ops_s01_static_zero_write_retry_worker_v121834(): void {
    if (!vf_ops_s01_static_zero_write_retry_runtime_v121834()) { return; }
    $state = vf_ops_s01_static_zero_write_retry_state_v121834();
    $candidateId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['candidateJobId'] ?? ''));
    $inspectionId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['inspectionJobId'] ?? ''));
    $oldId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['oldCandidateJobId'] ?? ''));
    $expectedSha = strtolower((string)($state['expectedSha'] ?? ''));
    $attempts = max(0, (int)($state['attempts'] ?? 0));
    if ($candidateId === '' || $inspectionId === '' || $oldId === '' || hash_equals($oldId, $candidateId)
        || preg_match('/^[a-f0-9]{64}$/', $expectedSha) !== 1 || $attempts >= 180) {
        vf_ops_s01_static_zero_write_retry_store_v121834(array_merge($state,['status'=>'blocked','code'=>'ZERO_WRITE_RETRY_STATE_INVALID']));
        return;
    }
    $candidate = VF_Ops_Release_Async_Job::load($candidateId);
    if (!$candidate || (string)($candidate['job_mode'] ?? '') !== 'candidate' || (string)($candidate['promoted_from_inspection_job'] ?? '') !== $inspectionId) {
        vf_ops_s01_static_zero_write_retry_store_v121834(array_merge($state,['status'=>'blocked','code'=>'ZERO_WRITE_RETRY_CANDIDATE_IDENTITY_CHANGED']));
        return;
    }
    $source = trim((string)($candidate['source_path'] ?? ''));
    $actualSha = $source !== '' && is_file($source) && is_readable($source) && !is_link($source) ? strtolower((string)@hash_file('sha256', $source)) : '';
    if (preg_match('/^[a-f0-9]{64}$/', $actualSha) !== 1 || !hash_equals($expectedSha, $actualSha)) {
        vf_ops_s01_static_zero_write_retry_store_v121834(array_merge($state,['status'=>'blocked','code'=>'ZERO_WRITE_RETRY_SOURCE_MISMATCH']));
        return;
    }
    $terminal = ['DONE','FAIL','FAILED','BLOCKED','ERROR','CANCELLED','TIMEOUT'];
    $status = strtoupper((string)($candidate['status'] ?? ''));
    if (in_array($status, $terminal, true)) {
        vf_ops_s01_static_zero_write_retry_store_v121834(array_merge($state,['status'=>strtolower($status),'code'=>'ZERO_WRITE_RETRY_CANDIDATE_TERMINAL']));
        return;
    }
    $lockKey = 'vf_ops_s01_static_zero_write_retry_lock_v121834';
    if (!add_option($lockKey, time(), '', false)) {
        $held = (int)get_option($lockKey, 0);
        if ($held > 0 && (time() - $held) < 120) { vf_ops_s01_static_zero_write_retry_schedule_v121834(8); return; }
        delete_option($lockKey);
        if (!add_option($lockKey, time(), '', false)) { vf_ops_s01_static_zero_write_retry_schedule_v121834(8); return; }
    }
    try {
        $candidate = VF_Ops_Release_Async_Job::load($candidateId) ?: $candidate;
        try {
            $candidate = VF_Ops_Release_Async_Job::run_next_stage($candidate);
        } catch (Throwable $e) {
            if (isset($GLOBALS['vf_ops_release_last_candidate_audit']) && is_array($GLOBALS['vf_ops_release_last_candidate_audit'])) {
                $candidate['candidate_audit'] = $GLOBALS['vf_ops_release_last_candidate_audit'];
                if (!isset($candidate['context']) || !is_array($candidate['context'])) { $candidate['context'] = []; }
                $candidate['context']['candidate_audit'] = $GLOBALS['vf_ops_release_last_candidate_audit'];
            }
            $candidate['status'] = 'FAIL';
            $candidate['error'] = sanitize_text_field($e->getMessage());
            $candidate['next'] = ($e instanceof VF_Ops_Release_Pipeline_Exception) ? $e->next_action() : 'Zero-write retry Candidate remains fail-closed.';
            $idx = (int)($candidate['current_stage'] ?? 0) >= 6 ? 7 : ((int)($candidate['current_stage'] ?? 0) >= 3 ? 6 : 1);
            if (isset($candidate['steps'][$idx]) && is_array($candidate['steps'][$idx])) {
                $candidate['steps'][$idx]['status'] = 'FAIL';
                $candidate['steps'][$idx]['note'] = $candidate['error'];
            }
        }
        VF_Ops_Release_Async_Job::save($candidate);
        $candidate = VF_Ops_Release_Async_Job::load($candidateId) ?: $candidate;
        VF_Ops_Release_Async_Job::sync_record($candidate);
        $status = strtoupper((string)($candidate['status'] ?? 'FAIL'));
        $nextAttempts = $attempts + 1;
        vf_ops_s01_static_zero_write_retry_store_v121834([
            'status'=>in_array($status,$terminal,true)?strtolower($status):'running',
            'code'=>in_array($status,$terminal,true)?'ZERO_WRITE_RETRY_CANDIDATE_TERMINAL':'ZERO_WRITE_RETRY_CANDIDATE_RUNNING',
            'inspectionJobId'=>$inspectionId,'oldCandidateJobId'=>$oldId,'candidateJobId'=>$candidateId,
            'expectedSha'=>$expectedSha,'attempts'=>$nextAttempts,
        ]);
        if (!in_array($status, $terminal, true)) { vf_ops_s01_static_zero_write_retry_schedule_v121834(3); }
    } finally {
        delete_option($lockKey);
    }
}
function vf_ops_s01_static_zero_write_retry_snapshot_v121834(): array {
    $state = vf_ops_s01_static_zero_write_retry_state_v121834();
    $out = [
        'sourceRecoveryZeroWriteRetryStatus'=>sanitize_key((string)($state['status'] ?? 'not_run')),
        'sourceRecoveryZeroWriteRetryCode'=>sanitize_key((string)($state['code'] ?? '')),
        'sourceRecoveryZeroWriteRetryAttempts'=>max(0,(int)($state['attempts'] ?? 0)),
        'sourceRecoveryZeroWriteRetryCandidateStatus'=>'',
        'sourceRecoveryZeroWriteRetryCandidateCurrentStage'=>0,
        'sourceRecoveryZeroWriteRetryCandidateAuditFailureCount'=>0,
        'sourceRecoveryZeroWriteRetryCandidateFailureClass'=>'',
    ];
    if (!vf_ops_s01_static_zero_write_retry_runtime_v121834()) { return $out; }
    $candidateId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($state['candidateJobId'] ?? ''));
    if ($candidateId === '') { return $out; }
    $job = VF_Ops_Release_Async_Job::load($candidateId);
    if (!$job || (string)($job['job_mode'] ?? '') !== 'candidate') { return $out; }
    $audit = is_array($job['candidate_audit'] ?? null) ? (array)$job['candidate_audit'] : [];
    $out['sourceRecoveryZeroWriteRetryCandidateStatus'] = strtolower(sanitize_key((string)($job['status'] ?? '')));
    $out['sourceRecoveryZeroWriteRetryCandidateCurrentStage'] = max(0,min(7,(int)($job['current_stage'] ?? 0)));
    $out['sourceRecoveryZeroWriteRetryCandidateAuditFailureCount'] = count((array)($audit['failures'] ?? []));
    if (function_exists('vf_ops_s01_static_candidate_build_failure_classify_v121830') && $out['sourceRecoveryZeroWriteRetryCandidateCurrentStage'] === 4) {
        $out['sourceRecoveryZeroWriteRetryCandidateFailureClass'] = vf_ops_s01_static_candidate_build_failure_classify_v121830((string)($job['error'] ?? ''));
    }
    return $out;
}
function vf_ops_s01_static_zero_write_retry_rest_v121834($response, $server, $request) {
    $route = is_object($request) && method_exists($request, 'get_route') ? (string)$request->get_route() : '';
    if ($route !== '/vf-ops/v1/s01-static-candidate-readiness') { return $response; }
    if (!is_object($response) || !method_exists($response, 'get_data') || !method_exists($response, 'set_data')) { return $response; }
    $data = $response->get_data();
    if (!is_array($data)) { return $response; }
    $response->set_data(array_merge($data, vf_ops_s01_static_zero_write_retry_snapshot_v121834()));
    return $response;
}
if (function_exists('add_action')) {
    add_action('admin_init', 'vf_ops_s01_static_zero_write_retry_start_v121834', 32);
    add_action(vf_ops_s01_static_zero_write_retry_hook_v121834(), 'vf_ops_s01_static_zero_write_retry_worker_v121834');
}
if (function_exists('add_filter')) {
    add_filter('rest_post_dispatch', 'vf_ops_s01_static_zero_write_retry_rest_v121834', 32, 3);
}
''')
write('includes/site-release/s01-static-zero-write-batch-retry-v121834.php', retry)


phase = dedent(r'''\
<?php
$root = dirname(__DIR__, 2);
$builder = file_get_contents($root . '/includes/release/builders/class-candidate-batch-builder.php');
$retry = file_get_contents($root . '/includes/site-release/s01-static-zero-write-batch-retry-v121834.php');
$classifier = file_get_contents($root . '/includes/site-release/s01-static-candidate-build-failure-readback-v121830.php');
$boot = file_get_contents($root . '/vf-ops.php');
$version = trim((string)file_get_contents($root . '/VERSION'));
if ($version !== '1.21.834') { exit(11); }
if (strpos($boot, "define('VF_OPS_VERSION', '1.21.834')") === false || strpos($boot, 'STATIC-CANDIDATE-ZERO-WRITE-BATCH-CLOSURE-V1') === false) { exit(12); }
if (strpos($builder, '$dstOpened = false;') === false || strpos($builder, 'if (!$dstOpened)') === false) { exit(13); }
if (substr_count($builder, 'open_for_append($dst') < 2) { exit(14); }
if (strpos($builder, '大包候选包 ZIP 关闭失败') === false || strpos($classifier, 'candidate_zip_close_failed') === false) { exit(15); }
if (strpos($retry, 'vf_ops_s01_static_recovery_continuation_inspection_v121829') === false || strpos($retry, 'vf_ops_publish_release_prepare_candidate_v121771') === false) { exit(16); }
if (strpos($retry, 'sourceRecoveryCandidateExactProcessProbeShadowWrittenDelta') === false || strpos($retry, 'ZERO_WRITE_RETRY_FRESH_CANDIDATE_MISMATCH') === false) { exit(17); }
if (strpos($retry, 'sourceRecoveryZeroWriteRetryCandidateAuditFailureCount') === false) { exit(18); }
if (strpos($retry, "'candidatePackageReady'") !== false || strpos($retry, "'finalOnlinePass'") !== false) { exit(19); }
echo "PASS_V121834_ZERO_WRITE_BATCH_CLOSURE\n";
''')
write('.github/phase3/v121834-zero-write-batch-closure.php', phase)

write('VERSION', '1.21.834\n')
p = 'vf-ops.php'
s = read(p)
s = rep(s, ' * Version: 1.21.833\n', ' * Version: 1.21.834\n', 'plugin header version')
s = rep(s, "define('VF_OPS_VERSION', '1.21.833')", "define('VF_OPS_VERSION', '1.21.834')", 'runtime version')
s = rep(s, "define('VF_OPS_ROUND', 'STATIC-CANDIDATE-EXACT-PROCESS-PROBE-V1')", "define('VF_OPS_ROUND', 'STATIC-CANDIDATE-ZERO-WRITE-BATCH-CLOSURE-V1')", 'round')
s = rep(
    s,
    "require_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-candidate-exact-process-probe-v121833.php';\n",
    "require_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-candidate-exact-process-probe-v121833.php';\nrequire_once VF_OPS_SERVICE_DIR . 'site-release/s01-static-zero-write-batch-retry-v121834.php';\n",
    'bootstrap retry',
)
write(p, s)
