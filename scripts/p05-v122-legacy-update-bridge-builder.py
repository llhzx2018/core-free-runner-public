#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_VERSION = "1.2.2"
TARGET_VERSION = "1.2.3"
BRIDGE_NAME = "P05_V1.2.2_TO_UNIFIED_UPDATE_BRIDGE.php"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def locate_root(extracted: Path) -> Path:
    if (extracted / "VERSION").is_file():
        return extracted
    children = [p for p in extracted.iterdir() if p.is_dir()]
    if len(children) == 1 and (children[0] / "VERSION").is_file():
        return children[0]
    raise SystemExit("cannot locate FULL root")


def build_manifest(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in {"VF_INSTALL_INSTANCE.json", BRIDGE_NAME}:
            continue
        out[rel] = sha256(p)
    if not out or "VERSION" not in out or "php/src/PhpUpdater.php" not in out:
        raise SystemExit("FULL manifest missing required files")
    return out


def php_manifest(manifest: dict[str, str]) -> str:
    rows = ["["]
    for path, digest in manifest.items():
        rows.append("        " + json.dumps(path) + " => " + json.dumps(digest) + ",")
    rows.append("    ]")
    return "\n".join(rows)


TEMPLATE = r'''<?php
declare(strict_types=1);

use VfSeo\PhpRuntime\Backup;
use VfSeo\PhpRuntime\Config;
use VfSeo\PhpRuntime\Database;
use VfSeo\PhpRuntime\PhpUpdater;
use VfSeo\PhpRuntime\RuntimePaths;
use VfSeo\PhpRuntime\Security;

/**
 * P05 v1.2.2 one-time Legacy Update Bridge.
 *
 * GOV-DOC contract:
 * - does NOT change Product VERSION, Schema, source files or business data;
 * - never embeds, prints or asks OWNER for VF_PRIVATE_READ_TOKEN;
 * - existing admin authentication creates a verified recovery point;
 * - public Runner delivers the shared read-only token only as a sodium sealed payload;
 * - existing v1.2.2 PhpUpdater::saveCredential() validates core-updates + Product Release
 *   before atomically persisting the token to pointer-bound private runtime.env;
 * - bridge stops at READY. Formal v1.2.2 -> v1.2.3 Atomic upgrade remains the normal
 *   authenticated System Update action.
 */
final class P05LegacyUpdateBridge
{
    private const SOURCE_VERSION = '@@SOURCE_VERSION@@';
    private const TARGET_VERSION = '@@TARGET_VERSION@@';
    private const STATE_TTL = 1800;
    private const EXPECTED_FILES = @@MANIFEST@@;

    private Config $config;
    private Database $db;
    private Backup $backup;
    private PhpUpdater $updater;
    private string $statePath;

    public function __construct(private readonly string $root)
    {
        $root = rtrim($root, '/');
        foreach ([
            'php/src/RuntimePaths.php', 'php/src/Config.php', 'php/src/Database.php',
            'php/src/Security.php', 'php/src/Backup.php', 'php/src/SiteInstance.php',
            'php/src/CoreUpdates/UpdateCore.php', 'php/src/CoreUpdates/GitHubClient.php',
            'php/src/PhpUpdater.php',
        ] as $required) {
            require_once $root . '/' . $required;
        }
        $this->config = Config::load($root);
        $this->db = new Database($this->config->sqlitePath, $this->config->sqliteBusyTimeoutMs);
        $this->backup = new Backup($this->db, $this->config);
        $this->updater = new PhpUpdater($this->config, $this->backup);
        $private = rtrim(dirname($this->config->backupDir), '/') . '/bridge';
        if (!is_dir($private) && !@mkdir($private, 0700, true) && !is_dir($private)) {
            throw new RuntimeException('BRIDGE_PRIVATE_DIR_CREATE_FAILED');
        }
        @chmod($private, 0700);
        $this->statePath = $private . '/p05-v122-unified-update-bridge.json';
    }

    /** @return array<string,mixed> */
    public function sourceCheck(): array
    {
        if (!hash_equals(self::SOURCE_VERSION, $this->config->version)) {
            throw new RuntimeException('BRIDGE_SOURCE_VERSION_MISMATCH');
        }
        $checked = 0;
        foreach (self::EXPECTED_FILES as $relative => $expected) {
            $path = rtrim($this->root, '/') . '/' . $relative;
            if (!is_file($path) || is_link($path)) throw new RuntimeException('BRIDGE_SOURCE_FILE_MISSING:' . $relative);
            $actual = hash_file('sha256', $path);
            if (!is_string($actual) || !hash_equals($expected, strtolower($actual))) {
                throw new RuntimeException('BRIDGE_SOURCE_IDENTITY_MISMATCH:' . $relative);
            }
            $checked++;
        }
        $integrity = $this->db->integrity();
        if (($integrity['ok'] ?? false) !== true) throw new RuntimeException('BRIDGE_DATABASE_INTEGRITY_FAILED');
        return ['ok' => true, 'version' => self::SOURCE_VERSION, 'schema' => Config::SCHEMA_VERSION, 'filesChecked' => $checked];
    }

    /** @return array<string,mixed> */
    public function initialize(string $password): array
    {
        $this->sourceCheck();
        if (!extension_loaded('sodium')) throw new RuntimeException('BRIDGE_SODIUM_REQUIRED');
        $existing = $this->readState();
        if (is_array($existing) && !$this->expired($existing) && in_array(($existing['status'] ?? ''), ['WAITING_RELAY', 'READY'], true)) {
            return $this->publicState($existing);
        }
        if ($existing !== null) $this->deleteState();

        $admins = $this->db->all('SELECT id,password_hash FROM admins WHERE disabled_at IS NULL LIMIT 10');
        $actorId = '';
        foreach ($admins as $admin) {
            if (Security::verifyPassword($password, (string) ($admin['password_hash'] ?? ''))) {
                $actorId = (string) ($admin['id'] ?? '');
                break;
            }
        }
        if ($actorId === '') throw new RuntimeException('BRIDGE_ADMIN_AUTH_FAILED');

        $backup = $this->backup->create($actorId);
        $keypair = sodium_crypto_box_keypair();
        $publicKey = sodium_crypto_box_publickey($keypair);
        $nonce = bin2hex(random_bytes(24));
        $now = time();
        $state = [
            'version' => 1,
            'status' => 'WAITING_RELAY',
            'sourceVersion' => self::SOURCE_VERSION,
            'targetVersion' => self::TARGET_VERSION,
            'publicKey' => base64_encode($publicKey),
            'keypair' => base64_encode($keypair),
            'nonce' => $nonce,
            'backupId' => (string) ($backup['id'] ?? ''),
            'createdAt' => gmdate('c', $now),
            'expiresAt' => $now + self::STATE_TTL,
        ];
        $this->writeState($state);
        return $this->publicState($state);
    }

    /** @return array<string,mixed> */
    public function relayInfo(): array
    {
        $state = $this->readState();
        if (!is_array($state)) return ['ok' => true, 'status' => 'NOT_READY', 'sourceVersion' => self::SOURCE_VERSION, 'targetVersion' => self::TARGET_VERSION];
        if ($this->expired($state)) {
            $this->deleteState();
            return ['ok' => true, 'status' => 'EXPIRED', 'sourceVersion' => self::SOURCE_VERSION, 'targetVersion' => self::TARGET_VERSION];
        }
        return $this->publicState($state);
    }

    /** @return array<string,mixed> */
    public function deliver(string $nonce, string $sealedBase64): array
    {
        $state = $this->readState();
        if (!is_array($state) || ($state['status'] ?? '') !== 'WAITING_RELAY') throw new RuntimeException('BRIDGE_NOT_WAITING');
        if ($this->expired($state)) { $this->deleteState(); throw new RuntimeException('BRIDGE_EXPIRED'); }
        if (!hash_equals((string) ($state['nonce'] ?? ''), $nonce)) throw new RuntimeException('BRIDGE_NONCE_MISMATCH');
        $sealed = base64_decode($sealedBase64, true);
        $keypair = base64_decode((string) ($state['keypair'] ?? ''), true);
        if (!is_string($sealed) || !is_string($keypair) || $sealed === '' || $keypair === '' || strlen($sealed) > 2048) {
            throw new RuntimeException('BRIDGE_SEALED_PAYLOAD_INVALID');
        }
        $token = sodium_crypto_box_seal_open($sealed, $keypair);
        if (!is_string($token) || $token === '') throw new RuntimeException('BRIDGE_SEALED_PAYLOAD_OPEN_FAILED');
        try {
            $result = $this->updater->saveCredential($token);
        } finally {
            if (function_exists('sodium_memzero') && is_string($token)) sodium_memzero($token);
        }
        if (($result['credentialConfigured'] ?? false) !== true) throw new RuntimeException('BRIDGE_CREDENTIAL_SAVE_NOT_CONFIRMED');
        $status = $this->updater->status();
        if (($status['channel'] ?? '') !== 'AVAILABLE'
            || ($status['updaterReady'] ?? false) !== true
            || (string) (($status['manifest']['targetVersion'] ?? '')) !== self::TARGET_VERSION) {
            throw new RuntimeException('BRIDGE_DISCOVERY_NOT_READY');
        }
        $ready = [
            'version' => 1,
            'status' => 'READY',
            'sourceVersion' => self::SOURCE_VERSION,
            'targetVersion' => self::TARGET_VERSION,
            'nonceHash' => hash('sha256', $nonce),
            'backupId' => (string) ($state['backupId'] ?? ''),
            'readyAt' => gmdate('c'),
            'expiresAt' => time() + 300,
        ];
        $this->writeState($ready);
        return $this->publicState($ready);
    }

    /** @return array<string,mixed> */
    public function cleanup(string $nonce, bool $deleteBridge = false): array
    {
        $state = $this->readState();
        if (!is_array($state) || ($state['status'] ?? '') !== 'READY') throw new RuntimeException('BRIDGE_NOT_READY');
        if (!hash_equals((string) ($state['nonceHash'] ?? ''), hash('sha256', $nonce))) throw new RuntimeException('BRIDGE_CLEANUP_NONCE_MISMATCH');
        $this->deleteState();
        if ($deleteBridge) {
            $file = __FILE__;
            register_shutdown_function(static function () use ($file): void { if (is_file($file) && !is_link($file)) @unlink($file); });
        }
        return ['ok' => true, 'status' => 'CLEANED', 'targetVersion' => self::TARGET_VERSION];
    }

    private function expired(array $state): bool { return (int) ($state['expiresAt'] ?? 0) < time(); }

    /** @return array<string,mixed>|null */
    private function readState(): ?array
    {
        if (!is_file($this->statePath) || is_link($this->statePath) || !is_readable($this->statePath)) return null;
        try {
            $decoded = json_decode((string) file_get_contents($this->statePath), true, 32, JSON_THROW_ON_ERROR);
            return is_array($decoded) ? $decoded : null;
        } catch (Throwable) { return null; }
    }

    private function writeState(array $state): void
    {
        $bytes = json_encode($state, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . "\n";
        $tmp = $this->statePath . '.tmp-' . bin2hex(random_bytes(6));
        $h = @fopen($tmp, 'xb');
        if ($h === false) throw new RuntimeException('BRIDGE_STATE_CREATE_FAILED');
        try {
            if (@fwrite($h, $bytes) !== strlen($bytes) || !@fflush($h)) throw new RuntimeException('BRIDGE_STATE_WRITE_FAILED');
            if (function_exists('fsync')) @fsync($h);
        } finally { @fclose($h); }
        @chmod($tmp, 0600);
        if (!@rename($tmp, $this->statePath)) { @unlink($tmp); throw new RuntimeException('BRIDGE_STATE_COMMIT_FAILED'); }
        @chmod($this->statePath, 0600);
    }

    private function deleteState(): void { if (is_file($this->statePath) && !is_link($this->statePath)) @unlink($this->statePath); }

    /** @return array<string,mixed> */
    private function publicState(array $state): array
    {
        $out = [
            'ok' => true,
            'status' => (string) ($state['status'] ?? 'UNKNOWN'),
            'sourceVersion' => self::SOURCE_VERSION,
            'targetVersion' => self::TARGET_VERSION,
            'expiresAt' => (int) ($state['expiresAt'] ?? 0),
            'backupId' => (string) ($state['backupId'] ?? ''),
        ];
        if (($state['status'] ?? '') === 'WAITING_RELAY') {
            $out['publicKey'] = (string) ($state['publicKey'] ?? '');
            $out['nonce'] = (string) ($state['nonce'] ?? '');
        }
        return $out;
    }
}

if (defined('P05_LEGACY_BRIDGE_LIBRARY_MODE') && P05_LEGACY_BRIDGE_LIBRARY_MODE === true) return;

header('Cache-Control: no-store, private, max-age=0');
header('Pragma: no-cache');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");

function p05_bridge_json(int $status, array $payload): never {
    http_response_code($status); header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR); exit;
}
function p05_bridge_origin_ok(): bool {
    $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
    if ($origin === '') return true;
    $forwarded = strtolower(trim(explode(',', (string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? ''))[0] ?? ''));
    $scheme = ($forwarded === 'https' || (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')) ? 'https' : 'http';
    $host = trim((string) ($_SERVER['HTTP_HOST'] ?? ''));
    return $host !== '' && hash_equals($scheme . '://' . $host, rtrim($origin, '/'));
}

try {
    $bridge = new P05LegacyUpdateBridge(__DIR__);
    $relay = (string) ($_GET['relay'] ?? '');
    if ($relay === 'info' && ($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'GET') p05_bridge_json(200, $bridge->relayInfo());
    if ($relay === 'deliver' && ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
        $body = json_decode((string) file_get_contents('php://input'), true, 16, JSON_THROW_ON_ERROR);
        p05_bridge_json(200, $bridge->deliver((string) ($body['nonce'] ?? ''), (string) ($body['sealed'] ?? '')));
    }
    if ($relay === 'cleanup' && ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
        $body = json_decode((string) file_get_contents('php://input'), true, 16, JSON_THROW_ON_ERROR);
        p05_bridge_json(200, $bridge->cleanup((string) ($body['nonce'] ?? ''), true));
    }

    $message = '';
    $error = '';
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
        if (!p05_bridge_origin_ok()) throw new RuntimeException('BRIDGE_ORIGIN_REJECTED');
        $password = is_string($_POST['password'] ?? null) ? (string) $_POST['password'] : '';
        if ($password === '') throw new RuntimeException('BRIDGE_ADMIN_PASSWORD_REQUIRED');
        $result = $bridge->initialize($password);
        $password = '';
        $message = ($result['status'] ?? '') === 'WAITING_RELAY' ? '管理员验证、Source Gate 与恢复点已完成。正在等待安全初始化。' : '更新服务已经初始化。';
    }
    $state = $bridge->relayInfo();
} catch (Throwable $e) {
    $state = ['status' => 'ERROR'];
    $error = preg_match('/^[A-Z0-9_:-]{3,160}$/', strtoupper($e->getMessage())) ? strtoupper($e->getMessage()) : 'BRIDGE_FAILED';
}
$statusText = (string) ($state['status'] ?? 'NOT_READY');
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VF SEO · 更新服务初始化</title><style>
body{margin:0;background:#eef5f6;color:#16373d;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}.wrap{max-width:680px;margin:7vh auto;padding:18px}.card{background:#fff;border:1px solid #cbdfe2;border-radius:18px;padding:26px;box-shadow:0 18px 60px rgba(14,42,49,.12)}.eyebrow{font-size:12px;font-weight:800;color:#078694;letter-spacing:.06em}h1{font-size:26px;margin:8px 0 8px}p{line-height:1.65;color:#607980}.box{margin-top:18px;padding:15px;border-radius:12px;background:#f4f9fa;border:1px solid #d8e8ea}.ok{background:#eaf8f5;border-color:#bde4dc;color:#17675e}.warn{background:#fff7e8;border-color:#ecd9ae}.err{background:#fff0ed;border-color:#efc8bf;color:#963b2d}label{display:block;font-weight:750;margin:18px 0 7px}input{box-sizing:border-box;width:100%;padding:12px;border:1px solid #bfd3d7;border-radius:10px;font:inherit}button{margin-top:12px;width:100%;padding:12px;border:0;border-radius:10px;background:#0b96a5;color:#fff;font:inherit;font-weight:800}.small{font-size:12px;color:#779096;margin-top:14px}</style></head><body><main class="wrap"><section class="card"><div class="eyebrow">P05 · VF SEO · ONE-TIME LEGACY BRIDGE</div><h1>初始化后台更新服务</h1><p>这不是产品升级。它只让当前 V1.2.2 后台接入统一更新通道；不会修改版本、Schema 或业务数据。</p>
<?php if ($error !== ''): ?><div class="box err">初始化未完成：<?=htmlspecialchars($error, ENT_QUOTES, 'UTF-8')?></div><?php endif; ?>
<?php if ($statusText === 'READY'): ?><div class="box ok"><strong>更新服务已初始化。</strong><br>请回到 VF SEO 后台「系统与更新」，点击「重新检查」。应显示 V1.2.3 可更新。</div>
<?php elseif ($statusText === 'WAITING_RELAY'): ?><div id="relay" class="box warn"><strong>准备完成，正在等待安全初始化…</strong><br>无需输入 GitHub Token。公共 Runner 会通过密封通道完成一次性服务器配置。</div><script>setInterval(async()=>{try{const r=await fetch('?relay=info',{cache:'no-store'}),j=await r.json();if(j.status==='READY'){document.getElementById('relay').className='box ok';document.getElementById('relay').innerHTML='<strong>更新服务已初始化。</strong><br>请回到后台「系统与更新」点击「重新检查」。';}}catch(e){}},1800);</script>
<?php else: ?><form method="post"><label for="password">当前 VF SEO 管理员密码</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="1024"><button type="submit">开始一次性初始化</button></form><?php endif; ?>
<p class="small">安全边界：Token 不在本页面显示、输入或保存到浏览器；正式升级仍由后台一键更新执行。</p></section></main></body></html>
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-root", required=True)
    ap.add_argument("--out", required=True)
    ns = ap.parse_args()
    root = locate_root(Path(ns.full_root).resolve())
    if (root / "VERSION").read_text(encoding="utf-8").strip() != SOURCE_VERSION:
        raise SystemExit("FULL VERSION mismatch")
    manifest = build_manifest(root)
    text = (TEMPLATE
            .replace("@@SOURCE_VERSION@@", SOURCE_VERSION)
            .replace("@@TARGET_VERSION@@", TARGET_VERSION)
            .replace("@@MANIFEST@@", php_manifest(manifest)))
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"BRIDGE_FILE={out}")
    print(f"BRIDGE_BYTES={out.stat().st_size}")
    print(f"BRIDGE_SHA256={digest}")
    print(f"SOURCE_FILES={len(manifest)}")


if __name__ == "__main__":
    main()
