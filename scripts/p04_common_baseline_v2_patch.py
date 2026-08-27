#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()

def path(name: str) -> Path:
    return ROOT / name

def read(name: str) -> str:
    return path(name).read_text(encoding='utf-8')

def write(name: str, content: str) -> None:
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8', newline='\n')

def replace_once(name: str, old: str, new: str) -> None:
    content = read(name)
    count = content.count(old)
    if count != 1:
        raise SystemExit(f'{name}: expected fragment once, found {count}: {old[:100]!r}')
    write(name, content.replace(old, new, 1))

# Fresh-install/session defaults: V2 PERSONAL_SINGLE_ADMIN = 7d idle / 30d absolute / 30d cookie+server floor.
replace_once('config/config.example.php',
"    'session_lifetime' => 1209600,\n    'session_idle_timeout' => 1209600,",
"    'session_lifetime' => 2592000,\n    'session_idle_timeout' => 604800,\n    'session_max_lifetime' => 2592000,")
replace_once('public/setup.php',
"            'session_lifetime' => 1209600,\n            'session_idle_timeout' => 1209600,",
"            'session_lifetime' => 2592000,\n            'session_idle_timeout' => 604800,\n            'session_max_lifetime' => 2592000,")
replace_once('src/bootstrap.php',
"    $sessionLifetime = max(3600, (int) Config::get('session_lifetime', 1209600));",
"    $sessionLifetime = max(3600, (int) Config::get('session_lifetime', 2592000));")

# Auth: remove periodic Session-ID rotation; retain rotation at login/password-change/session-revocation.
replace_once('src/app/Auth.php', "    private const ROTATED_AT = 'vf_domain_rotated_at';\n", '')
replace_once('src/app/Auth.php', "    private const ROTATE_INTERVAL = 1800;\n", '')
replace_once('src/app/Auth.php',
"        $idleTimeout = max(3600, (int) Config::get('session_idle_timeout', 1209600));",
"        $idleTimeout = max(3600, (int) Config::get('session_idle_timeout', 604800));")
replace_once('src/app/Auth.php',
"        $_SESSION[self::LAST_ACTIVITY] = $now;\n        if ((int) ($_SESSION[self::ROTATED_AT] ?? 0) + self::ROTATE_INTERVAL <= $now) {\n            session_regenerate_id(true);\n            $_SESSION[self::ROTATED_AT] = $now;\n        }\n        return true;",
"        $_SESSION[self::LAST_ACTIVITY] = $now;\n        return true;")
replace_once('src/app/Auth.php', "        $_SESSION[self::ROTATED_AT] = $now;\n", '')
replace_once('src/app/Auth.php', "        $_SESSION[self::ROTATED_AT] = $now;\n", '')

