from pathlib import Path

home = Path('src/app/FunctionalHome.php')
css = Path('src/assets/workspace-home.css')

text = home.read_text(encoding='utf-8')

anchor = """function vf_home_operation_view(array $entry, array $assetTitles, array $categoryTitles): array\n{"""
helper = r'''function vf_home_backup_status(array $policy, array $backups, ?int $now = null): array
{
    $current = $now ?? time();
    $enabled = !empty($policy['enabled']);
    $intervalHours = max(1, (int)($policy['interval_hours'] ?? 24));
    $latest = is_array($backups[0] ?? null) ? $backups[0] : [];
    $isValid = static function (array $row): bool {
        $exists = !array_key_exists('exists', $row) || !empty($row['exists']);
        return $exists
            && (string)($row['validation_status'] ?? '') === 'valid'
            && strtolower((string)($row['integrity_status'] ?? '')) === 'ok'
            && (int)($row['foreign_key_errors'] ?? 0) === 0;
    };

    $latestValid = [];
    foreach ($backups as $row) {
        if (is_array($row) && $isValid($row)) { $latestValid = $row; break; }
    }
    $latestValidAt = trim((string)($latestValid['created_at'] ?? ''));
    $latestValidTs = 0;
    if ($latestValidAt !== '') {
        try { $latestValidTs = (new DateTimeImmutable($latestValidAt))->getTimestamp(); }
        catch (Throwable $ignored) { $latestValidTs = 0; }
    }
    $age = $latestValidAt !== '' ? vf_home_relative_age($latestValidAt, $current) : '';
    $staleAfter = max(6 * 3600, $intervalHours * 2 * 3600);
    $stale = $latestValidTs > 0 && max(0, $current - $latestValidTs) > $staleAfter;

    if (!$enabled) {
        return ['known'=>true,'needs_action'=>true,'label'=>'自动备份已关闭','detail'=>'数据仍可手动备份，但日常保护已经停止。'];
    }
    if (!$backups) {
        return ['known'=>true,'needs_action'=>true,'label'=>'还没有可用备份','detail'=>'自动备份已开启，但目前还没有 SQLite 恢复点。'];
    }
    if ($latest && !$isValid($latest)) {
        return ['known'=>true,'needs_action'=>true,'label'=>'最近一次备份需要检查','detail'=>'最近备份未通过完整性校验或文件已缺失。'];
    }
    if (!$latestValid) {
        return ['known'=>true,'needs_action'=>true,'label'=>'没有通过校验的备份','detail'=>'当前备份记录里找不到可确认恢复的 SQLite 快照。'];
    }
    if ($latestValidTs <= 0) {
        return ['known'=>true,'needs_action'=>true,'label'=>'备份时间需要检查','detail'=>'已有有效备份，但最近备份时间无法确认。'];
    }
    if ($stale) {
        return ['known'=>true,'needs_action'=>true,'label'=>'最近备份已超过计划周期','detail'=>'最近有效备份 '.$age.'，建议检查自动备份任务。'];
    }
    return ['known'=>true,'needs_action'=>false,'label'=>'数据安全正常','detail'=>'自动备份已开启 · 最近有效备份 '.$age];
}

'''
if anchor not in text:
    raise SystemExit('home operation anchor missing')
text = text.replace(anchor, helper + anchor, 1)

old = """    $healthStatus = (array)($context['health_status'] ?? []);\n    $firstUse = !empty($context['first_use']);"""
new = """    $healthStatus = (array)($context['health_status'] ?? []);\n    $backupStatus = (array)($context['backup_status'] ?? []);\n    $backupKnown = !empty($backupStatus['known']);\n    $backupNeedsAction = $backupKnown && !empty($backupStatus['needs_action']);\n    $firstUse = !empty($context['first_use']);"""
if old not in text:
    raise SystemExit('render context anchor missing')
text = text.replace(old, new, 1)

old = """    $hasAttention = $hasHealthPriority || $pending > 0;"""
new = """    $hasAttention = $hasHealthPriority || $pending > 0 || $backupNeedsAction;"""
if old not in text:
    raise SystemExit('attention anchor missing')
text = text.replace(old, new, 1)

