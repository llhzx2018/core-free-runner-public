<?php
declare(strict_types=1);

/**
 * P01 · VF Start V2.21.14 Credential Runtime Activator
 *
 * OPERATIONS / ONE-TIME PRODUCTION RUNTIME ACTIVATION ONLY.
 *
 * Purpose:
 * - reuse the proven P02 sealed Runner -> VPS relay model;
 * - receive the existing VF_PRIVATE_READ_TOKEN only as a sodium sealed payload;
 * - persist it only in VF Start's protected private runtime storage;
 * - add a runtime-only adapter to app/.runtime.php so bootstrap provides
 *   VF_PRIVATE_READ_TOKEN to the already sealed UpdateManager via getenv();
 * - verify real core-updates + GitHub Release discovery;
 * - never execute the V2.21.15 Production upgrade.
 *
 * This artifact does NOT change VERSION, Schema, business data, Browser Extension,
 * Candidate, Tag, Release, P01.json or Git main.
 */
final class VfP01CredentialRuntimeActivator
{
    private const SOURCE_VERSION = '2.21.14';
    private const SOURCE_SCHEMA = '2026080902';
    private const PROJECT_ID = 'P01';
    private const COMPONENT_ID = 'APP';
    private const CORE_REPOSITORY = 'llhzx2018/core-updates';
    private const CORE_PROJECT_FILE = 'P01.json';
    private const PRODUCT_REPOSITORY = 'llhzx2018/vf-start';
    private const EXPECTED_RELEASE_TAG = 'v2.21.15';
    private const EXPECTED_ASSET = 'VF_Start_V2.21.15_UPDATE.zip';
    private const EXPECTED_ASSET_BYTES = 1073031;
    private const EXPECTED_ASSET_SHA256 = '7562fbc82b59de09c1f1b0dc77e0ca2e2f73ad556f969d6225a7cca5fd1b5947';
    private const RELAY_TTL_SECONDS = 1800;
    private const MAX_RELAY_BYTES = 16384;
    private const RUNTIME_MARKER = 'P01_VF_PRIVATE_READ_TOKEN_RUNTIME_ADAPTER_V1';
    private const SECRET_DIR_NAME = 'runtime-secrets';
    private const SECRET_FILE_NAME = 'vf-private-read-token.php';
    private const RELAY_STATE_FILE = 'p01-private-read-token-relay.php';
    private const ACTIVATION_JOURNAL_FILE = 'p01-private-read-token-activation-journal.php';
    private const RESULT_FILE = 'p01-private-read-token-activation-result.php';

    private const SOURCE_ANCHORS = [
        'VERSION.txt' => 'd22a9d0df210522a1f54e6ddde9d59b457f01e3ca4e2362524756ac0a940e15d',
        'index.php' => '7cb9204cbd2461aaf069cfea985ce63cda2d223491cdbf01ec5746698cded0d8',
        'api.php' => 'fa04a04a7fa787608d73e490d7a12738b37251987af8b3ef5c760c0d1cf0fbd2',
        'update.php' => 'd469f0159c1e911066dd235a31f774a769d2a26de6fc398f9180aadd67c8c59c',
        'app/bootstrap.php' => '4d01ab2fdb05ef296a49ed8f708732ce54211a3ff6a0c35e6e5b2de895d6838a',
        'app/MigrationRunner.php' => 'f43cdb8e35a7956db820cc2efa3925c34394369c366e74fde22ff04b691a6477',
        'app/Repository.php' => '0ae69f4164255691fbc1b8428d29e557f612161ee1f0127f55196bf3e3fd9292',
        'app/Auth.php' => '01915abb8abbeef1f8dcb16b20f0a96ad429f6cf94a53ceff1fc8067184f43bd',
        'migrations/2026080902_v2192_data_governance_review.php' => '9423b4f8461426577edd069820fd8df2f835ae71a1c8e769eeb52dacc322d705',
    ];

    private const BRIDGE_HASHES = [
        'app/UpdateManager.php' => '13257a93f3d3cf72de543a26503f2060de140e929db221ce00baf81f54895e16',
        'app/CoreUpdates/UpdateCore.php' => 'e84be2370fa96552838bbcc0b235162118d709f158aed461a52c07cde5b85c24',
        'app/CoreUpdates/GitHubClient.php' => 'f3a934f58555b4cc249fd08b278ba9a4414e65859b61267b91bae17f0d0a58ef',
    ];