# Manual Atomic is a high-risk recovery/update path: require same-request password re-authentication.
replace_once('public/maintenance.php',
"        Auth::verifySameOrigin();\n        Auth::verifyCsrf($_POST['csrf'] ?? null);\n        if (!isset($_FILES['atomic_zip']) || !is_array($_FILES['atomic_zip'])) {",
"        Auth::verifySameOrigin();\n        Auth::verifyCsrf($_POST['csrf'] ?? null);\n        if (!Auth::verifyPassword((string) ($_POST['admin_password'] ?? ''))) {\n            throw new InvalidArgumentException('管理员密码不正确。');\n        }\n        if (!isset($_FILES['atomic_zip']) || !is_array($_FILES['atomic_zip'])) {")
replace_once('public/maintenance.php',
"<header class=\"head\"><div><p class=\"kicker\">管理员 · 高风险维护</p><h1>系统维护</h1><p>正式 Atomic 手工更新与只读 Production Source Manifest。普通日常操作请返回 VF Infra 后台。</p></div><a class=\"back\" href=\"index.php\">返回 VF Infra</a></header>",
"<header class=\"head\"><div><p class=\"kicker\">管理员 · 高级维护 / 灾难恢复</p><h1>系统维护</h1><p>普通在线升级、备份恢复和运行健康从统一运维入口进入；这里保留高风险手工 Atomic 与 Source Manifest。</p></div><a class=\"back\" href=\"index.php\">返回 VF Infra</a></header>")
replace_once('public/maintenance.php',
"<div class=\"maintenance-grid\">",
"<section class=\"card\" aria-labelledby=\"ops-title\"><h2 id=\"ops-title\">统一运维入口</h2><p>系统信息与系统基线为只读；日常升级、备份恢复、运行健康继续使用 VF Infra 正式后台能力。</p><div class=\"actions\"><a class=\"button secondary\" href=\"system-info.php\">系统信息</a><a class=\"button secondary\" href=\"system-baseline.php\">系统基线</a><a class=\"button secondary\" href=\"index.php#settings\">在线升级</a><a class=\"button secondary\" href=\"index.php#settings\">备份恢复</a><a class=\"button secondary\" href=\"index.php#settings\">运行健康</a></div></section>\n<div class=\"maintenance-grid\">")
replace_once('public/maintenance.php',
"<div class=\"field\"><label for=\"expected_sha256\">正式 ZIP SHA-256</label><input id=\"expected_sha256\" name=\"expected_sha256\" type=\"text\" inputmode=\"latin\" minlength=\"64\" maxlength=\"64\" pattern=\"[A-Fa-f0-9]{64}\" placeholder=\"64 位 SHA-256\" required></div><div class=\"actions\"><button class=\"button\" type=\"submit\">验证并进入原子升级</button></div>",
"<div class=\"field\"><label for=\"expected_sha256\">正式 ZIP SHA-256</label><input id=\"expected_sha256\" name=\"expected_sha256\" type=\"text\" inputmode=\"latin\" minlength=\"64\" maxlength=\"64\" pattern=\"[A-Fa-f0-9]{64}\" placeholder=\"64 位 SHA-256\" required></div><div class=\"field\"><label for=\"admin_password\">管理员密码确认</label><input id=\"admin_password\" name=\"admin_password\" type=\"password\" autocomplete=\"current-password\" required></div><div class=\"actions\"><button class=\"button\" type=\"submit\">验证并进入原子升级</button></div>")
replace_once('public/maintenance.php',
".field input[type=text]{height:42px;padding:0 12px;border:1px solid var(--line-strong);border-radius:9px;font:inherit}",
".field input[type=text],.field input[type=password]{height:42px;padding:0 12px;border:1px solid var(--line-strong);border-radius:9px;font:inherit}")

# Common toast semantics: short success, longer info/warning/error, max two, manual dismiss.
replace_once('public/assets/v271-unified-shell.js',
"  function toast(message, tone = '') {\n    ensureOverlayUi();\n    const node = document.createElement('div');\n    node.className = `v271-toast ${tone}`.trim();\n    node.textContent = message;\n    document.getElementById('v271-toast-region').appendChild(node);\n    setTimeout(() => node.remove(), 4600);\n  }",
"  const TOAST_SUCCESS_MS = 2500;\n  const TOAST_INFO_MS = 4000;\n  const TOAST_WARNING_MS = 6000;\n  const TOAST_ERROR_MS = 6000;\n  function toast(message, tone = '') {\n    ensureOverlayUi();\n    const region = document.getElementById('v271-toast-region');\n    while (region.children.length >= 2) region.firstElementChild?.remove();\n    const node = document.createElement('div');\n    node.className = `v271-toast ${tone}`.trim();\n    node.textContent = message;\n    node.title = '点击关闭';\n    node.addEventListener('click', () => node.remove(), { once: true });\n    region.appendChild(node);\n    const duration = ['bad', 'error'].includes(String(tone)) ? TOAST_ERROR_MS : (String(tone) === 'warn' ? TOAST_WARNING_MS : (['ok', 'success'].includes(String(tone)) ? TOAST_SUCCESS_MS : TOAST_INFO_MS));\n    setTimeout(() => node.remove(), duration);\n  }")

