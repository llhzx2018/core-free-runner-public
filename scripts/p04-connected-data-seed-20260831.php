<?php

declare(strict_types=1);

$web = rtrim((string)($argv[1] ?? ''), '/\\');
if ($web === '' || !is_file($web . '/bootstrap.php')) {
    fwrite(STDERR, "P04_CONNECTED_SEED_FAIL: runtime bootstrap missing\n");
    exit(1);
}

require $web . '/bootstrap.php';

try {
    $pdo = Database::connection();
    $now = Support::now();

    $providerService = new \VFInfra\Core\ProviderService();
    $provider = $providerService->ensureProvider('vultr', 'Vultr', 'compute', ['assets', 'billing']);
    if (empty($provider['id'])) {
        throw new RuntimeException('synthetic provider unavailable');
    }

    $account = $providerService->createAccount((int)$provider['id'], 'Fresh Synthetic Account', 'fresh-synthetic-account');
    if (empty($account['id'])) {
        throw new RuntimeException('synthetic provider account unavailable');
    }
    $accountId = (int)$account['id'];
    $providerService->setLifecycle($accountId, 'active');

    $domain = (new DomainRepository())->save([
        'domain' => 'transition.example',
        'project_name' => 'Fresh Transition',
        'registrar' => 'Vultr',
        'renewal_price' => '12.00',
        'currency' => 'USD',
        'renewal_policy' => 'manual',
        'manual_expiry_date' => '2027-08-31',
        'notes' => 'Synthetic Fresh transition audit data only.',
    ]);
    if (empty($domain['id'])) {
        throw new RuntimeException('synthetic domain unavailable');
    }
    $domainId = (int)$domain['id'];
    $pdo->prepare("UPDATE domains SET registrar_provider_account_id=:account,registrar_last_synced_at=:t,registrar_remote_status='active',updated_at=:t WHERE id=:id")
        ->execute([':account' => $accountId, ':t' => $now, ':id' => $domainId]);

    $stmt = $pdo->prepare(
        "INSERT INTO compute_instances(provider_account_id,external_instance_id,label,hostname,external_status,power_status,primary_ipv4,region,plan_code,os_label,backups_enabled,first_seen_at,last_seen_at,updated_at) " .
        "VALUES(:account,:external,:label,:hostname,'active','running','192.0.2.44','ewr','synthetic-1','Synthetic Linux',1,:t,:t,:t)"
    );
    $stmt->execute([
        ':account' => $accountId,
        ':external' => 'fresh-synthetic-server-001',
        ':label' => 'vf-transition-server',
        ':hostname' => 'vf-transition-server.example',
        ':t' => $now,
    ]);
    $serverId = (int)$pdo->lastInsertId();
    if ($serverId <= 0) {
        throw new RuntimeException('synthetic compute instance unavailable');
    }

    Database::assertHealthy($pdo);

    echo json_encode([
        'status' => 'PASS',
        'synthetic_only' => true,
        'external_provider_api_called' => false,
        'provider_account_id' => $accountId,
        'domain_id' => $domainId,
        'server_id' => $serverId,
    ], JSON_UNESCAPED_SLASHES) . "\n";
} catch (Throwable $e) {
    fwrite(STDERR, 'P04_CONNECTED_SEED_FAIL: ' . Support::sanitizeError($e->getMessage()) . "\n");
    exit(1);
}
