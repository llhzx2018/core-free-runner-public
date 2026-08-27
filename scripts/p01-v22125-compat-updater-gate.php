<?php
declare(strict_types=1);

$root = $argv[1] ?? '';
$manifestPath = $argv[2] ?? '';
$asset = $argv[3] ?? '';
if ($root === '' || !is_dir($root) || !is_file($manifestPath) || !is_file($asset)) {
    fwrite(STDERR, "invalid gate inputs\n");
    exit(2);
}
chdir($root);
require 'app/bootstrap.php';
require_once 'app/UpdateManager.php';
$manifest = json_decode((string)file_get_contents($manifestPath), true, 512, JSON_THROW_ON_ERROR);
$pdo = vf_db();
$manager = new VfUpdateManager($pdo, [
    'root' => getcwd(),
    'private_root' => VF_PRIVATE_ROOT,
    'current_version' => '2.21.24',
    'manifest_fetcher' => static fn(...$args) => $manifest,
    'asset_downloader' => static function(array $m, string $dest) use ($asset): array {
        if (!copy($asset, $dest)) throw new RuntimeException('compat asset copy failed');
        return ['size' => filesize($dest)];
    },
    'backup_creator' => static fn(string $from, string $to): array => ['backup_key' => 'compat-gate-' . $from . '-' . $to],
]);
$check = $manager->check(true);
if (empty($check['ok']) || ($check['latest_version'] ?? '') !== '2.21.25' || empty($check['available']) || empty($check['can_update'])) {
    throw new RuntimeException('check rejected compat manifest: ' . json_encode($check, JSON_UNESCAPED_UNICODE));
}
echo "P01_V22124_REAL_CHECK=PASS\n";
$prep = $manager->prepare();
if (empty($prep['ok']) || ($prep['asset_name'] ?? '') !== 'VF_Start_V2.21.25_UPDATE.zip' || ($prep['to_version'] ?? '') !== '2.21.25') {
    throw new RuntimeException('prepare failed: ' . json_encode($prep, JSON_UNESCAPED_UNICODE));
}
echo "P01_V22124_REAL_PREPARE=PASS\n";
$install = $manager->install((string)$prep['operation_id']);
if (empty($install['ok']) || empty($install['updated']) || ($install['to_version'] ?? '') !== '2.21.25') {
    throw new RuntimeException('install failed: ' . json_encode($install, JSON_UNESCAPED_UNICODE));
}
echo "P01_V22124_REAL_INSTALL=PASS\n";