    public static function main(): void
    {
        self::headers();
        try {
            $rootEvidence = self::discoverRoot();
            $root = (string)$rootEvidence['root'];
            require_once $root . '/app/bootstrap.php';
            self::assertRuntime($root);
            self::recoverInterruptedActivation($root);

            $relay = (string)($_GET['relay'] ?? '');
            if ($relay === 'info') {
                self::requireMethod('GET');
                self::json(self::relayInfo($root, $rootEvidence));
            }
            if ($relay === 'token') {
                self::requireMethod('POST');
                self::json(self::receiveSealedToken($root, $rootEvidence));
            }
            if ($relay === 'verify') {
                self::requireMethod('GET');
                $result = self::verifyPersistentRuntime($root, $rootEvidence);
                if (!empty($result['ok']) && !empty($result['ready'])) {
                    register_shutdown_function(static function (): void { @unlink(__FILE__); });
                }
                self::json($result);
            }
            self::htmlStatus($rootEvidence);
        } catch (Throwable $e) {
            self::fail($e->getMessage());
        }
    }

    private static function headers(): void
    {
        if (headers_sent()) return;
        header_remove('X-Powered-By');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('Cache-Control: no-store, private');
        header('Pragma: no-cache');
        header('X-Content-Type-Options: nosniff');
        header('X-Frame-Options: DENY');
        header('Referrer-Policy: no-referrer');
        header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'");
    }

