<?php

declare(strict_types=1);

$web = rtrim((string)($argv[1] ?? ''), '/\\');
if ($web === '' || !is_file($web . '/bootstrap.php')) {
    fwrite(STDERR, "P04_ATTENTION_SEED_FAIL: runtime bootstrap missing\n");
    exit(1);
}

require $web . '/bootstrap.php';

try {
    $pdo = Database::connection();
    $now = Support::now();

    $providerService = new \VFInfra\Core\ProviderService();
    $provider = $providerService->ensureProvider('vultr', 'Vultr', 'compute', ['assets', 'billing']);
    if (empty($provider['id'])) throw new RuntimeException('synthetic provider unavailable');

    $account = $providerService->createAccount((int)$provider['id'], 'Fresh Attention Account', 'fresh-attention-account');
    if (empty($account['id'])) throw new RuntimeException('synthetic account unavailable');
    $accountId = (int)$account['id'];
    $providerService->setLifecycle($accountId, 'degraded');

    $domain = (new DomainRepository())->save([
        'domain' => 'attention.example',
        'project_name' => 'Fresh Attention Audit',
        'registrar' => 'Vultr',
        'renewal_price' => '18.00',
        'currency' => 'USD',
        'renewal_policy' => 'manual',
        'manual_expiry_date' => '2026-09-05',
        'notes' => 'Synthetic attention audit data only.',
    ]);
    if (empty($domain['id'])) throw new RuntimeException('synthetic attention domain unavailable');
    $domainId = (int)$domain['id'];
    $pdo->prepare("UPDATE domains SET registrar_provider_account_id=:account,registrar_last_synced_at=:t,registrar_remote_status='active',updated_at=:t WHERE id=:id")
        ->execute([':account' => $accountId, ':t' => $now, ':id' => $domainId]);

    $stmt = $pdo->prepare(
        "INSERT INTO compute_instances(provider_account_id,external_instance_id,label,hostname,external_status,power_status,primary_ipv4,region,plan_code,os_label,backups_enabled,first_seen_at,last_seen_at,updated_at) " .
        "VALUES(:account,:external,:label,:hostname,'stopped','stopped','192.0.2.55','ewr','synthetic-risk','Synthetic Linux',1,:t,:t,:t)"
    );
    $stmt->execute([
        ':account' => $accountId,
        ':external' => 'fresh-attention-server-001',
        ':label' => 'attention-server',
        ':hostname' => 'attention-server.example',
        ':t' => $now,
    ]);
    $serverId = (int)$pdo->lastInsertId();
    if ($serverId <= 0) throw new RuntimeException('synthetic attention server unavailable');

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
    fwrite(STDERR, 'P04_ATTENTION_SEED_FAIL: ' . Support::sanitizeError($e->getMessage()) . "\n");
    exit(1);
}
