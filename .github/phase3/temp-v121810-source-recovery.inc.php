<?php
function vf_ops_s01_static_source_pointer_recovery_option_v121810(): string {
    return 'vf_ops_s01_static_source_pointer_recovery_v121810';
}

function vf_ops_s01_static_source_pointer_recovery_store_v121810(string $status, string $code, string $basis = '', int $matches = 0): array {
    $row = [
        'schemaVersion'=>'1.0.0',
        'pluginVersion'=>defined('VF_OPS_VERSION') ? (string)VF_OPS_VERSION : '',
        'status'=>sanitize_key($status),
        'code'=>sanitize_key($code),
        'basis'=>sanitize_key($basis),
        'matchedCount'=>max(0, $matches),
        'updatedAt'=>function_exists('current_time') ? (string)current_time('mysql') : gmdate('Y-m-d H:i:s'),
    ];
    $existing = get_option(vf_ops_s01_static_source_pointer_recovery_option_v121810(), []);
    if (is_array($existing)
        && (string)($existing['pluginVersion'] ?? '') === $row['pluginVersion']
        && (string)($existing['status'] ?? '') === $row['status']
        && (string)($existing['code'] ?? '') === $row['code']
        && (string)($existing['basis'] ?? '') === $row['basis']
        && (int)($existing['matchedCount'] ?? -1) === $row['matchedCount']
    ) { return $existing; }
    update_option(vf_ops_s01_static_source_pointer_recovery_option_v121810(), $row, false);
    $readback = get_option(vf_ops_s01_static_source_pointer_recovery_option_v121810(), []);
    return is_array($readback) && $readback === $row ? $row : [];
}

function vf_ops_s01_static_source_pointer_job_v121810(string $jobId): array {
    $jobId = preg_replace('/[^a-z0-9_\-]/i', '', $jobId);
    if ($jobId === '') { return []; }
    $job = get_option('vf_ops_release_async_job_' . $jobId, []);
    return is_array($job) ? $job : [];
}

function vf_ops_s01_static_source_pointer_option_names_v121810(int $limit = 200): array {
    global $wpdb;
    $limit = max(1, min(200, $limit));
    if (!is_object($wpdb) || !isset($wpdb->options) || !method_exists($wpdb, 'get_col') || !method_exists($wpdb, 'prepare')) { return []; }
    $prefix = 'vf_ops_release_async_job_';
    $debug = 'vf_ops_release_async_job_debug_';
    $likePrefix = method_exists($wpdb, 'esc_like') ? $wpdb->esc_like($prefix) : addcslashes($prefix, '_%\\');
    $likeDebug = method_exists($wpdb, 'esc_like') ? $wpdb->esc_like($debug) : addcslashes($debug, '_%\\');
    $query = $wpdb->prepare(
        "SELECT option_name FROM {$wpdb->options} WHERE option_name LIKE %s AND option_name NOT LIKE %s ORDER BY option_id DESC LIMIT %d",
        $likePrefix . '%',
        $likeDebug . '%',
        $limit
    );
    $names = [];
    foreach ((array)$wpdb->get_col($query) as $name) {
        $name = (string)$name;
        if (str_starts_with($name, $prefix) && !str_starts_with($name, $debug)) { $names[$name] = true; }
    }
    return array_keys($names);
}