old = """          <?php if($pending>0): ?>\n            <a class=\"vf-home-attention-item\" href=\"surface-manager.php\">"""
new = """          <?php if($backupNeedsAction): ?>\n            <a class=\"vf-home-attention-item warning\" href=\"data-safety.php#backups-section\">\n              <span class=\"vf-home-attention-copy\"><b>数据安全</b><small><?=vf_fw_h((string)($backupStatus['label'] ?? '备份需要检查'))?> · <?=vf_fw_h((string)($backupStatus['detail'] ?? ''))?></small></span>\n              <strong class=\"vf-home-attention-signal\">!</strong>\n              <i>检查 →</i>\n            </a>\n          <?php endif; ?>\n          <?php if($pending>0): ?>\n            <a class=\"vf-home-attention-item\" href=\"surface-manager.php\">"""
if old not in text:
    raise SystemExit('pending anchor missing')
text = text.replace(old, new, 1)

old = """        </div>\n      <?php endif; ?>\n    </section>\n\n    <section class=\"vf-home-activity-section\""""
new = """        </div>\n      <?php endif; ?>\n      <?php if($backupKnown && !$backupNeedsAction): ?>\n        <a class=\"vf-home-safety-status\" href=\"data-safety.php#backups-section\">\n          <span>✓ <?=vf_fw_h((string)($backupStatus['label'] ?? '数据安全正常'))?></span>\n          <small><?=vf_fw_h((string)($backupStatus['detail'] ?? ''))?></small>\n          <i>查看 →</i>\n        </a>\n      <?php endif; ?>\n    </section>\n\n    <section class=\"vf-home-activity-section\""""
if old not in text:
    raise SystemExit('focus close anchor missing')
text = text.replace(old, new, 1)

old = """    $healthStatus = [];\n    try { $healthStatus = (new VfLinkHealth($db))->status(); } catch (Throwable $ignored) {}\n    $operationAssetTitles = [];"""
new = """    $healthStatus = [];\n    try { $healthStatus = (new VfLinkHealth($db))->status(); } catch (Throwable $ignored) {}\n    $backupStatus = [];\n    try {\n        $backupManager = new VfBackupManager($db);\n        $backupStatus = vf_home_backup_status($backupManager->policy(), $backupManager->list());\n    } catch (Throwable $ignored) {}\n    $operationAssetTitles = [];"""
if old not in text:
    raise SystemExit('workspace health anchor missing')
text = text.replace(old, new, 1)

old = """<?php vf_render_home_command_center(['pending'=>$pending,'operations'=>$operations,'operation_asset_titles'=>$operationAssetTitles,'operation_category_titles'=>$operationCategoryTitles,'health_status'=>$healthStatus,'first_use'=>count($allAssets)===0]); ?>"""
new = """<?php vf_render_home_command_center(['pending'=>$pending,'operations'=>$operations,'operation_asset_titles'=>$operationAssetTitles,'operation_category_titles'=>$operationCategoryTitles,'health_status'=>$healthStatus,'backup_status'=>$backupStatus,'first_use'=>count($allAssets)===0]); ?>"""
if old not in text:
    raise SystemExit('render call anchor missing')
text = text.replace(old, new, 1)

home.write_text(text, encoding='utf-8')

styles = css.read_text(encoding='utf-8').rstrip() + r'''

/* Daily data-safety signal: surface existing backup authority without duplicating backup logic. */
.vf-home-attention-item>strong.vf-home-attention-signal{min-width:34px;text-align:center;color:#92400e;font-size:18px}
.vf-home-safety-status{margin-top:8px;padding:8px 10px;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:9px;border:1px solid color-mix(in srgb,var(--ws-teal) 18%,var(--ws-line));border-radius:8px;background:color-mix(in srgb,var(--ws-teal-soft) 18%,var(--ws-panel));color:inherit;text-decoration:none}
.vf-home-safety-status>span{color:var(--ws-teal);font-size:10.5px;font-weight:780;white-space:nowrap}
.vf-home-safety-status>small{min-width:0;color:var(--ws-muted-2);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vf-home-safety-status>i{color:var(--ws-teal);font-style:normal;font-size:10px;font-weight:750;white-space:nowrap}
.vf-home-safety-status:hover{border-color:color-mix(in srgb,var(--ws-teal) 34%,var(--ws-line));background:var(--ws-soft)}
@media(max-width:760px){.vf-home-safety-status{grid-template-columns:1fr auto}.vf-home-safety-status>small{grid-column:1/-1;white-space:normal;line-height:1.4}.vf-home-safety-status>i{grid-column:2;grid-row:1}}
'''
css.write_text(styles.rstrip() + '\n', encoding='utf-8')
