#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
from pathlib import Path

VERSION = "2.47.11"
SOURCE_VERSION = "2.47.10"
SCHEMA = "2026090401"
PROJECT_ID = "P01"
COMPONENT_ID = "APP"
REPOSITORY = "llhzx2018/vf-start"
BRIDGE_NAME = "P01_V24710_AUTH_BRIDGE.php"
FULL_NAME = f"VF-Start-V{VERSION}-FULL.zip"
UPDATE_NAME = f"VF_Start_V{VERSION}_UPDATE.zip"
REPAIR_NAME = f"repair-v{VERSION}.php"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def b64json(value) -> str:
    return base64.b64encode(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).decode()


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("p01_release_base", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_const(php: str, name: str, encoded: str) -> str:
    pattern = rf"private const {re.escape(name)}='[^']*';"
    replacement = f"private const {name}='{encoded}';"
    updated, count = re.subn(pattern, replacement, php, count=1)
    if count != 1:
        raise SystemExit(f"cannot replace {name} in Atomic package")
    return updated


def build_bridge(source: dict[str, bytes], target: dict[str, bytes]) -> str:
    gh = "app/CoreUpdates/GitHubClient.php"
    store = "app/UpdateCredentialStore.php"
    page = "update-credential.php"
    for rel in (gh, store, page):
        if rel not in target:
            raise SystemExit(f"bridge target missing {rel}")
    if gh not in source:
        raise SystemExit("bridge source GitHubClient missing")
    if store in source or page in source:
        raise SystemExit("V2.47.10 unexpectedly already contains recovery files")

    payload = {rel: base64.b64encode(target[rel]).decode() for rel in (gh, store, page)}
    hashes = {rel: sha256_bytes(target[rel]) for rel in (gh, store, page)}
    old_gh = sha256_bytes(source[gh])

    template = r'''<?php
declare(strict_types=1);

final class VfP01V24710AuthBridge
{
    private const SOURCE_VERSION = '2.47.10';
    private const SOURCE_GITHUB_CLIENT_SHA = '@@OLD_GH@@';
    private const PAYLOAD = '@@PAYLOAD@@';
    private const HASHES = '@@HASHES@@';

    private static function decode(string $value): array
    {
        $raw = base64_decode($value, true);
        $decoded = $raw === false ? null : json_decode($raw, true);
        if (!is_array($decoded)) throw new RuntimeException('Bridge metadata invalid.');
        return $decoded;
    }

    private static function rel(string $rel): string
    {
        if ($rel === '' || $rel[0] === '/' || strpos($rel, '\\') !== false || preg_match('#(^|/)\.\.(/|$)#', $rel)) {
            throw new RuntimeException('Unsafe bridge path.');
        }
        return $rel;
    }

    private static function writeExact(string $path, string $bytes, int $mode = 0640): void
    {
        $dir = dirname($path);
        if (!is_dir($dir) && !@mkdir($dir, 0750, true) && !is_dir($dir)) throw new RuntimeException('Bridge directory create failed.');
        $tmp = $path . '.v24710-auth-stage-' . bin2hex(random_bytes(4));
        $h = @fopen($tmp, 'xb');
        if (!$h) throw new RuntimeException('Bridge temp create failed.');
        try {
            $off = 0; $len = strlen($bytes);
            while ($off < $len) {
                $n = @fwrite($h, substr($bytes, $off));
                if ($n === false || $n === 0) throw new RuntimeException('Bridge short write.');
                $off += $n;
            }
            if (!@fflush($h)) throw new RuntimeException('Bridge flush failed.');
            if (function_exists('fsync')) @fsync($h);
        } finally { @fclose($h); }
        @chmod($tmp, $mode);
        if (!@rename($tmp, $path)) { @unlink($tmp); throw new RuntimeException('Bridge atomic rename failed.'); }
        @chmod($path, $mode);
    }

    public static function selfTest(): array
    {
        $payload = self::decode(self::PAYLOAD);
        $hashes = self::decode(self::HASHES);
        if (array_keys($payload) !== array_keys($hashes)) throw new RuntimeException('Bridge payload identity mismatch.');
        foreach ($payload as $rel => $encoded) {
            self::rel((string)$rel);
            $bytes = base64_decode((string)$encoded, true);
            if ($bytes === false || !hash_equals((string)$hashes[$rel], hash('sha256', $bytes))) {
                throw new RuntimeException('Bridge payload hash mismatch.');
            }
        }
        if (count($payload) !== 3) throw new RuntimeException('Bridge must contain exactly three bounded files.');
        return ['ok'=>true, 'files'=>3, 'network'=>false, 'credential_embedded'=>false];
    }

    public static function run(string $root): array
    {
        self::selfTest();
        $root = rtrim(realpath($root) ?: $root, '/');
        if (!defined('VF_VERSION') || VF_VERSION !== self::SOURCE_VERSION) throw new RuntimeException('Bridge accepts exact V2.47.10 only.');
        if (trim((string)@file_get_contents($root . '/VERSION.txt')) !== self::SOURCE_VERSION) throw new RuntimeException('Installed VERSION is not exact V2.47.10.');

        $ghRel = 'app/CoreUpdates/GitHubClient.php';
        $ghPath = $root . '/' . $ghRel;
        if (!is_file($ghPath) || is_link($ghPath)) throw new RuntimeException('GitHubClient source missing or unsafe.');
        $hashes = self::decode(self::HASHES);
        $currentGh = hash_file('sha256', $ghPath) ?: '';
        $targetGh = (string)$hashes[$ghRel];
        if (!hash_equals(self::SOURCE_GITHUB_CLIENT_SHA, $currentGh) && !hash_equals($targetGh, $currentGh)) {
            throw new RuntimeException('GitHubClient source bytes are not the fixed V2.47.10 bridge source.');
        }

        $payload = self::decode(self::PAYLOAD);
        $backup = [];
        $backupRoot = rtrim((string)constant('VF_PRIVATE_ROOT'), '/') . '/update-auth/bridge-v24710-backup';
        if (!is_dir($backupRoot) && !@mkdir($backupRoot, 0700, true) && !is_dir($backupRoot)) throw new RuntimeException('Cannot create private bridge backup directory.');
        @chmod($backupRoot, 0700);
        $ghBackup = $backupRoot . '/GitHubClient.php';
        if (!is_file($ghBackup)) self::writeExact($ghBackup, (string)file_get_contents($ghPath), 0600);
        if (!hash_equals($currentGh, hash_file('sha256', $ghBackup) ?: '')) throw new RuntimeException('GitHubClient backup verification failed.');

        try {
            foreach ($payload as $rel => $encoded) {
                $rel = self::rel((string)$rel);
                $path = $root . '/' . $rel;
                $backup[$rel] = is_file($path) && !is_link($path) ? base64_encode((string)file_get_contents($path)) : null;
                if (is_link($path)) throw new RuntimeException('Bridge target symlink rejected.');
                $bytes = base64_decode((string)$encoded, true);
                if ($bytes === false) throw new RuntimeException('Bridge payload decode failed.');
                self::writeExact($path, $bytes, 0640);
                if (!hash_equals((string)$hashes[$rel], hash_file('sha256', $path) ?: '')) throw new RuntimeException('Bridge post-write hash verification failed.');
            }
            if (trim((string)file_get_contents($root . '/VERSION.txt')) !== self::SOURCE_VERSION) throw new RuntimeException('Bridge changed VERSION unexpectedly.');
            return ['ok'=>true, 'version'=>self::SOURCE_VERSION, 'files'=>3, 'backup_verified'=>true, 'network'=>false];
        } catch (Throwable $e) {
            foreach ($backup as $rel => $encoded) {
                $path = $root . '/' . self::rel((string)$rel);
                if ($encoded === null) @unlink($path);
                else self::writeExact($path, (string)base64_decode((string)$encoded, true), 0640);
            }
            throw new RuntimeException('Bridge failed and restored previous source: ' . $e->getMessage(), 0, $e);
        }
    }
}

if (defined('VF_P01_V24710_AUTH_BRIDGE_LIBRARY_MODE') && VF_P01_V24710_AUTH_BRIDGE_LIBRARY_MODE) return;

$root = __DIR__;
require_once $root . '/app/bootstrap.php';
vf_security_headers(true);
header('X-Robots-Tag: noindex,nofollow,noarchive');
header('Cache-Control: no-store, private');
if (!vf_is_installed()) { header('Location: setup.php'); exit; }
if (!vf_is_admin()) { header('Location: ./'); exit; }
if (VF_VERSION !== '2.47.10') { http_response_code(409); echo '<meta charset="utf-8"><p>此一次性桥接器只适用于 VF Start V2.47.10。</p>'; exit; }
$csrf = vf_csrf_token();
$error = '';
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    try {
        $provided = (string)($_POST['csrf'] ?? '');
        if (!hash_equals($csrf, $provided)) throw new RuntimeException('请求已过期，请刷新后重试。');
        VfP01V24710AuthBridge::run($root);
        header('Location: update-credential.php?bridge=v24710');
        exit;
    } catch (Throwable $e) { $error = htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8'); }
}
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VF Start 更新授权恢复</title></head><body><main><h1>更新授权恢复</h1><?php if($error!==''):?><p><?= $error ?></p><?php endif;?><p>此一次性桥接器只为 V2.47.10 补入正式的“更新授权”恢复入口，不升级版本、不改变 Schema、不联网、不包含任何 Token。</p><form method="post"><input type="hidden" name="csrf" value="<?=htmlspecialchars($csrf,ENT_QUOTES,'UTF-8')?>"><button type="submit">启用更新授权恢复</button></form></main></body></html>
'''
    return template.replace('@@OLD_GH@@', old_gh).replace('@@PAYLOAD@@', b64json(payload)).replace('@@HASHES@@', b64json(hashes))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--candidate-commit', required=True)
    ap.add_argument('--source-commit', required=True)
    ap.add_argument('--candidate-tree', required=True)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    base = load_base(here / 'p01-build-release.py')
    base.VERSION = VERSION
    base.SOURCE_VERSION = SOURCE_VERSION
    base.SCHEMA = SCHEMA

    candidate = Path(args.candidate).resolve()
    source_root = Path(args.source).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    target = base.collect(candidate)
    source = base.collect(source_root)
    if target.get('VERSION.txt', b'').strip() != VERSION.encode(): raise SystemExit('target VERSION mismatch')
    if source.get('VERSION.txt', b'').strip() != SOURCE_VERSION.encode(): raise SystemExit('source VERSION mismatch')
    if target.get('app/bootstrap.php') is None or source.get('app/bootstrap.php') is None: raise SystemExit('bootstrap missing')

    runtime_files = {k: sha256_bytes(v) for k, v in sorted(target.items())}
    release_manifest = {
        'project': 'VF Start',
        'project_id': PROJECT_ID,
        'component_id': COMPONENT_ID,
        'version': VERSION,
        'release_type': 'formal-release',
        'source_commit': args.candidate_commit,
        'source_tree': args.candidate_tree,
        'production_source_commit': args.source_commit,
        'source_version': SOURCE_VERSION,
        'schema_version': SCHEMA,
        'schema_change': False,
        'schema_migrations': [],
        'runtime_data_included': False,
        'private_data_included': False,
        'update': {
            'from_versions': [SOURCE_VERSION],
            'asset_name': UPDATE_NAME,
            'backup_required': True,
            'rollback_supported': True,
            'bridge': BRIDGE_NAME,
        },
        'runtime_hashed_file_count': len(runtime_files),
        'runtime_files': runtime_files,
    }
    target_with = dict(target)
    target_with['release-manifest.json'] = (json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\n').encode()

    bridge = build_bridge(source, target)
    bridge_bytes = bridge.encode()
    (out / BRIDGE_NAME).write_bytes(bridge_bytes)

    repair = base.build_repair(source, target_with, sha256_bytes(target['app/UpdateManager.php']))
    alternates = {
        'app/UpdateManager.php': sorted({sha256_bytes(source['app/UpdateManager.php']), sha256_bytes(target['app/UpdateManager.php'])}),
        'app/CoreUpdates/GitHubClient.php': sorted({sha256_bytes(source['app/CoreUpdates/GitHubClient.php']), sha256_bytes(target['app/CoreUpdates/GitHubClient.php'])}),
    }
    repair = replace_const(repair, 'SOURCE_ALTERNATES', b64json(alternates))
    removed = sorted((set(source) - set(target_with)) | {BRIDGE_NAME})
    repair = replace_const(repair, 'REMOVED', b64json(removed))
    (out / REPAIR_NAME).write_text(repair, encoding='utf-8', newline='\n')

    base.deterministic_zip(out / UPDATE_NAME, {REPAIR_NAME: repair.encode()})
    base.deterministic_zip(out / FULL_NAME, target_with)

    update_bytes = (out / UPDATE_NAME).stat().st_size
    update_sha = sha256_file(out / UPDATE_NAME)
    core_manifest = {
        'schema_version': '1.0',
        'project_id': PROJECT_ID,
        'component_id': COMPONENT_ID,
        'enabled': True,
        'target_version': VERSION,
        'update_type': 'ATOMIC',
        'from_versions': [SOURCE_VERSION],
        'schema_from': SCHEMA,
        'schema_to': SCHEMA,
        'repository': REPOSITORY,
        'release_tag': 'v' + VERSION,
        'asset_name': UPDATE_NAME,
        'asset_bytes': update_bytes,
        'asset_sha256': update_sha,
        'backup_required': True,
        'rollback_supported': True,
        'minimum_php': '8.0',
        'released_at': '2026-09-17T00:00:00Z',
        'notes': {'summary': 'V2.47.11 restores private update authorization recovery and stale-discovery handling.'},
    }
    (out / 'P01.json').write_text(json.dumps(core_manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    files = [p for p in sorted(out.iterdir()) if p.is_file() and p.name != 'SHA256SUMS.txt']
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{sha256_file(p)}  {p.name}\n' for p in files), encoding='utf-8')
    result = {
        'status': 'PASS',
        'version': VERSION,
        'source_version': SOURCE_VERSION,
        'schema': SCHEMA,
        'candidate_commit': args.candidate_commit,
        'candidate_tree': args.candidate_tree,
        'source_commit': args.source_commit,
        'full_name': FULL_NAME,
        'full_bytes': (out / FULL_NAME).stat().st_size,
        'full_sha256': sha256_file(out / FULL_NAME),
        'update_name': UPDATE_NAME,
        'update_bytes': update_bytes,
        'update_sha256': update_sha,
        'bridge_name': BRIDGE_NAME,
        'bridge_bytes': (out / BRIDGE_NAME).stat().st_size,
        'bridge_sha256': sha256_file(out / BRIDGE_NAME),
        'repair_sha256': sha256_file(out / REPAIR_NAME),
    }
    (out / 'BUILD_RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
