<?php
declare(strict_types=1);

/*
 * P05 · VF SEO · v1.2.2 Legacy Discovery Bridge
 * Purpose: bootstrap the shared server-side update reader only.
 * It MUST NOT change VERSION, Schema, or business data, and MUST NOT execute the formal upgrade.
 * Secret transport: ephemeral Sodium sealed box. Plaintext token is never rendered or logged.
 */

use VfSeo\PhpRuntime\Backup;
use VfSeo\PhpRuntime\Config;
use VfSeo\PhpRuntime\Database;
use VfSeo\PhpRuntime\PhpUpdater;
use VfSeo\PhpRuntime\RuntimePaths;
use VfSeo\PhpRuntime\Security;

const P05_BRIDGE_PROJECT = 'P05';
const P05_BRIDGE_FROM = '1.2.2';
const P05_BRIDGE_TARGET = '1.2.3';
const P05_BRIDGE_TTL = 900;
const P05_BRIDGE_MAX_ATTEMPTS = 5;

$root = __DIR__;
require_once $root . '/php/src/SiteInstance.php';
require_once $root . '/php/src/RuntimePaths.php';
require_once $root . '/php/src/Config.php';
require_once $root . '/php/src/Database.php';
require_once $root . '/php/src/Security.php';
require_once $root . '/php/src/Backup.php';
require_once $root . '/php/src/CoreUpdates/UpdateCore.php';
require_once $root . '/php/src/CoreUpdates/GitHubClient.php';
require_once $root . '/php/src/PhpUpdater.php';

function p05_bridge_json(int $status, array $payload): never {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, max-age=0');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    exit;
}

function p05_bridge_html_headers(): void {
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, max-age=0');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: no-referrer');
    header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
}

function p05_bridge_same_origin(): bool {
    $host = strtolower(trim((string)($_SERVER['HTTP_HOST'] ?? '')));
    if ($host === '') return false;
    $host = preg_replace('/:\\d+$/', '', $host) ?: $host;
    foreach (['HTTP_ORIGIN', 'HTTP_REFERER'] as $key) {
        $value = trim((string)($_SERVER[$key] ?? ''));
        if ($value === '') continue;
        $candidate = strtolower((string)(parse_url($value, PHP_URL_HOST) ?? ''));
        return $candidate !== '' && hash_equals($host, $candidate);
    }
    return false;
}

function p05_bridge_runtime(string $root): array {
    $version = trim((string)@file_get_contents($root . '/VERSION'));
    if (!hash_equals(P05_BRIDGE_FROM, $version)) throw new RuntimeException('BRIDGE_SOURCE_VERSION_MISMATCH');
    if (!extension_loaded('sodium')) throw new RuntimeException('BRIDGE_SODIUM_REQUIRED');
    if (!extension_loaded('curl')) throw new RuntimeException('BRIDGE_CURL_REQUIRED');
    if (!class_exists(ZipArchive::class)) throw new RuntimeException('BRIDGE_ZIP_REQUIRED');

    $config = Config::load($root);
    if ($config->version !== P05_BRIDGE_FROM) throw new RuntimeException('BRIDGE_CONFIG_VERSION_MISMATCH');
    if (Config::SCHEMA_VERSION !== 1) throw new RuntimeException('BRIDGE_SCHEMA_CONTRACT_MISMATCH');
    $db = new Database($config->sqlitePath, $config->sqliteBusyTimeoutMs);
    $schema = $db->one('SELECT schema_identity,schema_version FROM schema_metadata WHERE singleton=1');
    if (!is_array($schema) || ($schema['schema_identity'] ?? null) !== 'VF-SEO-SCHEMA@1' || (int)($schema['schema_version'] ?? 0) !== 1) {
        throw new RuntimeException('BRIDGE_RUNTIME_SCHEMA_MISMATCH');
    }
    $backup = new Backup($db, $config);
    return [$config, $db, $backup, new PhpUpdater($config, $backup)];
}

function p05_bridge_state_path(string $root): string {
    $dir = RuntimePaths::configDir($root);
    if (!is_dir($dir) || !is_writable($dir)) throw new RuntimeException('BRIDGE_PRIVATE_CONFIG_NOT_WRITABLE');
    return rtrim($dir, '/') . '/p05-v122-legacy-discovery-bridge.json';
}

function p05_bridge_state_read(string $path): ?array {
    if (!is_file($path)) return null;
    $raw = file_get_contents($path);
    if (!is_string($raw) || $raw === '') return null;
    $state = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
    return is_array($state) ? $state : null;
}