function vf_ops_s01_static_source_pointer_inspection_v121810(array $job, string $expectedSha, string $expectedSourceName = ''): array {
    $id = preg_replace('/[^a-z0-9_\-]/i', '', (string)($job['id'] ?? ''));
    if ($id === '') { return ['ok'=>false,'code'=>'JOB_ID_INVALID']; }
    if (sanitize_key((string)($job['job_mode'] ?? '')) !== 'inspect_only') { return ['ok'=>false,'code'=>'JOB_MODE_NOT_INSPECTION']; }
    if (strtoupper(trim((string)($job['status'] ?? ''))) !== 'DONE' || empty($job['inspection_complete'])) { return ['ok'=>false,'code'=>'INSPECTION_NOT_COMPLETE']; }
    if (trim((string)($job['error'] ?? '')) !== '') { return ['ok'=>false,'code'=>'INSPECTION_HAS_ERROR']; }
    foreach ((array)($job['steps'] ?? []) as $step) {
        if (!is_array($step)) { continue; }
        if (in_array(strtoupper((string)($step['status'] ?? '')), ['FAIL','FAILED','BLOCKED','ERROR'], true)) {
            return ['ok'=>false,'code'=>'INSPECTION_HAS_BLOCKING_STEP'];
        }
    }
    $sourcePath = trim((string)($job['source_path'] ?? ''));
    if ($sourcePath === '' || !is_file($sourcePath) || !is_readable($sourcePath)) { return ['ok'=>false,'code'=>'SOURCE_FILE_NOT_READABLE']; }
    $size = @filesize($sourcePath);
    if (!is_int($size) || $size < 1) { return ['ok'=>false,'code'=>'SOURCE_FILE_EMPTY']; }
    $expectedSha = strtolower(trim($expectedSha));
    if (preg_match('/^[a-f0-9]{64}$/', $expectedSha) !== 1) { return ['ok'=>false,'code'=>'SOURCE_HASH_AUTHORITY_MISSING']; }
    $actualSha = strtolower((string)@hash_file('sha256', $sourcePath));
    if (preg_match('/^[a-f0-9]{64}$/', $actualSha) !== 1 || !hash_equals($expectedSha, $actualSha)) {
        return ['ok'=>false,'code'=>'SOURCE_HASH_MISMATCH'];
    }
    $expectedSourceName = trim($expectedSourceName);
    $sourceName = trim((string)($job['source_name'] ?? ''));
    if ($expectedSourceName !== '' && $sourceName !== '' && $expectedSourceName !== $sourceName) {
        return ['ok'=>false,'code'=>'SOURCE_NAME_MISMATCH'];
    }
    return ['ok'=>true,'code'=>'TRUSTED_INSPECTION_SOURCE','id'=>$id,'sha256'=>$actualSha,'sourceName'=>$sourceName,'sourceSize'=>$size];
}