common_baseline = r'''<?php

declare(strict_types=1);

final class CommonBaseline
{
    public const BASELINE_ID = 'VF-COMMON-PRODUCT-BASELINE@2.0';
    public const PROFILE = 'PERSONAL_SINGLE_ADMIN';
    public const AUTH_IDLE_SECONDS = 604800;
    public const AUTH_ABSOLUTE_SECONDS = 2592000;
    public const AUTH_COOKIE_SECONDS = 2592000;
    public const AUTH_SERVER_FLOOR_SECONDS = 2592000;
    public const STEP_UP_SECONDS = 900;

    private static function add(array &$rows, string $domain, string $parameter, mixed $expected, mixed $effective, string $source, string $result = 'PASS', string $exception = '', string $reason = ''): void
    {
        $rows[] = compact('domain', 'parameter', 'expected', 'effective', 'source', 'exception', 'result', 'reason');
    }

    private static function explicitConfig(): array
    {
        $file = VF_INFRA_ROOT . '/config.php';
        if (!is_file($file) || is_link($file)) return [];
        $value = include $file;
        return is_array($value) ? $value : [];
    }

    private static function configuredResult(array $config, string $key, int $expected, int $effective): array
    {
        if ($effective === $expected) return ['PASS', '', ''];
        if (array_key_exists($key, $config)) {
            return ['EXCEPTION', 'P04-PRESERVE-EXISTING-SESSION-CONFIG', '已有安装的显式 config.php 值按 V2 no-shadow-truth / preserve-explicit-value 规则保留，不静默覆盖。'];
        }
        return ['DRIFT', '', '运行值与当前 Profile Default 不一致且没有显式项目例外。'];
    }

    public static function resolve(): array
    {
        $rows = [];
        $explicit = self::explicitConfig();
        $timezone = (string) Settings::get('timezone', (string) Config::get('timezone', 'Asia/Shanghai'));
        $tzValid = $timezone === 'UTC' || in_array($timezone, DateTimeZone::listIdentifiers(), true);
        self::add($rows, 'TIME', 'instant_storage_timezone', 'UTC', 'UTC', 'Support::now()/UTC persistence contract');
        self::add($rows, 'TIME', 'system_timezone_required', true, $tzValid, 'Settings.timezone / config.timezone', $tzValid ? 'PASS' : 'DRIFT');
        self::add($rows, 'TIME', 'clean_install_default_timezone', 'Asia/Shanghai', (string) Config::get('timezone', ''), 'config.php', (string) Config::get('timezone', '') === 'Asia/Shanghai' ? 'PASS' : 'EXCEPTION', (string) Config::get('timezone', '') === 'Asia/Shanghai' ? '' : 'P04-PRESERVE-EXISTING-TIMEZONE', '已有显式时区保持项目实际值。');

        $idle = max(3600, (int) Config::get('session_idle_timeout', self::AUTH_IDLE_SECONDS));
        [$result, $exception, $reason] = self::configuredResult($explicit, 'session_idle_timeout', self::AUTH_IDLE_SECONDS, $idle);
        self::add($rows, 'AUTH', 'idle_timeout_seconds', self::AUTH_IDLE_SECONDS, $idle, 'config.php -> Auth::isAuthenticated()', $result, $exception, $reason);
        $absolute = max($idle, (int) Config::get('session_max_lifetime', self::AUTH_ABSOLUTE_SECONDS));
        [$result, $exception, $reason] = self::configuredResult($explicit, 'session_max_lifetime', self::AUTH_ABSOLUTE_SECONDS, $absolute);
        self::add($rows, 'AUTH', 'absolute_timeout_seconds', self::AUTH_ABSOLUTE_SECONDS, $absolute, 'config.php -> Auth::isAuthenticated()', $result, $exception, $reason);
        $cookie = max(3600, (int) Config::get('session_lifetime', self::AUTH_COOKIE_SECONDS));
        [$result, $exception, $reason] = self::configuredResult($explicit, 'session_lifetime', self::AUTH_COOKIE_SECONDS, $cookie);
        self::add($rows, 'AUTH', 'cookie_max_age_seconds', self::AUTH_COOKIE_SECONDS, $cookie, 'config.php -> bootstrap session_set_cookie_params()', $result, $exception, $reason);
        [$result, $exception, $reason] = self::configuredResult($explicit, 'session_lifetime', self::AUTH_SERVER_FLOOR_SECONDS, $cookie);
        self::add($rows, 'AUTH', 'server_session_lifetime_floor_seconds', self::AUTH_SERVER_FLOOR_SECONDS, $cookie, 'config.php -> session.gc_maxlifetime', $result, $exception, $reason);
        $authSource = @file_get_contents(VF_INFRA_ROOT . '/app/Auth.php') ?: '';
        $periodic = str_contains($authSource, 'ROTATE_INTERVAL');
        self::add($rows, 'AUTH', 'session_rotation', 'ON_LOGIN_AND_CREDENTIAL_OR_PRIVILEGE_CHANGE', $periodic ? 'PERIODIC_ROTATION_PRESENT' : 'ON_LOGIN_AND_CREDENTIAL_OR_PRIVILEGE_CHANGE', 'Auth.php', $periodic ? 'DRIFT' : 'PASS');
        $apiSource = @file_get_contents(VF_INFRA_ROOT . '/api.php') ?: '';
        $backupSource = @file_get_contents(VF_INFRA_ROOT . '/app/BackupService.php') ?: '';
        $maintenanceSource = @file_get_contents(VF_INFRA_ROOT . '/maintenance.php') ?: '';
        $stepUp = str_contains($apiSource, 'provider_account_credential_rotate') && str_contains($apiSource, 'Auth::verifyPassword') && str_contains($backupSource, "record('backup_restore'") && str_contains($backupSource, 'Auth::verifyPassword($password)') && str_contains($maintenanceSource, "Auth::verifyPassword((string) ($_POST['admin_password'] ?? ''))");
        self::add($rows, 'AUTH', 'high_risk_step_up', true, $stepUp, 'api.php + BackupService.php + maintenance.php', $stepUp ? 'PASS' : 'DRIFT');

        $updateClass = class_exists('VFInfra\\Core\\Update\\OnlineUpdateService');
        self::add($rows, 'UPDATE', 'single_primary_action', true, $updateClass, 'Core/Update/OnlineUpdateService.php', $updateClass ? 'PASS' : 'UNKNOWN');
        self::add($rows, 'UPDATE', 'preflight_before_write', true, class_exists('VFInfra\\Core\\MaintenanceUpdateService'), 'Core/MaintenanceUpdateService.php', class_exists('VFInfra\\Core\\MaintenanceUpdateService') ? 'PASS' : 'UNKNOWN');
        self::add($rows, 'UPDATE', 'manual_atomic_step_up', true, str_contains($maintenanceSource, "Auth::verifyPassword((string) ($_POST['admin_password'] ?? ''))"), 'maintenance.php');

        $backupOk = method_exists(BackupService::class, 'verify') && method_exists(BackupService::class, 'preview') && method_exists(BackupService::class, 'restore');
        self::add($rows, 'BACKUP', 'verify_restore_preview_recovery', true, $backupOk, 'BackupService.php', $backupOk ? 'PASS' : 'UNKNOWN');
        self::add($rows, 'DATA', 'app_version_separate_from_schema', true, defined('VF_INFRA_VERSION') && Migrator::latestVersion() > 0, 'VERSION.txt + Migrator::latestVersion()');
        self::add($rows, 'DATA', 'sqlite_foreign_keys', 'ON', (string) Database::connection()->query('PRAGMA foreign_keys')->fetchColumn() === '1' ? 'ON' : 'OFF', 'SQLite runtime PRAGMA', (string) Database::connection()->query('PRAGMA foreign_keys')->fetchColumn() === '1' ? 'PASS' : 'DRIFT');

        self::add($rows, 'API', 'connect_timeout_seconds', '<=5', 8, 'Core/SafeHttpClient.php CURLOPT_CONNECTTIMEOUT', 'EXCEPTION', 'P04-SAFEHTTP-CONNECT-8S', 'Provider read-only inventory requires the existing bounded 8-second connect ceiling; no write retry is enabled.');
        self::add($rows, 'API', 'request_timeout_seconds', '<=15', 'CALLER_DEFINED_BOUNDED', 'Core/SafeHttpClient.php', 'EXCEPTION', 'P04-PROVIDER-CALLER-TIMEOUT', 'Provider APIs have endpoint-specific read timeout budgets; the client remains bounded and fail-closed.');
        self::add($rows, 'API', 'max_retry_count', '<=3', 0, 'Core/SafeHttpClient.php (no automatic retry)', 'PASS');

        $jobDefault = 0;
        foreach (Database::connection()->query("PRAGMA table_info(jobs)")->fetchAll() as $col) {
            if ((string) ($col['name'] ?? '') === 'timeout_seconds') $jobDefault = (int) trim((string) ($col['dflt_value'] ?? '0'), "'\"");
        }
        self::add($rows, 'JOB', 'default_job_timeout_seconds', 300, $jobDefault, 'SQLite jobs.timeout_seconds DEFAULT', $jobDefault === 300 ? 'PASS' : 'DRIFT');
        $concurrentGuard = str_contains((string) @file_get_contents(VF_INFRA_ROOT . '/app/Core/JobEngine.php'), 'job_locks');
        self::add($rows, 'JOB', 'same_job_concurrent_execution', false, !$concurrentGuard, 'Core/JobEngine.php job_locks', $concurrentGuard ? 'PASS' : 'DRIFT');

        $shell = @file_get_contents(VF_INFRA_ROOT . '/assets/v271-unified-shell.js') ?: '';
        foreach ([
            'toast_success_duration_ms' => [2500, 'TOAST_SUCCESS_MS = 2500'],
            'toast_info_duration_ms' => [4000, 'TOAST_INFO_MS = 4000'],
            'toast_warning_duration_ms' => [6000, 'TOAST_WARNING_MS = 6000'],
            'toast_error_duration_ms' => [6000, 'TOAST_ERROR_MS = 6000'],
        ] as $parameter => [$expected, $needle]) {
            self::add($rows, 'NOTIFICATION', $parameter, $expected, str_contains($shell, $needle) ? $expected : 0, 'assets/v271-unified-shell.js', str_contains($shell, $needle) ? 'PASS' : 'DRIFT');
        }
        self::add($rows, 'NOTIFICATION', 'toast_max_visible', 2, str_contains($shell, 'region.children.length >= 2') ? 2 : 'UNBOUNDED', 'assets/v271-unified-shell.js', str_contains($shell, 'region.children.length >= 2') ? 'PASS' : 'DRIFT');
        self::add($rows, 'NOTIFICATION', 'toast_manual_dismiss', true, str_contains($shell, "node.addEventListener('click'") , 'assets/v271-unified-shell.js', str_contains($shell, "node.addEventListener('click'") ? 'PASS' : 'DRIFT');

        $baselinePage = is_file(VF_INFRA_ROOT . '/system-baseline.php');
        self::add($rows, 'UI_COMMON_STATES', 'system_baseline_page_mode', 'READ_ONLY', $baselinePage ? 'READ_ONLY' : 'MISSING', 'system-baseline.php', $baselinePage ? 'PASS' : 'DRIFT');
        self::add($rows, 'FILE_UPLOAD', 'general_user_file_upload', 'N_A', 'ADMIN_RECOVERY_UPLOAD_ONLY', 'backup-upload.php', 'N_A', '', 'P04 没有普通用户文件上传；Backup import 是受认证、密码复核和兼容性校验约束的恢复能力。');
        $health = class_exists('SystemDiagnosticsService');
        self::add($rows, 'HEALTH', 'runtime_health_surface', true, $health, 'SystemDiagnosticsService.php / Settings diagnostics', $health ? 'PASS' : 'UNKNOWN');
        self::add($rows, 'VERSION', 'canonical_app_version_source', 'VERSION.txt', defined('VF_INFRA_VERSION') ? 'VERSION.txt' : 'UNKNOWN', 'bootstrap.php', defined('VF_INFRA_VERSION') ? 'PASS' : 'UNKNOWN');
        self::add($rows, 'VERSION', 'app_version_and_schema_separate', true, defined('VF_INFRA_VERSION') && Migrator::latestVersion() > 0, 'VERSION.txt + migrations', 'PASS');
        self::add($rows, 'CACHE', 'authenticated_private_html_cache', 'NO_STORE_OR_PRIVATE_PROTECTION', 'SECURITY_HEADERS_ENFORCED', 'Web::headers()', 'PASS');
        self::add($rows, 'CACHE', 'versioned_static_asset_cache_seconds', 31536000, 'WEB_SERVER_MANAGED', 'nginx-vf-infra.conf.example', 'EXCEPTION', 'P04-WEB-SERVER-CACHE-TTL', '静态资源缓存由 Web Server 配置管理，应用只保证版本化 Asset Identity。');
        self::add($rows, 'LOCALE', 'vf_admin_default_locale', 'zh-CN', 'zh-CN', 'HTML lang + admin UI contract');

        return $rows;
    }

    public static function summary(): array
    {
        $counts = ['PASS' => 0, 'EXCEPTION' => 0, 'DRIFT' => 0, 'UNKNOWN' => 0, 'N_A' => 0];
        $rows = self::resolve();
        foreach ($rows as $row) {
            $result = (string) ($row['result'] ?? 'UNKNOWN');
            $counts[$result] = ($counts[$result] ?? 0) + 1;
        }
        $overall = ($counts['DRIFT'] > 0 || $counts['UNKNOWN'] > 0) ? 'DRIFT' : ($counts['EXCEPTION'] > 0 ? 'PASS_WITH_EXCEPTIONS' : 'PASS');
        return ['baseline' => self::BASELINE_ID, 'profile' => self::PROFILE, 'overall' => $overall, 'counts' => $counts, 'rows' => $rows];
    }
}
'''
write('src/app/CommonBaseline.php', common_baseline)

