<?php

declare(strict_types=1);

$web = rtrim((string)($argv[1] ?? ''), '/\\');
if ($web === '' || !is_file($web . '/bootstrap.php')) {
    fwrite(STDERR, "P04_PROVIDER_SAFE_ACTIONS_SEED_FAIL: runtime bootstrap missing\n");
    exit(1);
}

require $web . '/bootstrap.php';

try {
    $pdo = Database::connection();
    $providerService = new \VFInfra\Core\ProviderService();
    $provider = $providerService->ensureProvider('vultr', 'Vultr', 'compute', ['assets', 'billing']);
    if (empty($provider['id'])) throw new RuntimeException('synthetic provider unavailable');

    $account = $providerService->createAccount((int)$provider['id'], 'Fresh Safe Actions Account', 'fresh-safe-actions-account');
    if (empty($account['id'])) throw new RuntimeException('synthetic account unavailable');
    $accountId = (int)$account['id'];
    $providerService->setLifecycle($accountId, 'active');

    Database::assertHealthy($pdo);
    echo json_encode([
        'status' => 'PASS',
        'synthetic_only' => true,
        'external_provider_api_called' => false,
        'provider_account_id' => $accountId,
    ], JSON_UNESCAPED_SLASHES) . "\n";
} catch (Throwable $e) {
    fwrite(STDERR, 'P04_PROVIDER_SAFE_ACTIONS_SEED_FAIL: ' . Support::sanitizeError($e->getMessage()) . "\n");
    exit(1);
}
