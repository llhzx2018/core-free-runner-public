from pathlib import Path

app = Path('public/assets/app.js')
text = app.read_text(encoding='utf-8')
sentinels = {
    "if (!date) return value ? String(value).slice(0, 16) : '—';": "if (!date) return value ? '时间格式异常' : '—';",
    "return String(value).slice(0, 16);": "return value ? '时间格式异常' : '—';",
    "return ({ success: '成功', failed: '失败', running: '执行中', pending: '等待执行', rolled_back: '已回滚', skipped: '已跳过' })[value] || '未知';": "return ({ success: '成功', failed: '失败', running: '执行中', pending: '等待执行', prepared: '已准备', rolled_back: '已回滚', superseded: '早前失败（已收正）', recovered: '已恢复', skipped: '已跳过' })[value] || '未知';",
}
for old, new in sentinels.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'app.js sentinel count mismatch: {old[:55]!r} -> {count}')
    text = text.replace(old, new, 1)
app.write_text(text, encoding='utf-8')

api = Path('public/api.php')
src = api.read_text(encoding='utf-8')
start = "        case 'settings':\n"
end = "        case 'update_check':\n"
if src.count(start) != 1 or src.count(end) != 1:
    raise SystemExit('api.php settings block sentinel mismatch')
before, tail = src.split(start, 1)
_old_block, after = tail.split(end, 1)
new_block = '''            $partialErrors = [];
            $optional = static function (string $module, callable $callback, mixed $fallback) use (&$partialErrors): mixed {
                try {
                    return $callback();
                } catch (Throwable $e) {
                    $reference = Support::randomHex(6);
                    error_log('[VF Infra][' . $reference . '] settings/' . $module . ': ' . Support::sanitizeError($e->getMessage()));
                    $partialErrors[] = [
                        'module' => $module,
                        'message' => '该模块暂时无法读取；现有设置和业务数据未被修改。',
                        'reference' => $reference,
                    ];
                    return $fallback;
                }
            };

            $cronStatus = $optional('自动检查状态', static fn(): array => (new CronStatusService())->get(), []);
            $checksDue = (int) $pdo->query("SELECT COUNT(*) FROM domains WHERE archived_at IS NULL AND (next_check_at IS NULL OR next_check_at<=datetime('now'))")->fetchColumn();
            $baselinePending = (int) $pdo->query("SELECT COUNT(*) FROM domains WHERE archived_at IS NULL AND last_checked_at IS NULL")->fetchColumn();
            $securitySummaries = $optional('安全记录', static function (): array {
                return array_map(static function (array $row): array {
                    return [
                        'id' => (int) ($row['id'] ?? 0),
                        'event_type' => (string) ($row['event_type'] ?? ''),
                        'severity' => (string) ($row['severity'] ?? 'info'),
                        'success' => !empty($row['success']),
                        'created_at' => (string) ($row['created_at'] ?? ''),
                    ];
                }, (new SecurityLogService())->list(50));
            }, []);
            $backups = $optional('备份记录', static fn(): array => (new BackupService())->list(), []);
            $notificationLogs = $optional('通知记录', static fn(): array => (new LogRepository())->notificationLogs(50), []);
            $restoreRuns = $optional('恢复记录', static fn(): array => Database::connection()->query('SELECT id,backup_id,started_at,finished_at,status FROM restore_runs ORDER BY id DESC LIMIT 30')->fetchAll(), []);
            $maintenanceRuns = $optional('维护记录', static fn(): array => Database::connection()->query('SELECT id,run_type,started_at,finished_at,status FROM maintenance_runs ORDER BY id DESC LIMIT 30')->fetchAll(), []);
            $retentionPreview = $optional('数据保留预览', static fn(): array => (new RetentionService())->preview(), ['counts' => [], 'protected_rules' => []]);
            $diagnostics = $optional('系统诊断', static fn(): array => (new SystemDiagnosticsService())->run(false), ['checks' => []]);
            $updateStatus = $optional('系统更新状态', static fn(): array => (new \\VFInfra\\Core\\Update\\UpdateManifestService())->status(), [
                'status' => 'check_failed',
                'current_version' => VF_DOMAIN_VERSION,
                'latest_version' => '',
                'can_update' => false,
                'check_error' => '更新状态暂时无法读取，现有系统不受影响。',
            ]);
            $updateHistory = $optional('更新历史', static fn(): array => (new \\VFInfra\\Core\\Update\\UpdateHistoryService())->list(30), []);
            $updatePending = $optional('更新准备状态', static fn(): ?array => \\VFInfra\\Core\\Update\\OnlineUpdateHandoff::publicPendingState(), null);
            $providers = $optional('服务商目录', static fn(): array => (new \\VFInfra\\Core\\ProviderAccountService())->providers(), []);
            $providerAccounts = $optional('连接账号', static fn(): array => (new \\VFInfra\\Core\\ProviderAccountService())->list(true), []);
            $assetSummary = $optional('资产汇总', static fn(): array => (new \\VFInfra\\Core\\AssetQueryService())->summary(), []);
            $updateTrust = $optional('更新信任状态', static function (): array {
                $label = 'core-updates + GitHub Release';
                $env = \\VFInfra\\Core\\Update\\UpdateContract::READ_TOKEN_ENV;
                $value = getenv($env);
                if ($value === false || trim((string) $value) === '') {
                    $value = $_ENV[$env] ?? ($_SERVER[$env] ?? '');
                }
                $ready = trim((string) $value) !== '';
                return ['mode' => $label, 'key_ids' => $ready ? [$label] : [], 'required_key_id' => $label, 'ready' => $ready];
            }, ['mode' => 'core-updates + GitHub Release', 'key_ids' => [], 'required_key_id' => 'core-updates + GitHub Release', 'ready' => false]);

            Http::json([
                'ok' => true,
                'settings' => Settings::allPublic(),
                'backups' => $backups,
                'notification_logs' => $notificationLogs,
                'restore_runs' => $restoreRuns,
                'maintenance_runs' => $maintenanceRuns,
                'security_logs' => $securitySummaries,
                'retention_preview' => $retentionPreview,
                'diagnostics' => $diagnostics,
                'update' => $updateStatus,
                'update_history' => $updateHistory,
                'update_pending' => $updatePending,
                'providers' => $providers,
                'provider_accounts' => $providerAccounts,
                'asset_summary' => $assetSummary,
                'update_trust' => $updateTrust,
                'partial_errors' => $partialErrors,
                'system' => [
                    'version' => VF_DOMAIN_VERSION,
                    'schema_version' => Migrator::latestVersion(),
                    'php_version' => PHP_VERSION,
                    'sqlite_version' => (string) $pdo->query('SELECT sqlite_version()')->fetchColumn(),
                    'sqlite_quick_check' => (string) $pdo->query('PRAGMA quick_check')->fetchColumn(),
                    'data_path' => 'Web 根外私有目录',
                    'base_url' => (string) Config::get('base_url'),
                    'allowed_hosts' => Config::get('allowed_hosts', []),
                    'host_mode' => (string) Config::get('host_mode', 'canonical_redirect'),
                    'current_host' => Support::requestHost(),
                    'cron_command' => 'php <SITE_ROOT>/cron.php',
                    'cron_status' => $cronStatus,
                    'last_cron' => $cronStatus['run'] ?? null,
                    'run_overview' => $optional('运行概览', static fn(): array => (new LogRepository())->overview(), []),
                    'domain_count' => (int) $pdo->query("SELECT COUNT(*) FROM domains WHERE archived_at IS NULL")->fetchColumn(),
                    'checks_due' => $checksDue,
                    'baseline_pending' => $baselinePending,
                    'pending_alerts' => $alerts->pendingCount() + (new \\VFInfra\\Core\\CoreAlertService())->workspacePendingCount(),
                ],
            ]);
            break;

'''
api.write_text(before + start + new_block + end + after, encoding='utf-8')
print('V254_SOURCE_PATCH=PASS')