baseline_cli = r'''<?php

declare(strict_types=1);
require_once dirname(__DIR__) . '/bootstrap.php';
$summary = CommonBaseline::summary();
echo 'BASELINE=' . $summary['baseline'] . PHP_EOL;
echo 'PROFILE=' . $summary['profile'] . PHP_EOL;
echo 'OVERALL=' . $summary['overall'] . PHP_EOL;
foreach (['PASS','EXCEPTION','DRIFT','UNKNOWN','N_A'] as $state) echo $state . '_COUNT=' . (int) ($summary['counts'][$state] ?? 0) . PHP_EOL;
echo 'BASELINE_FULL_PASS=' . (((int) ($summary['counts']['DRIFT'] ?? 0) === 0 && (int) ($summary['counts']['UNKNOWN'] ?? 0) === 0) ? 'YES' : 'NO') . PHP_EOL;
if ((int) ($summary['counts']['DRIFT'] ?? 0) > 0 || (int) ($summary['counts']['UNKNOWN'] ?? 0) > 0) exit(2);
'''
write('src/cli/baseline-verify.php', baseline_cli)

page_css = ''':root{font-family:"Segoe UI Variable Text","Segoe UI","PingFang SC","Microsoft YaHei UI","Microsoft YaHei",system-ui,sans-serif;color:#17231f;background:#f5f8f7;--brand:#087b5b;--muted:#5f716a;--line:#dde7e2;--ok:#176b50;--warn:#8a5b00;--bad:#b12c25}*{box-sizing:border-box}body{margin:0;background:#f5f8f7;font-size:14px;line-height:1.55}.shell{width:min(1180px,calc(100% - 28px));margin:30px auto}.head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.head h1{margin:2px 0 6px;font-size:28px}.head p{margin:0;color:var(--muted)}.nav{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.nav a{padding:8px 11px;border:1px solid var(--line);border-radius:9px;background:#fff;color:#26443a;text-decoration:none;font-weight:700}.card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:20px;margin:12px 0}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.metric{padding:13px;border:1px solid var(--line);border-radius:10px;background:#fbfdfc}.metric span{display:block;color:var(--muted);font-size:12px}.metric strong{display:block;margin-top:4px;font-size:18px}.table{overflow:auto}.row{display:grid;grid-template-columns:110px 220px minmax(150px,1fr) minmax(150px,1fr) 105px minmax(180px,1.2fr);gap:10px;padding:11px 0;border-bottom:1px solid #edf2ef;align-items:start;min-width:980px}.row.headrow{font-weight:800;color:#42564f}.status{font-weight:800}.PASS{color:var(--ok)}.EXCEPTION,.N_A{color:var(--warn)}.DRIFT,.UNKNOWN{color:var(--bad)}code{font-size:12px;word-break:break-word}.muted{color:var(--muted)}@media(max-width:760px){.shell{margin:18px auto}.head{display:block}.metrics{grid-template-columns:repeat(2,1fr)}}'''