function p05_bridge_state_write(string $path, array $state): void {
    $tmp = $path . '.tmp-' . bin2hex(random_bytes(6));
    $bytes = json_encode($state, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    if (file_put_contents($tmp, $bytes, LOCK_EX) === false) throw new RuntimeException('BRIDGE_STATE_WRITE_FAILED');
    @chmod($tmp, 0600);
    if (!rename($tmp, $path)) { @unlink($tmp); throw new RuntimeException('BRIDGE_STATE_COMMIT_FAILED'); }
    @chmod($path, 0600);
}

function p05_bridge_new_init_state(): array {
    return [
        'project_id' => P05_BRIDGE_PROJECT,
        'current_version' => P05_BRIDGE_FROM,
        'target_version' => P05_BRIDGE_TARGET,
        'status' => 'awaiting-admin',
        'csrf' => bin2hex(random_bytes(24)),
        'created_at' => gmdate('c'),
        'expires_at_epoch' => time() + P05_BRIDGE_TTL,
        'attempts' => 0,
    ];
}

function p05_bridge_restore_runtime_env(string $path, string|false $before): void {
    if ($before === false) { @unlink($path); return; }
    $tmp = $path . '.rollback-' . bin2hex(random_bytes(5));
    if (file_put_contents($tmp, $before, LOCK_EX) === false) return;
    @chmod($tmp, 0600);
    @rename($tmp, $path);
    @chmod($path, 0600);
}

try {
    [$config, $db, $backup, $updater] = p05_bridge_runtime($root);
    $statePath = p05_bridge_state_path($root);
} catch (Throwable $e) {
    if (isset($_GET['relay'])) p05_bridge_json(409, ['ok' => false, 'status' => 'blocked', 'error' => preg_replace('/[^A-Z0-9_]/', '_', strtoupper($e->getMessage()))]);
    p05_bridge_html_headers();
    echo '<!doctype html><meta charset="utf-8"><title>P05 Bridge</title><h1>Bridge 已安全停止</h1><p>当前 Runtime 不符合 v1.2.2 Bridge 前置条件。</p>';
    exit;
}

$relay = (string)($_GET['relay'] ?? '');
if ($relay === 'info') {
    $state = p05_bridge_state_read($statePath);
    if (!is_array($state)) p05_bridge_json(425, ['ok' => false, 'status' => 'not-ready']);
    if (($state['status'] ?? '') === 'success') p05_bridge_json(200, ['ok' => true, 'status' => 'already-success', 'project_id' => P05_BRIDGE_PROJECT]);
    if (($state['status'] ?? '') !== 'ready') p05_bridge_json(425, ['ok' => false, 'status' => 'not-ready']);
    if ((int)($state['expires_at_epoch'] ?? 0) < time()) p05_bridge_json(410, ['ok' => false, 'status' => 'expired']);
    p05_bridge_json(200, [
        'ok' => true,
        'status' => 'ready',
        'project_id' => P05_BRIDGE_PROJECT,
        'current_version' => P05_BRIDGE_FROM,
        'target_version' => P05_BRIDGE_TARGET,
        'public_key_b64' => (string)$state['public_key_b64'],
        'nonce' => (string)$state['nonce'],
        'expires_at' => (string)$state['expires_at'],
    ]);
}

if ($relay === 'token') {
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') p05_bridge_json(405, ['ok' => false, 'status' => 'method-not-allowed']);
    $length = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
    if ($length < 1 || $length > 4096) p05_bridge_json(413, ['ok' => false, 'status' => 'payload-invalid']);
    $state = p05_bridge_state_read($statePath);
    if (!is_array($state) || ($state['status'] ?? '') !== 'ready') p05_bridge_json(409, ['ok' => false, 'status' => 'not-ready']);
    if ((int)($state['expires_at_epoch'] ?? 0) < time()) p05_bridge_json(410, ['ok' => false, 'status' => 'expired']);
    $attempts = (int)($state['attempts'] ?? 0) + 1;
    if ($attempts > P05_BRIDGE_MAX_ATTEMPTS) p05_bridge_json(429, ['ok' => false, 'status' => 'attempt-limit']);
    $state['attempts'] = $attempts;
    p05_bridge_state_write($statePath, $state);

    $body = json_decode((string)file_get_contents('php://input'), true, 16, JSON_THROW_ON_ERROR);
    $nonce = is_array($body) ? (string)($body['nonce'] ?? '') : '';
    $sealedB64 = is_array($body) ? (string)($body['sealed_token_b64'] ?? '') : '';
    if ($nonce === '' || !hash_equals((string)$state['nonce'], $nonce)) p05_bridge_json(422, ['ok' => false, 'status' => 'nonce-mismatch']);
    $sealed = base64_decode($sealedB64, true);
    $sk = base64_decode((string)$state['secret_key_b64'], true);
    $pk = base64_decode((string)$state['public_key_b64'], true);
    if (!is_string($sealed) || !is_string($sk) || !is_string($pk) || strlen($sk) !== SODIUM_CRYPTO_BOX_SECRETKEYBYTES || strlen($pk) !== SODIUM_CRYPTO_BOX_PUBLICKEYBYTES) {
        p05_bridge_json(422, ['ok' => false, 'status' => 'sealed-payload-invalid']);
    }
    $keypair = sodium_crypto_box_keypair_from_secretkey_and_publickey($sk, $pk);
    $token = sodium_crypto_box_seal_open($sealed, $keypair);
    if (!is_string($token) || $token === '') p05_bridge_json(422, ['ok' => false, 'status' => 'sealed-open-failed']);

    $runtimeEnv = RuntimePaths::runtimeEnvPath($root);
    $beforeEnv = @file_get_contents($runtimeEnv);
    try {
        $updater->saveCredential($token);
        if (function_exists('sodium_memzero')) sodium_memzero($token);
        $status = $updater->status();
        $target = (string)($status['manifest']['targetVersion'] ?? '');
        if (($status['channel'] ?? '') !== 'AVAILABLE' || ($status['updateAvailable'] ?? false) !== true || ($status['updaterReady'] ?? false) !== true || !hash_equals(P05_BRIDGE_TARGET, $target)) {
            throw new RuntimeException('BRIDGE_DISCOVERY_NOT_AVAILABLE');
        }
        $state['status'] = 'success';
        unset($state['secret_key_b64'], $state['csrf']);
        p05_bridge_state_write($statePath, $state);
        register_shutdown_function(static function () use ($statePath): void {
            @unlink($statePath);
            @unlink(__FILE__);
        });
        p05_bridge_json(200, [
            'ok' => true,
            'status' => 'success',
            'project_id' => P05_BRIDGE_PROJECT,
            'current_version' => P05_BRIDGE_FROM,
            'target_version' => P05_BRIDGE_TARGET,
            'channel' => 'AVAILABLE',
            'updater_ready' => true,
            'formal_upgrade_executed' => false,
        ]);
    } catch (Throwable $e) {
        if (is_string($token) && $token !== '' && function_exists('sodium_memzero')) sodium_memzero($token);
        p05_bridge_restore_runtime_env($runtimeEnv, $beforeEnv);
        putenv('VF_PRIVATE_READ_TOKEN');
        unset($_ENV['VF_PRIVATE_READ_TOKEN']);
        p05_bridge_json(422, ['ok' => false, 'status' => 'relay-failed', 'error' => preg_replace('/[^A-Z0-9_]/', '_', strtoupper($e->getMessage()))]);
    }
}

$status = $updater->status();
if (($status['channel'] ?? '') === 'AVAILABLE' && (string)($status['manifest']['targetVersion'] ?? '') === P05_BRIDGE_TARGET) {
    @unlink($statePath);
    register_shutdown_function(static fn() => @unlink(__FILE__));
    p05_bridge_html_headers();
    echo '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>P05 更新桥</title><body><h1>更新服务已就绪</h1><p>后台已可发现 V1.2.3。Bridge 已退出，不会执行正式升级。</p><p><a href="/">返回 VF SEO 后台，在“系统与更新”中完成升级</a></p></body></html>';
    exit;
}

$state = p05_bridge_state_read($statePath);
if (!is_array($state) || (int)($state['expires_at_epoch'] ?? 0) < time() || !in_array((string)($state['status'] ?? ''), ['awaiting-admin', 'ready'], true)) {
    $state = p05_bridge_new_init_state();
    p05_bridge_state_write($statePath, $state);
}

$error = '';
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
    if (!p05_bridge_same_origin()) {
        $error = '请求来源未通过安全校验。';
    } else {
        $csrf = (string)($_POST['csrf'] ?? '');
        $password = (string)($_POST['password'] ?? '');
        if ($csrf === '' || !hash_equals((string)($state['csrf'] ?? ''), $csrf)) {
            $error = '页面令牌已失效，请刷新后重试。';
        } elseif (strlen($password) < 1 || strlen($password) > 1024) {
            $error = '管理员密码无效。';
        } else {
            $admins = $db->all('SELECT id,password_hash FROM admins WHERE disabled_at IS NULL ORDER BY created_at ASC LIMIT 2');
            if (count($admins) !== 1 || !Security::verifyPassword($password, (string)($admins[0]['password_hash'] ?? ''))) {
                $error = '管理员认证失败。';
            } else {
                try {
                    $adminId = (string)$admins[0]['id'];
                    $backupResult = $backup->create($adminId);
                    $verify = $backup->verifyRun((string)$backupResult['id']);
                    if (($verify['ok'] ?? false) !== true) throw new RuntimeException('BRIDGE_BACKUP_VERIFY_FAILED');
                    $kp = sodium_crypto_box_keypair();
                    $pk = sodium_crypto_box_publickey($kp);
                    $sk = sodium_crypto_box_secretkey($kp);
                    $nonce = bin2hex(random_bytes(24));
                    $expires = time() + P05_BRIDGE_TTL;
                    $state = [
                        'project_id' => P05_BRIDGE_PROJECT,
                        'current_version' => P05_BRIDGE_FROM,
                        'target_version' => P05_BRIDGE_TARGET,
                        'status' => 'ready',
                        'public_key_b64' => base64_encode($pk),
                        'secret_key_b64' => base64_encode($sk),
                        'nonce' => $nonce,
                        'backup_id' => (string)$backupResult['id'],
                        'created_at' => gmdate('c'),
                        'expires_at' => gmdate('c', $expires),
                        'expires_at_epoch' => $expires,
                        'attempts' => 0,
                    ];
                    p05_bridge_state_write($statePath, $state);
                    if (function_exists('sodium_memzero')) { sodium_memzero($password); sodium_memzero($sk); }
                } catch (Throwable $e) {
                    $error = 'Bridge 初始化失败，系统未进入更新阶段。';
                }
            }
        }
        if (function_exists('sodium_memzero') && $password !== '') sodium_memzero($password);
    }
}

