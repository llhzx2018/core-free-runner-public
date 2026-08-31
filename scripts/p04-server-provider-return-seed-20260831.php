<?php
declare(strict_types=1);

$root = rtrim((string)($argv[1] ?? ''), '/\\');
if ($root === '' || !is_file($root . '/bootstrap.php')) {
    fwrite(STDERR, "P04_RETURN_FIXTURE_RUNTIME_ROOT_INVALID\n");
    exit(61);
}
require $root . '/bootstrap.php';

$pdo = Database::connection();
$now = Support::now();
$providerId = (int)$pdo->query("SELECT id FROM providers WHERE provider_key='linode' LIMIT 1")->fetchColumn();
if ($providerId <= 0) {
    fwrite(STDERR, "P04_RETURN_FIXTURE_LINODE_PROVIDER_MISSING\n");
    exit(62);
}

$providers = [];
$servers = [];
$pdo->beginTransaction();
try {
    for ($i = 1; $i <= 14; $i++) {
        $suffix = str_pad((string)$i, 2, '0', STR_PAD_LEFT);
        $externalAccount = 'return-audit-provider-' . $suffix;
        $providerName = 'Return Audit Provider ' . $suffix;
        $externalInstance = 'return-server-' . $suffix;
        $serverName = 'return-server-' . $suffix;
        $ip = '203.0.113.' . (50 + $i);

        $stmt = $pdo->prepare("SELECT id FROM provider_accounts WHERE provider_id=:pid AND external_account_id=:external LIMIT 1");
        $stmt->execute([':pid' => $providerId, ':external' => $externalAccount]);
        $accountId = (int)$stmt->fetchColumn();
        $stmt->closeCursor();
        if ($accountId <= 0) {
            $stmt = $pdo->prepare("INSERT INTO provider_accounts(provider_id,display_name,external_account_id,status,last_verified_at,created_at,updated_at,archived_at) VALUES(:pid,:name,:external,'active',:t,:t,:t,NULL)");
            $stmt->execute([':pid' => $providerId, ':name' => $providerName, ':external' => $externalAccount, ':t' => $now]);
            $accountId = (int)$pdo->lastInsertId();
        } else {
            $pdo->prepare("UPDATE provider_accounts SET display_name=:name,status='active',last_verified_at=:t,updated_at=:t,archived_at=NULL WHERE id=:id")
                ->execute([':name' => $providerName, ':t' => $now, ':id' => $accountId]);
        }

        $pdo->prepare("INSERT INTO provider_account_sync_state(provider_account_id,sync_enabled,desired_sync_enabled,last_started_at,last_finished_at,last_successful_at,last_status,consecutive_failures,backoff_until,next_sync_at,last_error_code,last_error_summary,inventory_count,cursor_json,updated_at) VALUES(:id,1,1,datetime('now','-5 minute'),datetime('now','-4 minute'),datetime('now','-4 minute'),'success',0,NULL,datetime('now','+30 minute'),NULL,NULL,1,NULL,:t) ON CONFLICT(provider_account_id) DO UPDATE SET sync_enabled=1,desired_sync_enabled=1,last_started_at=datetime('now','-5 minute'),last_finished_at=datetime('now','-4 minute'),last_successful_at=datetime('now','-4 minute'),last_status='success',consecutive_failures=0,backoff_until=NULL,next_sync_at=datetime('now','+30 minute'),last_error_code=NULL,last_error_summary=NULL,inventory_count=1,updated_at=:t")
            ->execute([':id' => $accountId, ':t' => $now]);

        $stmt = $pdo->prepare("SELECT id FROM compute_instances WHERE provider_account_id=:aid AND external_instance_id=:external LIMIT 1");
        $stmt->execute([':aid' => $accountId, ':external' => $externalInstance]);
        $instanceId = (int)$stmt->fetchColumn();
        $stmt->closeCursor();
        if ($instanceId <= 0) {
            $stmt = $pdo->prepare("INSERT INTO compute_instances(provider_account_id,external_instance_id,label,hostname,external_status,power_status,primary_ipv4,ipv6_json,region,plan_code,os_label,backups_enabled,remote_created_at,first_seen_at,last_seen_at,missing_since,updated_at,archived_at) VALUES(:aid,:external,:label,:host,'running','running',:ip,'[]','us-east','g6-standard-1','Ubuntu 24.04',1,datetime('now','-30 day'),:t,:t,NULL,:t,NULL)");
            $stmt->execute([':aid' => $accountId, ':external' => $externalInstance, ':label' => $serverName, ':host' => $serverName, ':ip' => $ip, ':t' => $now]);
            $instanceId = (int)$pdo->lastInsertId();
        } else {
            $pdo->prepare("UPDATE compute_instances SET label=:label,hostname=:host,external_status='running',power_status='running',primary_ipv4=:ip,region='us-east',plan_code='g6-standard-1',os_label='Ubuntu 24.04',last_seen_at=:t,missing_since=NULL,updated_at=:t,archived_at=NULL WHERE id=:id")
                ->execute([':label' => $serverName, ':host' => $serverName, ':ip' => $ip, ':t' => $now, ':id' => $instanceId]);
        }

        $stmt = $pdo->prepare("SELECT id FROM assets WHERE source_module='compute' AND source_object_id=:iid LIMIT 1");
        $stmt->execute([':iid' => $instanceId]);
        $assetId = (int)$stmt->fetchColumn();
        $stmt->closeCursor();
        if ($assetId <= 0) {
            $stmt = $pdo->prepare("INSERT INTO assets(asset_type,asset_key,display_name,project_name,provider_account_id,parent_asset_id,status,source_module,source_object_id,created_at,updated_at,archived_at) VALUES('compute_instance',:key,:name,'Synthetic Return Audit',:aid,NULL,'active','compute',:iid,:t,:t,NULL)");
            $stmt->execute([':key' => 'linode:' . $externalAccount . ':' . $externalInstance, ':name' => $serverName, ':aid' => $accountId, ':iid' => $instanceId, ':t' => $now]);
            $assetId = (int)$pdo->lastInsertId();
        } else {
            $pdo->prepare("UPDATE assets SET display_name=:name,project_name='Synthetic Return Audit',provider_account_id=:aid,status='active',archived_at=NULL,updated_at=:t WHERE id=:id")
                ->execute([':name' => $serverName, ':aid' => $accountId, ':t' => $now, ':id' => $assetId]);
        }

        $pdo->prepare("INSERT INTO provider_billing_sync_state(provider_account_id,sync_enabled,desired_sync_enabled,last_started_at,last_finished_at,last_successful_at,last_status,consecutive_failures,backoff_until,next_sync_at,last_error_code,last_error_summary,updated_at) VALUES(:id,1,1,datetime('now','-5 minute'),datetime('now','-4 minute'),datetime('now','-4 minute'),'success',0,NULL,datetime('now','+30 minute'),NULL,NULL,:t) ON CONFLICT(provider_account_id) DO UPDATE SET sync_enabled=1,desired_sync_enabled=1,last_started_at=datetime('now','-5 minute'),last_finished_at=datetime('now','-4 minute'),last_successful_at=datetime('now','-4 minute'),last_status='success',consecutive_failures=0,backoff_until=NULL,next_sync_at=datetime('now','+30 minute'),last_error_code=NULL,last_error_summary=NULL,updated_at=:t")
            ->execute([':id' => $accountId, ':t' => $now]);
        $pdo->prepare("INSERT INTO provider_billing_snapshots(provider_account_id,currency,balance,credit,amount_due,month_to_date_usage,pending_charges,last_payment_amount,last_payment_at,next_invoice_at,provider_status,capabilities_json,warnings_json,observed_at,updated_at) VALUES(:id,'USD','0',NULL,:due,:usage,'0',NULL,NULL,datetime('now','+7 day'),'active','{\"amount_due\":true,\"month_to_date_usage\":true}','[]',:t,:t) ON CONFLICT(provider_account_id) DO UPDATE SET currency='USD',amount_due=:due,month_to_date_usage=:usage,pending_charges='0',next_invoice_at=datetime('now','+7 day'),provider_status='active',warnings_json='[]',observed_at=:t,updated_at=:t")
            ->execute([':id' => $accountId, ':due' => number_format(5 + $i / 10, 2, '.', ''), ':usage' => number_format(3 + $i / 10, 2, '.', ''), ':t' => $now]);

        $providers[] = ['id' => $accountId, 'name' => $providerName, 'external_account_id' => $externalAccount];
        $servers[] = ['instance_id' => $instanceId, 'asset_id' => $assetId, 'name' => $serverName, 'provider_account_id' => $accountId];
    }
    $pdo->commit();
    echo json_encode(['providers' => $providers, 'servers' => $servers], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
    echo "P04_SERVER_PROVIDER_RETURN_FIXTURE_PASS\n";
} catch (Throwable $e) {
    if ($pdo->inTransaction()) $pdo->rollBack();
    fwrite(STDERR, 'P04_SERVER_PROVIDER_RETURN_FIXTURE_FAIL ' . Support::sanitizeError($e->getMessage()) . "\n");
    exit(63);
}