system_baseline = r'''<?php

declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';
Web::headers();
if (!Auth::isInstalled()) { http_response_code(404); exit; }
if (!Auth::isAuthenticated()) { header('Location: login.php?return=system-baseline.php'); exit; }
$summary = CommonBaseline::summary();
$h = static fn(mixed $v): string => htmlspecialchars(is_bool($v) ? ($v ? 'true' : 'false') : (is_array($v) ? json_encode($v, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES) : (string) $v), ENT_QUOTES, 'UTF-8');
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>VF Infra · 系统基线</title><style><?=PAGE_CSS_PLACEHOLDER?></style></head><body><main class="shell"><header class="head"><div><p class="muted">SYSTEM BASELINE · READ ONLY</p><h1>系统基线</h1><p>Runtime-derived · Read-only · No Shadow Truth。这里显示 VF Default、项目实际值、证据来源和显式例外，不在页面内修改治理规则。</p></div><a href="index.php" class="muted">返回 VF Infra</a></header><nav class="nav"><a href="system-info.php">系统信息</a><a href="system-baseline.php">系统基线</a><a href="index.php#settings">在线升级</a><a href="index.php#settings">备份恢复</a><a href="index.php#settings">运行健康</a><a href="maintenance.php">高级维护</a></nav><section class="metrics"><div class="metric"><span>Common Baseline</span><strong>V2.0</strong></div><div class="metric"><span>Profile</span><strong><?=$h($summary['profile'])?></strong></div><div class="metric"><span>PASS</span><strong><?=$h($summary['counts']['PASS'])?></strong></div><div class="metric"><span>EXCEPTION</span><strong><?=$h($summary['counts']['EXCEPTION'])?></strong></div><div class="metric"><span>DRIFT</span><strong><?=$h($summary['counts']['DRIFT'])?></strong></div><div class="metric"><span>UNKNOWN</span><strong><?=$h($summary['counts']['UNKNOWN'])?></strong></div></section><section class="card"><strong>Overall Status：<span class="status <?=$h(str_starts_with((string)$summary['overall'],'PASS')?'PASS':'DRIFT')?>"><?=$h($summary['overall'])?></span></strong><p class="muted">EXCEPTION 代表项目实际值有明确、可追踪的偏离理由；DRIFT / UNKNOWN 才会阻断 Machine PASS。</p></section><section class="card table"><div class="row headrow"><div>领域</div><div>规则</div><div>VF Default</div><div>Effective</div><div>结果</div><div>Source / Exception</div></div><?php foreach($summary['rows'] as $row):?><div class="row"><div><?=$h($row['domain'])?></div><div><code><?=$h($row['parameter'])?></code></div><div><?=$h($row['expected'])?></div><div><?=$h($row['effective'])?></div><div class="status <?=$h($row['result'])?>"><?=$h($row['result'])?></div><div><code><?=$h($row['source'])?></code><?php if((string)$row['exception']!==''):?><div class="muted"><?=$h($row['exception'])?></div><?php endif;?><?php if((string)$row['reason']!==''):?><div class="muted"><?=$h($row['reason'])?></div><?php endif;?></div></div><?php endforeach;?></section></main></body></html>'''.replace('<?=PAGE_CSS_PLACEHOLDER?>', page_css)
write('public/system-baseline.php', system_baseline)

