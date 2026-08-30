#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import sys
import zipfile
from pathlib import Path

SOURCE_VERSION = "1.1.10"
TARGET_VERSION = "1.1.11"
SCHEMA_IDENTITY = "VF-SEO-SCHEMA@1"
SCHEMA_VERSION = 1

FORBIDDEN_NAMES = {
    "VF_INSTALL_INSTANCE.json",
    ".vf-seo-site-instance.json",
    ".env",
    "runtime.env",
    "setup.lock.json",
}
FORBIDDEN_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".db-wal", ".db-shm")


def die(message: str):
    raise SystemExit(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        die(f"release root missing: {root}")
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            die(f"symlink forbidden in formal release: {path}")
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        name = path.name
        lower = name.lower()
        if name in FORBIDDEN_NAMES or lower.endswith(FORBIDDEN_SUFFIXES):
            die(f"runtime/private file forbidden in formal release: {rel}")
        files[rel] = path.read_bytes()
    if not files:
        die("formal release is empty")
    return files


def b64json(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def deterministic_zip(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, files[name])


def build_repair(source: dict[str, bytes], target: dict[str, bytes]) -> str:
    source_manifest = {k: sha256_bytes(v) for k, v in sorted(source.items())}
    target_manifest = {k: sha256_bytes(v) for k, v in sorted(target.items())}
    payload = {k: base64.b64encode(v).decode("ascii") for k, v in sorted(target.items())}
    removed = sorted(set(source) - set(target))

    template = r'''<?php
declare(strict_types=1);

final class P05AtomicPackage
{
    public const SOURCE_VERSION = '1.1.10';
    public const TARGET_VERSION = '1.1.11';
    public const SCHEMA_IDENTITY = 'VF-SEO-SCHEMA@1';
    public const SCHEMA_VERSION = 1;

    private const SOURCE_MANIFEST = '@@SOURCE_MANIFEST@@';
    private const TARGET_MANIFEST = '@@TARGET_MANIFEST@@';
    private const PAYLOAD = '@@PAYLOAD@@';
    private const REMOVED = '@@REMOVED@@';

    private static function decode(string $encoded): array
    {
        $raw = base64_decode($encoded, true);
        if ($raw === false) throw new RuntimeException('ATOMIC_METADATA_DECODE_FAILED');
        $value = json_decode($raw, true);
        if (!is_array($value)) throw new RuntimeException('ATOMIC_METADATA_JSON_INVALID');
        return $value;
    }

    private static function rel(string $rel): string
    {
        if ($rel === '' || $rel[0] === '/' || str_contains($rel, '\\') || preg_match('#(^|/)\.\.(/|$)#', $rel) === 1) {
            throw new RuntimeException('ATOMIC_PATH_UNSAFE');
        }
        return $rel;
    }

    private static function writeExact(string $path, string $bytes, int $mode = 0640): void
    {
        $dir = dirname($path);
        if (!is_dir($dir) && !@mkdir($dir, 0750, true) && !is_dir($dir)) throw new RuntimeException('ATOMIC_DIRECTORY_CREATE_FAILED');
        $tmp = $path . '.atomic-tmp-' . bin2hex(random_bytes(5));
        $handle = @fopen($tmp, 'xb');
        if ($handle === false) throw new RuntimeException('ATOMIC_TEMP_CREATE_FAILED');
        try {
            $offset = 0;
            $length = strlen($bytes);
            while ($offset < $length) {
                $written = @fwrite($handle, substr($bytes, $offset));
                if ($written === false || $written === 0) throw new RuntimeException('ATOMIC_SHORT_WRITE');
                $offset += $written;
            }
            if (!@fflush($handle)) throw new RuntimeException('ATOMIC_FLUSH_FAILED');
            if (function_exists('fsync')) @fsync($handle);
        } finally {
            @fclose($handle);
        }
        @chmod($tmp, $mode);
        if (!@rename($tmp, $path)) {
            @unlink($tmp);
            throw new RuntimeException('ATOMIC_RENAME_FAILED');
        }
        @chmod($path, $mode);
    }

    private static function jsonWrite(string $path, array $data, int $mode = 0600): void
    {
        $json = json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . "\n";
        self::writeExact($path, $json, $mode);
    }

    private static function removeTree(string $path): void
    {
        if (!file_exists($path)) return;
        if (is_file($path) || is_link($path)) {
            @unlink($path);
            return;
        }
        foreach (scandir($path) ?: [] as $name) {
            if ($name === '.' || $name === '..') continue;
            self::removeTree($path . '/' . $name);
        }
        @rmdir($path);
    }

    private static function verifyManifest(string $root, array $manifest): array
    {
        $errors = [];
        foreach ($manifest as $rel => $expected) {
            $rel = self::rel((string) $rel);
            $path = rtrim($root, '/') . '/' . $rel;
            if (!is_file($path) || is_link($path)) {
                $errors[] = $rel . ':missing';
                continue;
            }
            $actual = hash_file('sha256', $path);
            if (!is_string($actual) || !hash_equals((string) $expected, $actual)) $errors[] = $rel . ':sha256';
        }
        return ['ok' => $errors === [], 'errors' => $errors, 'checked' => count($manifest)];
    }

    private static function readEnvValue(string $path, string $name): ?string
    {
        if (!is_file($path) || !is_readable($path)) return null;
        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if ($lines === false) return null;
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) continue;
            [$key, $value] = explode('=', $line, 2);
            if (trim($key) !== $name) continue;
            $value = trim($value);
            if (strlen($value) >= 2 && (($value[0] === '"' && $value[-1] === '"') || ($value[0] === "'" && $value[-1] === "'"))) $value = substr($value, 1, -1);
            return $value;
        }
        return null;
    }

    private static function usableHome(string $path): bool
    {
        $path = trim($path);
        return $path !== '' && $path !== '/' && str_starts_with($path, '/');
    }

    private static function legacyHome(string $root): string
    {
        $home = getenv('HOME');
        if ($home !== false && self::usableHome($home)) return rtrim(trim($home), '/');
        if (function_exists('posix_geteuid') && function_exists('posix_getpwuid')) {
            try {
                $entry = posix_getpwuid(posix_geteuid());
                $dir = is_array($entry) ? ($entry['dir'] ?? null) : null;
                if (is_string($dir) && self::usableHome($dir)) return rtrim(trim($dir), '/');
            } catch (Throwable) {
            }
        }
        $parent = rtrim(dirname($root), '/');
        $site = basename(rtrim($root, '/'));
        $safe = preg_replace('/[^A-Za-z0-9._-]+/', '-', $site) ?: substr(hash('sha256', $root), 0, 16);
        return $parent . '/.vf-seo-private/' . $safe;
    }

    private static function absolutePath(string $path, string $root): string
    {
        $path = trim($path);
        if ($path === '') throw new RuntimeException('ATOMIC_RUNTIME_PATH_EMPTY');
        if (str_starts_with($path, '/')) return $path;
        return rtrim($root, '/') . '/' . ltrim($path, '/');
    }

    private static function pointerRuntime(string $root): array
    {
        $pointerPath = rtrim($root, '/') . '/VF_INSTALL_INSTANCE.json';
        if (!is_file($pointerPath) || is_link($pointerPath) || !is_readable($pointerPath)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_MISSING');
        $raw = file_get_contents($pointerPath);
        if (!is_string($raw)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_READ_FAILED');
        $pointer = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
        if (!is_array($pointer)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_INVALID');

        $id = strtolower(trim((string) ($pointer['siteInstanceId'] ?? '')));
        if (preg_match('/^[0-9a-f]{32}$/', $id) !== 1) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_ID_INVALID');

        $format = (int) ($pointer['format'] ?? 0);
        if ($format === 3) {
            $slug = trim((string) ($pointer['storageSlug'] ?? ''));
            if (($pointer['installed'] ?? false) !== true || !hash_equals('.vfseo-data-' . $id, $slug)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_INVALID');
            $storageRoot = rtrim(dirname($root), '/') . '/' . $slug;
            return [
                'format' => 3,
                'site_instance_id' => $id,
                'pointer_path' => $pointerPath,
                'pointer_sha256' => hash('sha256', $raw),
                'storage_root' => $storageRoot,
                'updates_dir' => $storageRoot . '/updates',
                'runtime_env' => $storageRoot . '/config/runtime.env',
                'sqlite' => $storageRoot . '/data/vf-seo.sqlite3',
                'setup_lock' => $storageRoot . '/config/setup.lock.json',
            ];
        }

        if ($format === 2 && trim((string) ($pointer['storageScope'] ?? '')) === 'instance-v1') {
            $home = self::legacyHome($root);
            $configDir = $home . '/.config/vf-seo/instances/' . $id;
            $dataDir = $home . '/.local/share/vf-seo/instances/' . $id;
            $runtimeEnv = $configDir . '/runtime.env';
            $sqlite = $dataDir . '/vf-seo.sqlite3';
            $legacySqlite = self::readEnvValue($runtimeEnv, 'VF_SQLITE_PATH');
            if ($legacySqlite !== null && trim($legacySqlite) !== '') $sqlite = self::absolutePath($legacySqlite, $root);
            $storageRoot = dirname($sqlite);
            return [
                'format' => 2,
                'site_instance_id' => $id,
                'pointer_path' => $pointerPath,
                'pointer_sha256' => hash('sha256', $raw),
                'storage_root' => $storageRoot,
                'updates_dir' => $storageRoot . '/updates',
                'runtime_env' => $runtimeEnv,
                'sqlite' => $sqlite,
                'setup_lock' => $configDir . '/setup.lock.json',
            ];
        }

        throw new RuntimeException('ATOMIC_RUNTIME_POINTER_FORMAT_UNSUPPORTED');
    }

    private static function dbVerify(string $dbPath): array
    {
        if (!extension_loaded('pdo_sqlite')) throw new RuntimeException('PDO_SQLITE_EXTENSION_REQUIRED');
        if (!is_file($dbPath) || is_link($dbPath)) throw new RuntimeException('ATOMIC_DATABASE_MISSING');

        $pdo = new PDO('sqlite:' . $dbPath, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
        $pdo->exec('PRAGMA foreign_keys=ON');
        $pdo->exec('PRAGMA busy_timeout=5000');
        $integrity = strtolower((string) $pdo->query('PRAGMA integrity_check')->fetchColumn());
        $fk = $pdo->query('PRAGMA foreign_key_check')->fetchAll();
        $schema = $pdo->query('SELECT schema_identity,schema_version FROM schema_metadata WHERE singleton=1')->fetch();
        $adminCount = (int) $pdo->query('SELECT count(*) FROM admins WHERE disabled_at IS NULL')->fetchColumn();
        $install = $pdo->query('SELECT installed,first_admin_ready FROM system_install_state WHERE singleton=1')->fetch();

        if ($integrity !== 'ok' || $fk !== [] || !is_array($schema) || ($schema['schema_identity'] ?? null) !== self::SCHEMA_IDENTITY || (int) ($schema['schema_version'] ?? 0) !== self::SCHEMA_VERSION || $adminCount < 1 || !is_array($install) || (int) ($install['installed'] ?? 0) !== 1 || (int) ($install['first_admin_ready'] ?? 0) !== 1) {
            throw new RuntimeException('ATOMIC_DATABASE_VERIFY_FAILED');
        }

        return [
            'integrity' => $integrity,
            'foreign_key_errors' => count($fk),
            'schema_identity' => self::SCHEMA_IDENTITY,
            'schema_version' => self::SCHEMA_VERSION,
            'admin_count' => $adminCount,
        ];
    }

    private static function snapshotDb(string $dbPath, string $dest): void
    {
        if (file_exists($dest)) @unlink($dest);
        $pdo = new PDO('sqlite:' . $dbPath, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
        $pdo->exec('PRAGMA busy_timeout=5000');
        $pdo->exec('PRAGMA wal_checkpoint(FULL)');
        $quoted = str_replace("'", "''", $dest);
        $pdo->exec("VACUUM INTO '$quoted'");
        @chmod($dest, 0600);
    }

    private static function restoreDb(string $snapshot, string $dbPath): void
    {
        if (!is_file($snapshot)) throw new RuntimeException('ATOMIC_DATABASE_SNAPSHOT_MISSING');
        @unlink($dbPath . '-wal');
        @unlink($dbPath . '-shm');
        self::writeExact($dbPath, (string) file_get_contents($snapshot), 0600);
    }

    private static function backupFiles(string $root, string $stage, array $paths): array
    {
        $meta = [];
        foreach ($paths as $rel) {
            $rel = self::rel((string) $rel);
            $src = rtrim($root, '/') . '/' . $rel;
            $exists = is_file($src) && !is_link($src);
            $meta[$rel] = $exists;
            if ($exists) self::writeExact($stage . '/source/' . $rel, (string) file_get_contents($src), 0600);
        }
        return $meta;
    }

    private static function restoreFiles(string $root, string $stage, array $meta): void
    {
        foreach ($meta as $rel => $existed) {
            $rel = self::rel((string) $rel);
            $dest = rtrim($root, '/') . '/' . $rel;
            $saved = $stage . '/source/' . $rel;
            if ($existed) {
                if (!is_file($saved)) throw new RuntimeException('ATOMIC_SOURCE_SNAPSHOT_MISSING');
                self::writeExact($dest, (string) file_get_contents($saved), 0640);
            } else {
                if (is_file($dest) || is_link($dest)) @unlink($dest);
            }
        }
    }

    private static function privateSnapshots(string $stage, array $runtime): void
    {
        foreach (['runtime.env' => (string) $runtime['runtime_env'], 'setup.lock.json' => (string) $runtime['setup_lock']] as $name => $path) {
            if (!is_file($path) || is_link($path) || !is_readable($path)) throw new RuntimeException('ATOMIC_PRIVATE_RUNTIME_FILE_MISSING');
            self::writeExact($stage . '/private/' . $name, (string) file_get_contents($path), 0600);
        }
        self::snapshotDb((string) $runtime['sqlite'], $stage . '/private/database.sqlite3');
    }

    private static function restorePrivate(string $stage, array $runtime): void
    {
        self::restoreDb($stage . '/private/database.sqlite3', (string) $runtime['sqlite']);
        foreach (['runtime.env' => (string) $runtime['runtime_env'], 'setup.lock.json' => (string) $runtime['setup_lock']] as $name => $path) {
            $saved = $stage . '/private/' . $name;
            if (!is_file($saved)) throw new RuntimeException('ATOMIC_PRIVATE_SNAPSHOT_MISSING');
            self::writeExact($path, (string) file_get_contents($saved), 0600);
        }
    }

    private static function journalPath(array $runtime): string
    {
        return rtrim((string) $runtime['updates_dir'], '/') . '/p05-atomic-transaction.json';
    }

    private static function lockPath(array $runtime): string
    {
        return rtrim((string) $runtime['updates_dir'], '/') . '/p05-atomic.lock';
    }

    private static function ensureUpdatesDir(array $runtime): void
    {
        $dir = (string) $runtime['updates_dir'];
        if (!is_dir($dir) && !@mkdir($dir, 0700, true) && !is_dir($dir)) throw new RuntimeException('ATOMIC_UPDATES_DIRECTORY_CREATE_FAILED');
        @chmod($dir, 0700);
    }

    private static function acquireLock(array $runtime)
    {
        self::ensureUpdatesDir($runtime);
        $handle = @fopen(self::lockPath($runtime), 'c+');
        if ($handle === false) throw new RuntimeException('ATOMIC_LOCK_CREATE_FAILED');
        if (!@flock($handle, LOCK_EX | LOCK_NB)) {
            fclose($handle);
            throw new RuntimeException('ATOMIC_UPDATE_IN_PROGRESS');
        }
        @chmod(self::lockPath($runtime), 0600);
        return $handle;
    }

    private static function releaseLock($handle, array $runtime): void
    {
        if (is_resource($handle)) {
            @flock($handle, LOCK_UN);
            @fclose($handle);
        }
        @unlink(self::lockPath($runtime));
    }

    private static function recoverInterrupted(string $root, array $runtime): bool
    {
        $journal = self::journalPath($runtime);
        if (!is_file($journal)) return false;
        if (is_link($journal)) throw new RuntimeException('ATOMIC_JOURNAL_SYMLINK_FORBIDDEN');
        $record = json_decode((string) file_get_contents($journal), true);
        if (!is_array($record) || ($record['target_version'] ?? null) !== self::TARGET_VERSION || ($record['source_version'] ?? null) !== self::SOURCE_VERSION) throw new RuntimeException('ATOMIC_JOURNAL_INVALID');

        $updates = rtrim((string) $runtime['updates_dir'], '/');
        $stage = (string) ($record['stage'] ?? '');
        if ($stage === '' || !str_starts_with($stage, $updates . '/.atomic-' . self::TARGET_VERSION . '-') || !is_dir($stage)) throw new RuntimeException('ATOMIC_RECOVERY_STAGE_INVALID');

        $meta = json_decode((string) @file_get_contents($stage . '/source-meta.json'), true);
        if (!is_array($meta)) throw new RuntimeException('ATOMIC_RECOVERY_META_MISSING');
        self::restoreFiles($root, $stage, $meta);
        self::restorePrivate($stage, $runtime);
        $source = self::verifySource($root);
        if (!$source['ok']) throw new RuntimeException('ATOMIC_INTERRUPTED_SOURCE_VERIFY_FAILED');
        self::dbVerify((string) $runtime['sqlite']);
        $pointerSha = hash_file('sha256', (string) $runtime['pointer_path']);
        if (!is_string($pointerSha) || !hash_equals((string) $runtime['pointer_sha256'], $pointerSha)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_CHANGED_DURING_RECOVERY');
        @unlink($journal);
        self::removeTree($stage);
        return true;
    }

    private static function applyPayload(string $root): void
    {
        foreach (self::decode(self::PAYLOAD) as $rel => $encoded) {
            $bytes = base64_decode((string) $encoded, true);
            if ($bytes === false) throw new RuntimeException('ATOMIC_PAYLOAD_DECODE_FAILED');
            self::writeExact(rtrim($root, '/') . '/' . self::rel((string) $rel), $bytes, 0640);
        }
        foreach (self::decode(self::REMOVED) as $rel) {
            $path = rtrim($root, '/') . '/' . self::rel((string) $rel);
            if (is_file($path) || is_link($path)) @unlink($path);
        }
    }

    private static function updateSetupLock(array $runtime): void
    {
        $path = (string) $runtime['setup_lock'];
        $value = json_decode((string) file_get_contents($path), true);
        if (!is_array($value)) throw new RuntimeException('ATOMIC_SETUP_LOCK_INVALID');
        $value['version'] = self::TARGET_VERSION;
        $value['upgradedAt'] = gmdate('Y-m-d\\TH:i:s\\Z');
        self::jsonWrite($path, $value, 0600);
    }

    private static function resetOpcacheIfNeeded(): bool
    {
        if (!function_exists('opcache_get_status')) return false;
        $status = @opcache_get_status(false);
        if (!is_array($status) || !($status['opcache_enabled'] ?? false)) return false;
        if (!function_exists('opcache_reset') || @opcache_reset() !== true) throw new RuntimeException('ATOMIC_OPCACHE_RESET_FAILED');
        return true;
    }

    public static function selfTest(): array
    {
        if (PHP_VERSION_ID < 80200) throw new RuntimeException('PHP_8_2_REQUIRED');
        $source = self::decode(self::SOURCE_MANIFEST);
        $target = self::decode(self::TARGET_MANIFEST);
        $payload = self::decode(self::PAYLOAD);
        $removed = self::decode(self::REMOVED);
        if ($source === [] || $target === [] || $payload === []) throw new RuntimeException('ATOMIC_METADATA_EMPTY');
        foreach ($target as $rel => $expected) {
            if (!isset($payload[$rel])) throw new RuntimeException('ATOMIC_PAYLOAD_FILE_MISSING');
            $bytes = base64_decode((string) $payload[$rel], true);
            if ($bytes === false || !hash_equals((string) $expected, hash('sha256', $bytes))) throw new RuntimeException('ATOMIC_PAYLOAD_HASH_MISMATCH');
            self::rel((string) $rel);
        }
        foreach ($removed as $rel) self::rel((string) $rel);
        return [
            'ok' => true,
            'project_id' => 'P05',
            'source_version' => self::SOURCE_VERSION,
            'target_version' => self::TARGET_VERSION,
            'schema_identity' => self::SCHEMA_IDENTITY,
            'schema_version' => self::SCHEMA_VERSION,
            'source_files' => count($source),
            'target_files' => count($target),
            'payload_files' => count($payload),
            'removed_files' => count($removed),
            'recovery_point' => true,
            'rollback' => true,
            'interruption_recovery' => true,
            'idempotence' => true,
            'runtime_pointer_preserved' => true,
            'browser_single_php' => true,
            'remote_download_required' => false,
        ];
    }

    public static function verifySource(string $root): array
    {
        return self::verifyManifest(rtrim(realpath($root) ?: $root, '/'), self::decode(self::SOURCE_MANIFEST));
    }

    public static function verifyTarget(string $root): array
    {
        return self::verifyManifest(rtrim(realpath($root) ?: $root, '/'), self::decode(self::TARGET_MANIFEST));
    }

    public static function run(string $root): array
    {
        self::selfTest();
        $root = rtrim(realpath($root) ?: $root, '/');
        $runtime = self::pointerRuntime($root);
        $lock = self::acquireLock($runtime);
        $stage = '';
        $sourceMeta = [];
        $prepared = false;
        $recovered = false;

        try {
            $recovered = self::recoverInterrupted($root, $runtime);
            clearstatcache(true);
            $version = trim((string) @file_get_contents($root . '/VERSION'));

            if ($version === self::TARGET_VERSION) {
                $target = self::verifyTarget($root);
                if (!$target['ok']) throw new RuntimeException('ATOMIC_TARGET_FILES_INCONSISTENT');
                $db = self::dbVerify((string) $runtime['sqlite']);
                $pointerSha = hash_file('sha256', (string) $runtime['pointer_path']);
                if (!is_string($pointerSha) || !hash_equals((string) $runtime['pointer_sha256'], $pointerSha)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_CHANGED');
                self::resetOpcacheIfNeeded();
                return [
                    'ok' => true,
                    'already_current' => true,
                    'interrupted_recovered' => $recovered,
                    'pointer_preserved' => true,
                    'rollback_supported' => true,
                    'schema_identity' => $db['schema_identity'],
                    'schema_version' => $db['schema_version'],
                    'integrity' => $db['integrity'],
                ];
            }

            if ($version !== self::SOURCE_VERSION) throw new RuntimeException('ATOMIC_UNSUPPORTED_SOURCE_VERSION:' . $version);
            $source = self::verifySource($root);
            if (!$source['ok']) throw new RuntimeException('ATOMIC_SOURCE_VERIFY_FAILED:' . implode(',', $source['errors']));
            self::dbVerify((string) $runtime['sqlite']);

            self::ensureUpdatesDir($runtime);
            $stage = rtrim((string) $runtime['updates_dir'], '/') . '/.atomic-' . self::TARGET_VERSION . '-' . bin2hex(random_bytes(5));
            if (!@mkdir($stage, 0700, true) && !is_dir($stage)) throw new RuntimeException('ATOMIC_STAGE_CREATE_FAILED');
            @chmod($stage, 0700);

            $payload = self::decode(self::PAYLOAD);
            $removed = self::decode(self::REMOVED);
            $paths = array_values(array_unique(array_merge(array_keys($payload), $removed)));
            self::privateSnapshots($stage, $runtime);
            $sourceMeta = self::backupFiles($root, $stage, $paths);
            self::jsonWrite($stage . '/source-meta.json', $sourceMeta);

            $journal = self::journalPath($runtime);
            self::jsonWrite($journal, [
                'project_id' => 'P05',
                'source_version' => self::SOURCE_VERSION,
                'target_version' => self::TARGET_VERSION,
                'stage' => $stage,
                'phase' => 'prepared',
                'created_at' => gmdate('c'),
            ]);
            $prepared = true;

            self::applyPayload($root);
            self::jsonWrite($journal, [
                'project_id' => 'P05',
                'source_version' => self::SOURCE_VERSION,
                'target_version' => self::TARGET_VERSION,
                'stage' => $stage,
                'phase' => 'source_applied',
                'created_at' => gmdate('c'),
            ]);

            if (getenv('VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY') === '1') {
                fwrite(STDERR, "Injected hard interruption after source apply.\n");
                exit(97);
            }
            if (getenv('VF_ATOMIC_TEST_FAIL_AFTER_APPLY') === '1') throw new RuntimeException('INJECTED_FAILURE_AFTER_APPLY');

            self::updateSetupLock($runtime);
            $target = self::verifyTarget($root);
            if (!$target['ok']) throw new RuntimeException('ATOMIC_TARGET_VERIFY_FAILED:' . implode(',', $target['errors']));
            $db = self::dbVerify((string) $runtime['sqlite']);

            $pointerSha = hash_file('sha256', (string) $runtime['pointer_path']);
            if (!is_string($pointerSha) || !hash_equals((string) $runtime['pointer_sha256'], $pointerSha)) throw new RuntimeException('ATOMIC_RUNTIME_POINTER_CHANGED');

            $opcacheReset = self::resetOpcacheIfNeeded();
            self::jsonWrite($journal, [
                'project_id' => 'P05',
                'source_version' => self::SOURCE_VERSION,
                'target_version' => self::TARGET_VERSION,
                'stage' => $stage,
                'phase' => 'commit_ready',
                'created_at' => gmdate('c'),
            ]);
            @unlink($journal);
            self::removeTree($stage);
            $stage = '';
            $prepared = false;

            return [
                'ok' => true,
                'already_current' => false,
                'interrupted_recovered' => $recovered,
                'pointer_preserved' => true,
                'rollback_supported' => true,
                'source_checked' => $source['checked'],
                'target_checked' => $target['checked'],
                'schema_identity' => $db['schema_identity'],
                'schema_version' => $db['schema_version'],
                'integrity' => $db['integrity'],
                'opcache_reset' => $opcacheReset,
            ];
        } catch (Throwable $error) {
            if ($stage !== '' && is_dir($stage) && $prepared) {
                try {
                    $meta = $sourceMeta;
                    if ($meta === [] && is_file($stage . '/source-meta.json')) {
                        $decoded = json_decode((string) file_get_contents($stage . '/source-meta.json'), true);
                        if (is_array($decoded)) $meta = $decoded;
                    }
                    self::restoreFiles($root, $stage, $meta);
                    self::restorePrivate($stage, $runtime);
                    $source = self::verifySource($root);
                    if (!$source['ok']) throw new RuntimeException('ATOMIC_ROLLBACK_SOURCE_VERIFY_FAILED');
                    self::dbVerify((string) $runtime['sqlite']);
                    $pointerSha = hash_file('sha256', (string) $runtime['pointer_path']);
                    if (!is_string($pointerSha) || !hash_equals((string) $runtime['pointer_sha256'], $pointerSha)) throw new RuntimeException('ATOMIC_ROLLBACK_POINTER_VERIFY_FAILED');
                    @unlink(self::journalPath($runtime));
                    self::removeTree($stage);
                } catch (Throwable $rollbackError) {
                    throw new RuntimeException('ATOMIC_FAILED_AND_ROLLBACK_VERIFY_FAILED', 0, $error);
                }
            }
            throw new RuntimeException('ATOMIC_FAILED_SOURCE_RESTORED:' . $error->getMessage(), 0, $error);
        } finally {
            self::releaseLock($lock, $runtime);
        }
    }

    private static function webSecurityHeaders(): void
    {
        header('Content-Type: text/html; charset=utf-8');
        header('Cache-Control: no-store, max-age=0');
        header('Pragma: no-cache');
        header('X-Robots-Tag: noindex,nofollow,noarchive');
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: no-referrer');
        header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
    }

    private static function isHttps(): bool
    {
        $https = strtolower((string) ($_SERVER['HTTPS'] ?? ''));
        if ($https !== '' && $https !== 'off' && $https !== '0') return true;
        $forwarded = strtolower(trim(explode(',', (string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? ''))[0] ?? ''));
        return $forwarded === 'https';
    }

    private static function originAllowed(): bool
    {
        if (strtolower((string) ($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '')) === 'cross-site') return false;
        $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
        if ($origin === '') return true;
        $parts = parse_url($origin);
        if (!is_array($parts) || !isset($parts['scheme'], $parts['host'])) return false;
        $host = strtolower((string) ($_SERVER['HTTP_HOST'] ?? ''));
        $originHost = strtolower((string) $parts['host']) . (isset($parts['port']) ? ':' . (int) $parts['port'] : '');
        return strtolower((string) $parts['scheme']) === (self::isHttps() ? 'https' : 'http') && $originHost === $host;
    }

    private static function startWebSession(): void
    {
        if (session_status() === PHP_SESSION_ACTIVE) return;
        session_name('vf_p05_atomic_upgrade');
        session_set_cookie_params([
            'lifetime' => 1800,
            'path' => '/',
            'secure' => self::isHttps(),
            'httponly' => true,
            'samesite' => 'Strict',
        ]);
        if (!@session_start()) throw new RuntimeException('ATOMIC_SESSION_START_FAILED');
        if (!isset($_SESSION['csrf']) || !is_string($_SESSION['csrf'])) {
            session_regenerate_id(true);
            $_SESSION['csrf'] = bin2hex(random_bytes(24));
        }
    }

    private static function adminPasswordValid(string $root, string $password): bool
    {
        if ($password === '' || strlen($password) > 1024) return false;
        $runtime = self::pointerRuntime($root);
        $pdo = new PDO('sqlite:' . $runtime['sqlite'], null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
        $admin = $pdo->query('SELECT password_hash FROM admins WHERE disabled_at IS NULL ORDER BY created_at,id LIMIT 1')->fetch();
        if (!is_array($admin) || !is_string($admin['password_hash'] ?? null)) return false;
        require_once rtrim($root, '/') . '/php/src/Security.php';
        return \VfSeo\PhpRuntime\Security::verifyPassword($password, (string) $admin['password_hash']);
    }

    public static function web(string $root): void
    {
        self::webSecurityHeaders();
        self::startWebSession();
        $method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
        if (!in_array($method, ['GET', 'HEAD', 'POST'], true)) {
            http_response_code(405);
            header('Allow: GET, HEAD, POST');
            echo '<!doctype html><meta charset="utf-8"><title>VF SEO 升级</title><p>不支持当前请求方式。</p>';
            return;
        }

        $result = null;
        $error = '';
        if ($method === 'POST') {
            try {
                if (!self::originAllowed()) throw new RuntimeException('请求来源校验失败。');
                $csrf = (string) ($_POST['csrf'] ?? '');
                $expected = (string) ($_SESSION['csrf'] ?? '');
                if ($csrf === '' || $expected === '' || !hash_equals($expected, $csrf)) throw new RuntimeException('请求已过期，请刷新页面后重试。');
                $password = is_string($_POST['password'] ?? null) ? (string) $_POST['password'] : '';
                if (!self::adminPasswordValid($root, $password)) throw new RuntimeException('管理员密码不正确');
                $result = self::run($root);
                $_SESSION['csrf'] = bin2hex(random_bytes(24));
            } catch (Throwable $failure) {
                $error = $failure->getMessage();
                http_response_code(422);
            }
        }

        $csrf = htmlspecialchars((string) ($_SESSION['csrf'] ?? ''), ENT_QUOTES, 'UTF-8');
        $source = htmlspecialchars(self::SOURCE_VERSION, ENT_QUOTES, 'UTF-8');
        $target = htmlspecialchars(self::TARGET_VERSION, ENT_QUOTES, 'UTF-8');
        echo '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VF SEO 原子升级</title>';
        echo '<style>body{font-family:system-ui,-apple-system,sans-serif;background:#f7faf9;color:#173330;margin:0}main{max-width:680px;margin:8vh auto;padding:28px;background:#fff;border:1px solid #d9e7e4;border-radius:16px}h1{font-size:24px}p{line-height:1.7}.ok{padding:14px;background:#eefaf7;border-radius:10px}.err{padding:14px;background:#fff3f1;border-radius:10px}input{width:100%;box-sizing:border-box;padding:12px;margin:8px 0 16px;border:1px solid #b9ceca;border-radius:8px}button{padding:12px 18px;border:0;border-radius:8px;background:#147d70;color:white;font-weight:700;cursor:pointer}small{color:#607874}</style></head><body><main><h1>VF SEO 原子升级</h1>';

        if (is_array($result)) {
            echo '<div class="ok"><strong>升级完成</strong><p>已从 V' . $source . ' 升级到 V' . $target . '。运行指针、SQLite 与业务数据已保留。</p></div><p><a href="./">打开 VF SEO</a></p>';
        } else {
            if ($error !== '') echo '<div class="err">' . htmlspecialchars($error, ENT_QUOTES, 'UTF-8') . '</div>';
            echo '<p>将从 V' . $source . ' 升级到 V' . $target . '。执行前会建立恢复点；失败会自动回滚。</p>';
            echo '<form method="post"><input type="hidden" name="csrf" value="' . $csrf . '"><label>当前管理员密码<input type="password" name="password" required autocomplete="current-password"></label><button type="submit">执行原子升级</button></form>';
            echo '<p><small>此文件自带已校验的目标版本，不会在升级时下载远程代码。</small></p>';
        }
        echo '</main></body></html>';
    }
}

if (defined('P05_ATOMIC_LIBRARY_MODE') && P05_ATOMIC_LIBRARY_MODE) return;

if (PHP_SAPI === 'cli') {
    try {
        if (in_array('--self-test', $argv, true)) {
            echo json_encode(P05AtomicPackage::selfTest(), JSON_UNESCAPED_SLASHES) . "\n";
            exit(0);
        }
        foreach ($argv as $argument) {
            if (str_starts_with($argument, '--verify-source=')) {
                $result = P05AtomicPackage::verifySource(substr($argument, 16));
                echo json_encode($result, JSON_UNESCAPED_SLASHES) . "\n";
                exit($result['ok'] ? 0 : 1);
            }
            if (str_starts_with($argument, '--verify-target=')) {
                $result = P05AtomicPackage::verifyTarget(substr($argument, 16));
                echo json_encode($result, JSON_UNESCAPED_SLASHES) . "\n";
                exit($result['ok'] ? 0 : 1);
            }
            if (str_starts_with($argument, '--run=')) {
                $result = P05AtomicPackage::run(substr($argument, 6));
                echo json_encode($result, JSON_UNESCAPED_SLASHES) . "\n";
                exit(0);
            }
        }
        fwrite(STDERR, "Use --self-test, --verify-source=PATH, --verify-target=PATH or --run=PATH\n");
        exit(2);
    } catch (Throwable $error) {
        fwrite(STDERR, $error->getMessage() . "\n");
        exit(1);
    }
}

P05AtomicPackage::web(__DIR__);
'''

    return (
        template.replace("@@SOURCE_MANIFEST@@", b64json(source_manifest))
        .replace("@@TARGET_MANIFEST@@", b64json(target_manifest))
        .replace("@@PAYLOAD@@", b64json(payload))
        .replace("@@REMOVED@@", b64json(removed))
    )


def main() -> None:
    if len(sys.argv) != 4:
        die("usage: builder.py SOURCE_ROOT TARGET_ROOT OUT_DIR")
    source_root = Path(sys.argv[1]).resolve()
    target_root = Path(sys.argv[2]).resolve()
    out = Path(sys.argv[3]).resolve()
    source = collect(source_root)
    target = collect(target_root)

    if source.get("VERSION", b"").strip() != SOURCE_VERSION.encode():
        die("source VERSION mismatch")
    if target.get("VERSION", b"").strip() != TARGET_VERSION.encode():
        die("target VERSION mismatch")

    out.mkdir(parents=True, exist_ok=True)
    repair = build_repair(source, target)
    repair_path = out / f"repair-v{TARGET_VERSION}.php"
    repair_path.write_text(repair, encoding="utf-8", newline="\n")

    update_path = out / f"VF_SEO_V{TARGET_VERSION}_UPDATE.zip"
    deterministic_zip(update_path, {repair_path.name: repair_path.read_bytes()})

    source_manifest = {k: sha256_bytes(v) for k, v in sorted(source.items())}
    target_manifest = {k: sha256_bytes(v) for k, v in sorted(target.items())}
    changed = sorted(
        k for k in set(source) | set(target)
        if k not in source or k not in target or source_manifest.get(k) != target_manifest.get(k)
    )
    added = sorted(set(target) - set(source))
    removed = sorted(set(source) - set(target))

    metadata = {
        "project_id": "P05",
        "product": "VF SEO",
        "source_version": SOURCE_VERSION,
        "target_version": TARGET_VERSION,
        "schema_identity": SCHEMA_IDENTITY,
        "schema_version": SCHEMA_VERSION,
        "schema_change": False,
        "source_file_count": len(source),
        "target_file_count": len(target),
        "runtime_delta_count": len(changed),
        "runtime_added": added,
        "runtime_removed": removed,
        "runtime_delta": changed,
        "repair_name": repair_path.name,
        "repair_sha256": sha256_bytes(repair_path.read_bytes()),
        "update_name": update_path.name,
        "update_sha256": sha256_bytes(update_path.read_bytes()),
        "update_inner": [repair_path.name],
        "atomic_update": True,
        "recovery_point": True,
        "data_preservation": True,
        "idempotence": True,
        "rollback": True,
        "interruption_recovery": True,
        "runtime_pointer_preserved": True,
        "browser_single_php": True,
        "remote_download_required": False,
        "production_write": 0,
        "status": "ATOMIC_ARTIFACT_BUILT_UNVERIFIED",
    }
    (out / "P05-V1.1.11-ATOMIC-METADATA.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