function vf_ops_s01_static_source_pointer_recover_v121810(): array {
    if (!function_exists('is_admin') || !is_admin()) {
        return ['status'=>'NOT_RUN','code'=>'ADMIN_CONTEXT_REQUIRED'];
    }
    if (!function_exists('current_user_can') || !current_user_can('manage_options')) {
        return ['status'=>'NOT_RUN','code'=>'MANAGE_OPTIONS_REQUIRED'];
    }

    $optionKey = function_exists('vf_toolsite_cf_release_option_key') ? (string)vf_toolsite_cf_release_option_key() : 'vf_toolsite_cf_static_release_records_v1';
    $record = function_exists('vf_toolsite_cf_release_record') ? (array)vf_toolsite_cf_release_record() : (array)get_option($optionKey, []);
    $activeId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($record['active_release_job'] ?? $record['candidate_async_job'] ?? ''));
    if ($activeId === '') {
        vf_ops_s01_static_source_pointer_recovery_store_v121810('not_recovered','ACTIVE_JOB_MISSING');
        return ['status'=>'NOT_RECOVERED','code'=>'ACTIVE_JOB_MISSING'];
    }

    $activeJob = vf_ops_s01_static_source_pointer_job_v121810($activeId);
    $activeSource = trim((string)($activeJob['source_path'] ?? ''));
    if ($activeSource !== '' && is_file($activeSource) && is_readable($activeSource)) {
        vf_ops_s01_static_source_pointer_recovery_store_v121810('current','CURRENT_SOURCE_AVAILABLE','current_active_job',1);
        return ['status'=>'PASS','code'=>'CURRENT_SOURCE_AVAILABLE','basis'=>'current_active_job','matchedCount'=>1];
    }

    $expectedSha = '';
    foreach ([
        (string)($activeJob['source_inspection_sha256'] ?? ''),
        (string)($record['source_sha256'] ?? ''),
        (string)($record['source_package_sha256'] ?? ''),
    ] as $candidateSha) {
        $candidateSha = strtolower(trim($candidateSha));
        if (preg_match('/^[a-f0-9]{64}$/', $candidateSha) === 1) { $expectedSha = $candidateSha; break; }
    }
    if ($expectedSha === '') {
        vf_ops_s01_static_source_pointer_recovery_store_v121810('blocked','SOURCE_HASH_AUTHORITY_MISSING');
        return ['status'=>'BLOCKED','code'=>'SOURCE_HASH_AUTHORITY_MISSING'];
    }
    $expectedSourceName = trim((string)($activeJob['source_name'] ?? $record['source_package_name'] ?? ''));

    $matches = [];
    $basis = '';
    $lineageId = preg_replace('/[^a-z0-9_\-]/i', '', (string)($activeJob['promoted_from_inspection_job'] ?? ''));
    if ($lineageId !== '') {
        $lineageJob = vf_ops_s01_static_source_pointer_job_v121810($lineageId);
        $validated = vf_ops_s01_static_source_pointer_inspection_v121810($lineageJob, $expectedSha, $expectedSourceName);
        if (!empty($validated['ok'])) {
            $matches[$lineageId] = $validated;
            $basis = 'candidate_lineage';
        }
    }

    if (!$matches) {
        foreach (vf_ops_s01_static_source_pointer_option_names_v121810(200) as $name) {
            if (!preg_match('/^vf_ops_release_async_job_(?!debug_)([a-z0-9_\-]+)$/i', $name, $m)) { continue; }
            $id = (string)$m[1];
            if ($id === $activeId) { continue; }
            $job = vf_ops_s01_static_source_pointer_job_v121810($id);
            $validated = vf_ops_s01_static_source_pointer_inspection_v121810($job, $expectedSha, $expectedSourceName);
            if (!empty($validated['ok'])) { $matches[$id] = $validated; }
        }
        $basis = 'bounded_unique_hash_match';
    }

    $count = count($matches);
    if ($count !== 1) {
        $code = $count > 1 ? 'AMBIGUOUS_TRUSTED_INSPECTION_SOURCE' : 'NO_TRUSTED_INSPECTION_SOURCE';
        vf_ops_s01_static_source_pointer_recovery_store_v121810('blocked',$code,$basis,$count);
        return ['status'=>'BLOCKED','code'=>$code,'basis'=>$basis,'matchedCount'=>$count];
    }

    $selectedId = (string)array_key_first($matches);
    $selected = (array)$matches[$selectedId];

    $rawBefore = get_option($optionKey, []);
    $rawBefore = is_array($rawBefore) ? $rawBefore : [];
    $readActive = preg_replace('/[^a-z0-9_\-]/i', '', (string)($rawBefore['active_release_job'] ?? $rawBefore['candidate_async_job'] ?? ''));
    if ($readActive !== $activeId) {
        vf_ops_s01_static_source_pointer_recovery_store_v121810('blocked','RELEASE_POINTER_CHANGED',$basis,1);
        return ['status'=>'BLOCKED','code'=>'RELEASE_POINTER_CHANGED','basis'=>$basis,'matchedCount'=>1];
    }

    $rawAfter = $rawBefore;
    $rawAfter['active_release_job'] = $selectedId;
    $rawAfter['candidate_async_job'] = $selectedId;
    $rawAfter['upload_mode'] = 'inspect_only';
    $rawAfter['status'] = 'PARTIAL';
    $rawAfter['source_package_name'] = (string)($selected['sourceName'] ?? $expectedSourceName);
    $rawAfter['source_sha256'] = $expectedSha;
    $rawAfter['source_package_sha256'] = $expectedSha;
    $rawAfter['candidate_async_error'] = '';
    $rawAfter['candidate_path'] = '';
    $rawAfter['candidate_package_path'] = '';
    $rawAfter['candidate_package_name'] = '';
    $rawAfter['candidate_package_sha256'] = '';
    $rawAfter['sha256'] = '';
    $rawAfter['download_url'] = '';
    $rawAfter['generation_result'] = 'NOT_VERIFIED';
    $rawAfter['failures'] = 0;
    $rawAfter['note'] = '已从唯一、哈希一致的已完成原包检查恢复静态源指针；未重新上传 ZIP，候选包尚未重新生成。';
    $rawAfter['updated_at'] = function_exists('current_time') ? (string)current_time('mysql') : gmdate('Y-m-d H:i:s');

    update_option($optionKey, $rawAfter, false);
    $readback = get_option($optionKey, []);
    $readback = is_array($readback) ? $readback : [];
    if (
        (string)($readback['active_release_job'] ?? '') !== $selectedId
        || (string)($readback['candidate_async_job'] ?? '') !== $selectedId
        || (string)($readback['upload_mode'] ?? '') !== 'inspect_only'
        || !hash_equals($expectedSha, strtolower((string)($readback['source_sha256'] ?? '')))
    ) {
        vf_ops_s01_static_source_pointer_recovery_store_v121810('blocked','RELEASE_POINTER_READBACK_MISMATCH',$basis,1);
        return ['status'=>'BLOCKED','code'=>'RELEASE_POINTER_READBACK_MISMATCH','basis'=>$basis,'matchedCount'=>1];
    }

    vf_ops_s01_static_source_pointer_recovery_store_v121810('recovered','SOURCE_POINTER_RECOVERED',$basis,1);
    return ['status'=>'PASS','code'=>'SOURCE_POINTER_RECOVERED','basis'=>$basis,'matchedCount'=>1];
}