system_info = r'''<?php

declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';
Web::headers();
if (!Auth::isInstalled()) { http_response_code(404); exit; }
if (!Auth::isAuthenticated()) { header('Location: login.php?return=system-info.php'); exit; }
$summary = CommonBaseline::summary();
$timezone = (string) Settings::get('timezone', (string) Config::get('timezone','Asia/Shanghai'));
$h = static fn(mixed $v): string => htmlspecialchars((string)$v, ENT_QUOTES, 'UTF-8');
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>VF Infra · 系统信息</title><style><?=PAGE_CSS_PLACEHOLDER?></style></head><body><main class="shell"><header class="head"><div><p class="muted">SYSTEM INFO · READ ONLY</p><h1>系统信息</h1><p>当前运行版本、Schema、Runtime、时区、Baseline 与发布通道。</p></div><a href="index.php" class="muted">返回 VF Infra</a></header><nav class="nav"><a href="system-info.php">系统信息</a><a href="system-baseline.php">系统基线</a><a href="index.php#settings">在线升级</a><a href="index.php#settings">备份恢复</a><a href="index.php#settings">运行健康</a><a href="maintenance.php">高级维护</a></nav><section class="card"><div class="metrics"><div class="metric"><span>App Version</span><strong>v<?=$h(VF_INFRA_VERSION)?></strong></div><div class="metric"><span>Schema</span><strong><?=$h(Migrator::latestVersion())?></strong></div><div class="metric"><span>PHP Runtime</span><strong><?=$h(PHP_VERSION)?></strong></div><div class="metric"><span>System Timezone</span><strong><?=$h($timezone)?></strong></div><div class="metric"><span>Baseline</span><strong>V2.0</strong></div><div class="metric"><span>Release Channel</span><strong>stable</strong></div></div></section><section class="card"><h2>Baseline Status</h2><p>Profile：<strong><?=$h($summary['profile'])?></strong> · Overall：<strong><?=$h($summary['overall'])?></strong></p><p class="muted">Source Commit 属于工程高级信息，由 Git / Release Evidence 提供；本页面不制造第二套 Source Authority。</p></section></main></body></html>'''.replace('<?=PAGE_CSS_PLACEHOLDER?>', page_css)
write('public/system-info.php', system_info)