p05_bridge_html_headers();
$ready = (($state['status'] ?? '') === 'ready');
$csrfEsc = htmlspecialchars((string)($state['csrf'] ?? ''), ENT_QUOTES, 'UTF-8');
$errorEsc = htmlspecialchars($error, ENT_QUOTES, 'UTF-8');
?><!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P05 统一更新桥</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;background:#eef5f6;color:#15343b;margin:0;padding:32px}.card{max-width:720px;margin:5vh auto;background:#fff;border:1px solid #cfe0e3;border-radius:18px;padding:26px;box-shadow:0 20px 60px #17353c22}h1{margin:6px 0 8px;font-size:28px}.eyebrow{font-size:12px;font-weight:800;color:#078b98}.muted{color:#698087;line-height:1.7}.ok{background:#eaf8f4;border:1px solid #b8e5d9;padding:14px;border-radius:12px}.err{background:#fff0ed;border:1px solid #efc6bd;padding:12px;border-radius:10px;color:#933b2e}label{display:block;font-weight:750;margin:18px 0 7px}input{width:100%;box-sizing:border-box;padding:12px;border:1px solid #bed4d8;border-radius:10px;font:inherit}button,a.btn{display:inline-block;margin-top:16px;padding:11px 16px;border:0;border-radius:10px;background:#0795a4;color:#fff;font-weight:800;text-decoration:none;cursor:pointer}.steps{line-height:1.9}.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#edf7f8;color:#35636b;font-size:12px}</style></head><body><main class="card"><div class="eyebrow">P05 · VF SEO · GOV-DOC LEGACY UPDATE BRIDGE</div><h1>接通后台更新服务</h1><p class="muted">这是一次性 Discovery Bridge。它只让当前 V1.2.2 后台安全接入统一更新通道；不会修改版本、Schema 或业务数据，也不会执行正式升级。</p>
<?php if ($errorEsc !== ''): ?><div class="err"><?= $errorEsc ?></div><?php endif; ?>
<?php if (!$ready): ?>
<form method="post" autocomplete="off"><input type="hidden" name="csrf" value="<?= $csrfEsc ?>"><label>当前 VF SEO 管理员密码</label><input type="password" name="password" required maxlength="1024" autocomplete="current-password"><button type="submit">验证并准备安全连接</button></form>
<p class="muted">系统会先创建并验证 SQLite 恢复点，然后生成一次性 Sodium 公钥。共享更新凭据不会显示在此页面，也不会进入浏览器脚本。</p>
<?php else: ?>
<div class="ok"><strong>恢复点已通过，正在等待安全连接。</strong><div class="steps">✓ Production 仍为 V1.2.2<br>✓ Schema 仍为 1<br>✓ Backup 已创建并验证<br>✓ 临时 Sodium relay 已就绪<br>○ 等待统一更新凭据密封投递</div></div>
<p id="bridge-status" class="muted">完成后，后台“系统与更新”会直接发现 V1.2.3。</p>
<script>
(async()=>{const out=document.getElementById('bridge-status');for(let i=0;i<180;i++){try{const r=await fetch('/api/system/update/status',{credentials:'same-origin',cache:'no-store'});if(r.ok){const j=await r.json();if(j.channel==='AVAILABLE'&&j.manifest?.targetVersion==='1.2.3'){out.innerHTML='<strong>后台更新服务已就绪。</strong> 请返回 VF SEO，在“系统与更新”点击升级到 V1.2.3。';return;}}}catch(e){}await new Promise(r=>setTimeout(r,2000));}out.textContent='仍在等待安全连接；请保持此页面打开。';})();
</script>
<?php endif; ?>
<p><span class="badge">Formal upgrade executed: NO</span></p></main></body></html>