    private static function requireMethod(string $expected): void
    {
        $method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));
        if ($method !== $expected) throw new RuntimeException('METHOD_NOT_ALLOWED');
    }

    private static function json(array $payload, int $status = 200): void
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE), "\n";
        exit;
    }

    private static function fail(string $message): void
    {
        $safe = preg_replace('/(github_pat_|ghp_|gho_|ghu_|ghs_)[A-Za-z0-9_\-]+/i', '[REDACTED]', $message) ?? 'ACTIVATION_FAILED';
        if ((string)($_GET['relay'] ?? '') !== '') self::json(['ok'=>false,'status'=>'fail','error'=>$safe], 409);
        http_response_code(409);
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><meta charset="utf-8"><title>P01 Credential Runtime Activator</title><main style="font:16px/1.6 system-ui;max-width:850px;margin:50px auto;padding:24px"><h1>P01 · Credential Runtime Activator</h1><p style="color:#b42318"><strong>FAIL</strong></p><pre style="white-space:pre-wrap">'.htmlspecialchars($safe, ENT_QUOTES, 'UTF-8').'</pre><p>Production Upgrade: NOT EXECUTED</p></main>';
        exit;
    }

    private static function canonicalDir(string $path): ?string
    {
        $real = realpath($path);
        if ($real === false || !is_dir($real)) return null;
        return rtrim(str_replace('\\', '/', $real), '/');
    }

    private static function sha(string $path): string
    {
        if (!is_file($path) || is_link($path)) return 'ABSENT';
        $sha = hash_file('sha256', $path);
        return is_string($sha) ? strtolower($sha) : 'UNREADABLE';
    }

    private static function safeRel(string $rel): string
    {
        if ($rel === '' || $rel[0] === '/' || strpos($rel, '\\') !== false || preg_match('#(^|/)\.\.(/|$)#', $rel)) throw new RuntimeException('UNSAFE_PATH');
        return $rel;
    }

    private static function seeds(): array
    {
        $seeds = [];
        $add = static function (?string $path) use (&$seeds): void {
            if (!is_string($path) || trim($path) === '') return;
            $real = self::canonicalDir($path);
            if ($real !== null) $seeds[$real] = true;
        };
        $add(__DIR__);
        $add((string)($_SERVER['DOCUMENT_ROOT'] ?? ''));
        $add(dirname((string)($_SERVER['SCRIPT_FILENAME'] ?? __FILE__)));
        foreach (array_keys($seeds) as $seed) {
            $cur = $seed;
            for ($i = 0; $i < 6; $i++) {
                $parent = dirname($cur);
                if ($parent === $cur || $parent === '' || $parent === '/') break;
                $add($parent); $cur = $parent;
            }
        }
        return array_keys($seeds);
    }

    private static function rootEvidence(string $root): ?array
    {
        $root = self::canonicalDir($root) ?? '';
        if ($root === '') return null;
        if (trim((string)@file_get_contents($root . '/VERSION.txt')) !== self::SOURCE_VERSION) return null;
        foreach (self::SOURCE_ANCHORS as $rel => $expected) {
            $path = $root . '/' . self::safeRel($rel);
            if (!is_file($path) || is_link($path) || !hash_equals($expected, self::sha($path))) return null;
        }
        foreach (self::BRIDGE_HASHES as $rel => $expected) {
            $path = $root . '/' . self::safeRel($rel);
            if (!is_file($path) || is_link($path) || !hash_equals($expected, self::sha($path))) return null;
        }
        if (!is_file($root . '/app/.runtime.php') || is_link($root . '/app/.runtime.php')) return null;
        return ['root'=>$root,'fingerprint'=>substr(hash('sha256', $root), 0, 20),'bridge_source'=>'CORE-UPDATES'];
    }

    private static function discoverRoot(): array
    {
        $matches = [];
        foreach (self::seeds() as $seed) { $e = self::rootEvidence($seed); if ($e !== null) $matches[$e['root']] = $e; }
        if (count($matches) === 0) throw new RuntimeException('ROOT_NOT_FOUND');
        if (count($matches) !== 1) throw new RuntimeException('ROOT_AMBIGUOUS');
        return array_values($matches)[0];
    }

    private static function assertRuntime(string $root): void
    {
        $vfRoot = defined('VF_ROOT') ? self::canonicalDir((string)VF_ROOT) : null;
        if ($vfRoot === null || !hash_equals($root, $vfRoot)) throw new RuntimeException('RUNTIME_ROOT_MISMATCH');
        if (!defined('VF_VERSION') || (string)VF_VERSION !== self::SOURCE_VERSION) throw new RuntimeException('RUNTIME_VERSION_MISMATCH');
        if (!defined('VF_PRIVATE_ROOT') || !defined('VF_RUNTIME_FILE')) throw new RuntimeException('PRIVATE_RUNTIME_UNAVAILABLE');
        $privateRoot = self::canonicalDir((string)VF_PRIVATE_ROOT);
        if ($privateRoot === null || dirname($privateRoot) !== $root || !preg_match('/^\.vfnav-data-[a-f0-9]{32}$/', basename($privateRoot))) throw new RuntimeException('PRIVATE_ROOT_IDENTITY_MISMATCH');
        if (is_link((string)VF_PRIVATE_ROOT) || is_link((string)VF_RUNTIME_FILE)) throw new RuntimeException('PRIVATE_RUNTIME_SYMLINK_REJECTED');
        if (self::schemaHead() !== self::SOURCE_SCHEMA) throw new RuntimeException('RUNTIME_SCHEMA_MISMATCH');
    }

    private static function schemaHead(): string
    {
        if (!function_exists('vf_db') || !class_exists('VfMigrationRunner')) return '';
        try { $state = (new VfMigrationRunner(vf_db()))->schemaState(); return trim((string)($state['current_head'] ?? '')); }
        catch (Throwable $e) { return ''; }
    }

    private static function secretDir(): string { return rtrim((string)VF_PRIVATE_ROOT, '/') . '/' . self::SECRET_DIR_NAME; }
    private static function secretFile(): string { return self::secretDir() . '/' . self::SECRET_FILE_NAME; }
    private static function stateFile(string $name): string { return rtrim((string)VF_UPDATE_DIR, '/') . '/' . $name; }

    private static function atomicWrite(string $path, string $bytes, int $mode): void
    {
        $dir = dirname($path);
        if (!is_dir($dir) && !@mkdir($dir, 0700, true) && !is_dir($dir)) throw new RuntimeException('PRIVATE_DIRECTORY_CREATE_FAILED');
        if (is_link($dir)) throw new RuntimeException('PRIVATE_DIRECTORY_SYMLINK_REJECTED');
        @chmod($dir, 0700);
        $tmp = $path . '.tmp-' . bin2hex(random_bytes(6));
        $written = @file_put_contents($tmp, $bytes, LOCK_EX);
        if ($written !== strlen($bytes)) { @unlink($tmp); throw new RuntimeException('ATOMIC_STAGE_WRITE_FAILED'); }
        @chmod($tmp, $mode);
        if (!@rename($tmp, $path)) { @unlink($tmp); throw new RuntimeException('ATOMIC_REPLACE_FAILED'); }
        @chmod($path, $mode); clearstatcache(true, $path);
        if (!is_file($path) || is_link($path) || (int)filesize($path) !== strlen($bytes)) throw new RuntimeException('ATOMIC_WRITE_READBACK_FAILED');
    }

    private static function phpReturnFile(array $data): string
    {
        return "<?php\nif (isset(\$_SERVER['SCRIPT_FILENAME']) && realpath((string)\$_SERVER['SCRIPT_FILENAME']) === __FILE__) { http_response_code(404); exit; }\nreturn " . var_export($data, true) . ";\n";
    }

    private static function loadPhpArray(string $path): array
    {
        if (!is_file($path) || is_link($path)) return [];
        $value = include $path; return is_array($value) ? $value : [];
    }

    private static function ensurePrivateGuards(string $dir): void
    {
        if (!is_dir($dir) && !@mkdir($dir, 0700, true) && !is_dir($dir)) throw new RuntimeException('SECRET_DIR_CREATE_FAILED');
        @chmod($dir, 0700);
        if (function_exists('vf_write_storage_guards')) vf_write_storage_guards($dir);
        @chmod($dir . '/index.php', 0600); @chmod($dir . '/.htaccess', 0600); @chmod($dir . '/web.config', 0600);
    }

    private static function runtimeAdapterBytes(string $runtimeBytes): string
    {
        if (strpos($runtimeBytes, self::RUNTIME_MARKER) !== false) return $runtimeBytes;
        if (substr_count($runtimeBytes, 'return array(') !== 1) throw new RuntimeException('RUNTIME_FILE_SHAPE_MISMATCH');
        $snippet = "/* " . self::RUNTIME_MARKER . " */\n"
            . "\$vfPrivateReadTokenFile = \$base . '/" . self::SECRET_DIR_NAME . "/" . self::SECRET_FILE_NAME . "';\n"
            . "if (is_file(\$vfPrivateReadTokenFile) && !is_link(\$vfPrivateReadTokenFile)) {\n"
            . "    \$vfPrivateReadToken = include \$vfPrivateReadTokenFile;\n"
            . "    if (is_string(\$vfPrivateReadToken)) {\n"
            . "        \$vfPrivateReadToken = trim(\$vfPrivateReadToken);\n"
            . "        if (\$vfPrivateReadToken !== '' && strlen(\$vfPrivateReadToken) <= 4096 && strpos(\$vfPrivateReadToken, \"\\0\") === false) {\n"
            . "            putenv('VF_PRIVATE_READ_TOKEN=' . \$vfPrivateReadToken);\n"
            . "        }\n"
            . "    }\n"
            . "    unset(\$vfPrivateReadToken);\n"
            . "}\n"
            . "unset(\$vfPrivateReadTokenFile);\n";
        return preg_replace('/return array\(/', $snippet . 'return array(', $runtimeBytes, 1) ?? throw new RuntimeException('RUNTIME_ADAPTER_PATCH_FAILED');
    }

    private static function secretPhpBytes(string $token): string
    {
        if ($token === '' || strlen($token) > 4096 || strpos($token, "\0") !== false || strpos($token, "\r") !== false || strpos($token, "\n") !== false) throw new RuntimeException('TOKEN_FORMAT_INVALID');
        return "<?php\nif (isset(\$_SERVER['SCRIPT_FILENAME']) && realpath((string)\$_SERVER['SCRIPT_FILENAME']) === __FILE__) { http_response_code(404); exit; }\nreturn " . var_export($token, true) . ";\n";
    }

    private static function recoverInterruptedActivation(string $root): void
    {
        $journalPath = self::stateFile(self::ACTIVATION_JOURNAL_FILE); $journal = self::loadPhpArray($journalPath);
        if (empty($journal) || ($journal['state'] ?? '') !== 'APPLYING') return;
        $runtimePath = $root . '/app/.runtime.php'; $oldRuntime = base64_decode((string)($journal['old_runtime_b64'] ?? ''), true);
        if (!is_string($oldRuntime) || $oldRuntime === '') throw new RuntimeException('INTERRUPTED_RECOVERY_RUNTIME_INVALID');
        self::atomicWrite($runtimePath, $oldRuntime, 0640); $secretPath = self::secretFile();
        if (!empty($journal['secret_existed'])) {
            $oldSecret = base64_decode((string)($journal['old_secret_b64'] ?? ''), true);
            if (!is_string($oldSecret)) throw new RuntimeException('INTERRUPTED_RECOVERY_SECRET_INVALID');
            self::atomicWrite($secretPath, $oldSecret, 0600);
        } else @unlink($secretPath);
        @unlink($journalPath);
    }

    private static function installCredential(string $root, string $token): array
    {
        self::ensurePrivateGuards(self::secretDir());
        $runtimePath = $root . '/app/.runtime.php'; $runtimeBefore = @file_get_contents($runtimePath);
        if (!is_string($runtimeBefore) || $runtimeBefore === '') throw new RuntimeException('RUNTIME_FILE_READ_FAILED');
        $runtimeAfter = self::runtimeAdapterBytes($runtimeBefore); $secretPath = self::secretFile();
        $secretExisted = is_file($secretPath) && !is_link($secretPath); $oldSecret = $secretExisted ? @file_get_contents($secretPath) : '';
        if ($secretExisted && !is_string($oldSecret)) throw new RuntimeException('EXISTING_SECRET_READ_FAILED');
        $journal = ['state'=>'APPLYING','created_at'=>gmdate('c'),'old_runtime_b64'=>base64_encode($runtimeBefore),'secret_existed'=>$secretExisted,'old_secret_b64'=>$secretExisted ? base64_encode((string)$oldSecret) : ''];
        $journalPath = self::stateFile(self::ACTIVATION_JOURNAL_FILE); self::atomicWrite($journalPath, self::phpReturnFile($journal), 0600);
        try {
            self::atomicWrite($secretPath, self::secretPhpBytes($token), 0600); self::atomicWrite($runtimePath, $runtimeAfter, 0640);
            $runtimeDisk = @file_get_contents($runtimePath);
            if (!is_string($runtimeDisk) || strpos($runtimeDisk, self::RUNTIME_MARKER) === false) throw new RuntimeException('RUNTIME_ADAPTER_READBACK_FAILED');
            if (strpos($runtimeDisk, $token) !== false) throw new RuntimeException('TOKEN_LEAKED_IN_RUNTIME_POINTER');
            $secretDisk = include $secretPath;
            if (!is_string($secretDisk) || !hash_equals($token, trim($secretDisk))) throw new RuntimeException('SECRET_READBACK_FAILED');
            @chmod($secretPath, 0600); @chmod(self::secretDir(), 0700); putenv('VF_PRIVATE_READ_TOKEN=' . $token); @unlink($journalPath);
            return ['runtime_adapter'=>'PASS','secret_storage'=>'PASS','secret_mode'=>substr(sprintf('%o', fileperms($secretPath) ?: 0), -4),'runtime_contains_plaintext'=>false];
        } catch (Throwable $e) {
            self::atomicWrite($runtimePath, $runtimeBefore, 0640);
            if ($secretExisted) self::atomicWrite($secretPath, (string)$oldSecret, 0600); else @unlink($secretPath);
            @unlink($journalPath); throw $e;
        }
    }

    private static function relayInfo(string $root, array $rootEvidence): array
    {
        if (!extension_loaded('sodium')) throw new RuntimeException('SODIUM_REQUIRED');
        if (self::credentialConfigured()) {
            try { $verified = self::verifyPersistentRuntime($root, $rootEvidence); if (!empty($verified['ready'])) return ['ok'=>true,'status'=>'success'] + $verified; }
            catch (Throwable $ignored) {}
        }
        $statePath = self::stateFile(self::RELAY_STATE_FILE); $state = self::loadPhpArray($statePath); $now = time();
        if (empty($state) || (int)($state['expires_at'] ?? 0) <= $now || empty($state['nonce']) || empty($state['public_key_b64']) || empty($state['secret_key_b64'])) {
            $keypair = sodium_crypto_box_keypair(); $public = sodium_crypto_box_publickey($keypair); $secret = sodium_crypto_box_secretkey($keypair);
            $state = ['nonce'=>bin2hex(random_bytes(24)),'public_key_b64'=>base64_encode($public),'secret_key_b64'=>base64_encode($secret),'created_at'=>$now,'expires_at'=>$now + self::RELAY_TTL_SECONDS];
            self::atomicWrite($statePath, self::phpReturnFile($state), 0600);
        }
        return ['ok'=>true,'status'=>'ready','project_id'=>self::PROJECT_ID,'component_id'=>self::COMPONENT_ID,'current_version'=>self::SOURCE_VERSION,'current_schema'=>self::SOURCE_SCHEMA,'bridge_source'=>'CORE-UPDATES','root_fingerprint'=>(string)$rootEvidence['fingerprint'],'public_key_b64'=>(string)$state['public_key_b64'],'nonce'=>(string)$state['nonce'],'expires_at'=>gmdate('c', (int)$state['expires_at']),'production_upgrade'=>'NOT_EXECUTED'];
    }

    private static function receiveSealedToken(string $root, array $rootEvidence): array
    {
        if (!extension_loaded('sodium')) throw new RuntimeException('SODIUM_REQUIRED');
        $raw = file_get_contents('php://input', false, null, 0, self::MAX_RELAY_BYTES + 1);
        if (!is_string($raw) || $raw === '' || strlen($raw) > self::MAX_RELAY_BYTES) throw new RuntimeException('RELAY_BODY_INVALID');
        $body = json_decode($raw, true); if (!is_array($body)) throw new RuntimeException('RELAY_JSON_INVALID');
        $statePath = self::stateFile(self::RELAY_STATE_FILE); $state = self::loadPhpArray($statePath);
        if (empty($state) || (int)($state['expires_at'] ?? 0) < time()) throw new RuntimeException('RELAY_STATE_EXPIRED');
        $nonce = (string)($body['nonce'] ?? ''); if ($nonce === '' || !hash_equals((string)$state['nonce'], $nonce)) throw new RuntimeException('RELAY_NONCE_MISMATCH');
        $sealed = base64_decode((string)($body['sealed_token_b64'] ?? ''), true); $public = base64_decode((string)($state['public_key_b64'] ?? ''), true); $secret = base64_decode((string)($state['secret_key_b64'] ?? ''), true);
        if (!is_string($sealed) || !is_string($public) || !is_string($secret)) throw new RuntimeException('RELAY_CRYPTO_INPUT_INVALID');
        if (strlen($public) !== SODIUM_CRYPTO_BOX_PUBLICKEYBYTES || strlen($secret) !== SODIUM_CRYPTO_BOX_SECRETKEYBYTES) throw new RuntimeException('RELAY_KEY_INVALID');
        $keypair = sodium_crypto_box_keypair_from_secretkey_and_publickey($secret, $public); $token = sodium_crypto_box_seal_open($sealed, $keypair); sodium_memzero($secret);
        if (!is_string($token) || trim($token) === '') throw new RuntimeException('RELAY_DECRYPT_FAILED'); $token = trim($token);
        $identity = self::validateCredentialAgainstRelease($token); $activation = self::installCredential($root, $token); $discovery = self::liveDiscovery($token); sodium_memzero($token); @unlink($statePath);
        $result = ['ok'=>true,'status'=>'success','credential_runtime'=>'PASS','manual_vhost_required'=>false,'new_token_required'=>false,'vf_private_read_token'=>'SERVER_SIDE_ONLY','bridge_source'=>'CORE-UPDATES','activation'=>$activation,'current'=>$discovery['current'],'latest'=>$discovery['latest'],'available'=>$discovery['available'],'can_update'=>$discovery['can_update'],'update_source'=>$discovery['update_source'],'repository'=>$discovery['repository'],'release'=>$identity['release'],'asset'=>$identity['asset'],'asset_bytes'=>$identity['asset_bytes'],'asset_sha256'=>$identity['asset_sha256'],'production_version'=>self::SOURCE_VERSION,'schema'=>self::SOURCE_SCHEMA,'production_upgrade'=>'NOT_EXECUTED','root_fingerprint'=>(string)$rootEvidence['fingerprint'],'ready'=>self::isReady($discovery, $identity)];
        self::atomicWrite(self::stateFile(self::RESULT_FILE), self::phpReturnFile($result), 0600); return $result;
    }

    private static function verifyPersistentRuntime(string $root, array $rootEvidence): array
    {
        $token = self::readRuntimeToken(); if ($token === '') throw new RuntimeException('VF_PRIVATE_READ_TOKEN_MISSING');
        $identity = self::validateCredentialAgainstRelease($token); $discovery = self::liveDiscovery($token); $ready = self::isReady($discovery, $identity);
        return ['ok'=>$ready,'status'=>$ready?'success':'not-ready','credential_runtime'=>$ready?'PASS':'FAIL','manual_vhost_required'=>false,'new_token_required'=>false,'vf_private_read_token'=>'SERVER_SIDE_ONLY','bridge_source'=>'CORE-UPDATES','current'=>$discovery['current'],'latest'=>$discovery['latest'],'available'=>$discovery['available'],'can_update'=>$discovery['can_update'],'update_source'=>$discovery['update_source'],'repository'=>$discovery['repository'],'release'=>$identity['release'],'asset'=>$identity['asset'],'asset_bytes'=>$identity['asset_bytes'],'asset_sha256'=>$identity['asset_sha256'],'production_version'=>self::SOURCE_VERSION,'schema'=>self::SOURCE_SCHEMA,'production_upgrade'=>'NOT_EXECUTED','root_fingerprint'=>(string)$rootEvidence['fingerprint'],'ready'=>$ready];
    }

    private static function credentialConfigured(): bool { return self::readRuntimeToken() !== ''; }
    private static function readRuntimeToken(): string { $value = getenv('VF_PRIVATE_READ_TOKEN'); return is_string($value) && trim($value) !== '' ? trim($value) : ''; }

    private static function liveDiscovery(string $token): array
    {
        putenv('VF_PRIVATE_READ_TOKEN=' . $token);
        if (!class_exists('VfUpdateManager') || !function_exists('vf_db')) throw new RuntimeException('UPDATE_MANAGER_UNAVAILABLE');
        $manager = new VfUpdateManager(vf_db()); $check = $manager->check(true); $status = $manager->status();
        return ['current'=>(string)($status['current_version'] ?? $check['current_version'] ?? ''),'latest'=>(string)($status['latest_version'] ?? $check['latest_version'] ?? ''),'available'=>!empty($status['available']) || !empty($check['available']),'can_update'=>!empty($status['can_update']) || !empty($check['can_update']),'update_source'=>(string)($status['update_source'] ?? ''),'repository'=>(string)($status['repository'] ?? ''),'credential_configured'=>!empty($status['credential_configured'])];
    }

    private static function validateCredentialAgainstRelease(string $token): array
    {
        $manifestUrl = 'https://api.github.com/repos/' . self::CORE_REPOSITORY . '/contents/projects/' . self::CORE_PROJECT_FILE . '?ref=main';
        $manifest = json_decode(self::githubRequest($manifestUrl, $token, 'application/vnd.github.raw+json'), true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($manifest)) throw new RuntimeException('P01_MANIFEST_INVALID');
        $expected = ['project_id'=>self::PROJECT_ID,'component_id'=>self::COMPONENT_ID,'target_version'=>'2.21.15','repository'=>self::PRODUCT_REPOSITORY,'release_tag'=>self::EXPECTED_RELEASE_TAG,'asset_name'=>self::EXPECTED_ASSET,'asset_sha256'=>self::EXPECTED_ASSET_SHA256];
        foreach ($expected as $key=>$value) if (!isset($manifest[$key]) || (string)$manifest[$key] !== $value) throw new RuntimeException('P01_MANIFEST_IDENTITY_MISMATCH_' . strtoupper($key));
        if (empty($manifest['enabled']) || (int)($manifest['asset_bytes'] ?? 0) !== self::EXPECTED_ASSET_BYTES) throw new RuntimeException('P01_MANIFEST_ASSET_BYTES_MISMATCH');
        if (!is_array($manifest['from_versions'] ?? null) || !in_array(self::SOURCE_VERSION, $manifest['from_versions'], true)) throw new RuntimeException('P01_MANIFEST_FROM_VERSION_MISMATCH');
        if ((string)($manifest['schema_from'] ?? '') !== self::SOURCE_SCHEMA || (string)($manifest['schema_to'] ?? '') !== self::SOURCE_SCHEMA) throw new RuntimeException('P01_MANIFEST_SCHEMA_MISMATCH');
        $releaseUrl = 'https://api.github.com/repos/' . self::PRODUCT_REPOSITORY . '/releases/tags/' . rawurlencode(self::EXPECTED_RELEASE_TAG);
        $release = json_decode(self::githubRequest($releaseUrl, $token, 'application/vnd.github+json'), true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($release) || (string)($release['tag_name'] ?? '') !== self::EXPECTED_RELEASE_TAG || !empty($release['draft']) || !empty($release['prerelease'])) throw new RuntimeException('P01_RELEASE_IDENTITY_MISMATCH');
        $asset = null; foreach ((array)($release['assets'] ?? []) as $candidate) if (is_array($candidate) && (string)($candidate['name'] ?? '') === self::EXPECTED_ASSET) { $asset = $candidate; break; }
        if (!is_array($asset)) throw new RuntimeException('P01_RELEASE_ASSET_MISSING');
        if ((int)($asset['size'] ?? 0) !== self::EXPECTED_ASSET_BYTES) throw new RuntimeException('P01_RELEASE_ASSET_BYTES_MISMATCH');
        $digest = strtolower((string)($asset['digest'] ?? '')); if ($digest !== '' && $digest !== 'sha256:' . self::EXPECTED_ASSET_SHA256) throw new RuntimeException('P01_RELEASE_ASSET_SHA_MISMATCH');
        return ['release'=>self::EXPECTED_RELEASE_TAG,'asset'=>self::EXPECTED_ASSET,'asset_bytes'=>self::EXPECTED_ASSET_BYTES,'asset_sha256'=>self::EXPECTED_ASSET_SHA256];
    }

    private static function githubRequest(string $url, string $token, string $accept): string
    {
        if (!extension_loaded('curl')) throw new RuntimeException('CURL_REQUIRED'); $ch = curl_init($url); if ($ch === false) throw new RuntimeException('GITHUB_CURL_INIT_FAILED');
        curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_MAXREDIRS=>3,CURLOPT_CONNECTTIMEOUT=>12,CURLOPT_TIMEOUT=>45,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_REDIR_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_HTTPHEADER=>['Accept: ' . $accept,'Authorization: Bearer ' . $token,'X-GitHub-Api-Version: 2022-11-28','User-Agent: vf-start-p01-credential-runtime-activator/1']]);
        $body = curl_exec($ch); $status = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE); $error = curl_error($ch); curl_close($ch);
        if (!is_string($body) || $status < 200 || $status >= 300) throw new RuntimeException('GITHUB_READ_FAILED_HTTP_' . $status . ($error !== '' ? '_CURL' : '')); return $body;
    }

    private static function isReady(array $discovery, array $identity): bool
    {
        return ($discovery['current'] ?? '') === self::SOURCE_VERSION && ($discovery['latest'] ?? '') === '2.21.15' && !empty($discovery['available']) && !empty($discovery['can_update']) && ($discovery['update_source'] ?? '') === 'core-updates' && ($discovery['repository'] ?? '') === 'core-updates + GitHub Release' && ($identity['release'] ?? '') === self::EXPECTED_RELEASE_TAG && ($identity['asset'] ?? '') === self::EXPECTED_ASSET && (int)($identity['asset_bytes'] ?? 0) === self::EXPECTED_ASSET_BYTES && ($identity['asset_sha256'] ?? '') === self::EXPECTED_ASSET_SHA256 && defined('VF_VERSION') && (string)VF_VERSION === self::SOURCE_VERSION && self::schemaHead() === self::SOURCE_SCHEMA;
    }

    private static function htmlStatus(array $rootEvidence): void
    {
        $configured = self::credentialConfigured(); header('Content-Type: text/html; charset=utf-8'); $fp = htmlspecialchars((string)$rootEvidence['fingerprint'], ENT_QUOTES, 'UTF-8'); $configuredText = $configured ? 'PASS' : 'WAITING FOR SEALED RUNNER RELAY';
        echo '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P01 Credential Runtime Activator</title><style>body{margin:0;background:#f5f7f8;color:#111827;font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:900px;margin:36px auto;background:#fff;border:1px solid #dce3e7;border-radius:14px;padding:28px}.ok{color:#087f5b}.wait{color:#a15c00}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}th{width:44%}code{font-size:13px}</style><main><h1>P01 · VF Start Credential Runtime Activator</h1><p>复用 P02 已验证的 sealed Runner → VPS runtime secret 模式。无需修改 Vhost，不创建新 Token，不执行 2.21.15 正式升级。</p><table><tr><th>Application Root</th><td class="ok">PASS</td></tr><tr><th>Root Fingerprint</th><td><code>'.$fp.'</code></td></tr><tr><th>Bridge Source</th><td class="ok">CORE-UPDATES</td></tr><tr><th>Production Version</th><td>2.21.14</td></tr><tr><th>Schema</th><td>2026080902</td></tr><tr><th>Credential Runtime</th><td class="'.($configured?'ok':'wait').'">'.$configuredText.'</td></tr><tr><th>Manual Vhost Modification</th><td>NO</td></tr><tr><th>New Token</th><td>NO</td></tr><tr><th>Production Upgrade</th><td>NOT EXECUTED</td></tr></table><p>该页面不会显示、接收或要求你复制 Token。Runner 只会向一次性公钥发送密封后的凭证。</p></main></html>'; exit;
    }
}

VfP01CredentialRuntimeActivator::main();