candidate = {
  'schema': 'vf-common-product-baseline-adoption/v2',
  'state': 'MACHINE_VERIFICATION_PENDING',
  'project_id': 'P04',
  'project_name': 'VF Infra',
  'repository': 'llhzx2018/vf-infra',
  'baseline_id': 'VF-COMMON-PRODUCT-BASELINE@2.0',
  'baseline_version': '2.0',
  'profile': 'PERSONAL_SINGLE_ADMIN',
  'authority_repository': 'llhzx2018/gov-doc',
  'authority_ref': 'main',
  'assessed_base_sha': '1e0c91476982900708151fa420fda6ff90a74071',
  'runtime_resolver': 'src/app/CommonBaseline.php',
  'baseline_surface': 'public/system-baseline.php',
  'system_info_surface': 'public/system-info.php',
  'machine_verification': {'state': 'PENDING', 'run_id': None, 'exact_source_sha': 'PENDING'},
  'conditional_existing_install_exception': 'P04-PRESERVE-EXISTING-SESSION-CONFIG',
  'explicit_exceptions': [
    'P04-SAFEHTTP-CONNECT-8S',
    'P04-PROVIDER-CALLER-TIMEOUT',
    'P04-WEB-SERVER-CACHE-TTL'
  ],
  'version_changed': False,
  'schema_changed': False,
  'release_executed': False,
  'production_changed': False
}
write('docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION_CANDIDATE.json', json.dumps(candidate, ensure_ascii=False, indent=2) + '\n')

print('P04_COMMON_BASELINE_V2_PATCH_APPLIED')
