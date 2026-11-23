<?php
declare(strict_types=1);
/**
 * One-time synthetic REAL OpenSSH + real Nginx strict-TLS transport acceptance.
 * No P08 product files are edited. All endpoints bind to VM loopback only.
 * The public-address override exists ONLY for the synthetic RFC2606 test FQDN.
 * Private Laravel source remains in an ephemeral read-only Actions checkout.
 */
if (getenv('P08_ISOLATED_SSH_TEST') !== 'YES'
    || getenv('P08_SOURCE_SHA') !== '00a62c8c8e991c10344255511efc6d45174c1e1c') {
    fwrite(STDOUT, "P08_S3_TRANSPORT_ENV=BLOCKED\n"); exit(2);
}
$appRoot = getenv('P08_TEST_APP_ROOT') ?: '';
$root = getenv('P08_TEST_ROOT') ?: '';
$hostname = getenv('P08_TEST_HOST') ?: '';
if (!is_dir($root) || !is_file($appRoot.'/vendor/autoload.php')
    || $hostname !== 'p08-stage-preview.example.org') {
    fwrite(STDOUT, "P08_S3_TRANSPORT_INPUT=BLOCKED\n"); exit(2);
}
putenv('APP_ENV=testing');
putenv('APP_KEY=base64:'.base64_encode(str_repeat('S',32)));
putenv('DB_CONNECTION=sqlite');
putenv('DB_DATABASE=:memory:');
putenv('SESSION_DRIVER=array');
putenv('CACHE_STORE=array');
// Public logs expose only coarse synthetic failure categories, never SSH keys or stderr.
set_exception_handler(static function (Throwable $error): void {
    $message=(string)$error->getMessage();
    $category=match (true) {
        $message==='VPS_SSH_REMOTE_DENIED_OR_FAILED' => 'REAL_SSH_AUTH_OR_EXEC',
        str_starts_with($message,'VPS_') => preg_match('/^VPS_[A-Z0-9_]{4,80}$/D', $message) ? $message : 'VPS_UNKNOWN_POLICY',
        str_contains($message,'SYNTHETIC_') => 'SYNTHETIC_FIXTURE',
        default => 'PHP_BOOTSTRAP_OTHER',
    };
    echo "P08_S3_TRANSPORT_EARLY_EXCEPTION=".$category."\n";
    exit(1);
});
require $appRoot.'/vendor/autoload.php';
// This provider transport smoke does not need the product's first-install
// console kernel. Testing it on an uninstalled checkout can exit before
// executing ANY gateway assertion. Supply only the real Laravel HTTP Factory
// used by VpsAtomicGateway::verify(), with no fake HTTP responses.
\Illuminate\Support\Facades\Facade::setFacadeApplication(new \Illuminate\Container\Container());
\Illuminate\Support\Facades\Http::swap(new \Illuminate\Http\Client\Factory());
echo "P08_S3_TRANSPORT_PHP_GATEWAY_BOOTSTRAP=PASS\n";

use App\Modules\StaticDeployment\Actions\OpenSshRemoteExecutor;
use App\Modules\StaticDeployment\Actions\VpsAtomicGateway;
use App\Modules\StaticDeployment\Actions\VpsTargetPolicy;
use VF\AdOps\StaticDeployment\StaticBundleInspector;

$successes=0; $lastStep='BOOTSTRAP';
$check=static function (bool $okay,string $step) use (&$successes,&$lastStep): void {
    $lastStep=$step;
    if (!$okay) throw new RuntimeException('SYNTHETIC_ASSERTION_FAILED');
    ++$successes;
};
$reject=static function (callable $fn,string $step) use ($check): void {
    $blocked=false;
    try { $fn(); } catch (Throwable $e) { $blocked=true; }
    $check($blocked,$step);
};
$site='/home/p08stage/vf-adops-static/lp-preview';
$check($hostname==='p08-stage-preview.example.org','SYNTHETIC_HOSTNAME_ONLY');
$check(is_dir($site.'/releases') && is_dir($site.'/.staging'),'EMPTY_DEDICATED_SITE');
$check(is_file($site.'/.vf-adops-static-site'),'OWNER_MARKER_EXISTS');
$check(extension_loaded('curl') && is_file('/usr/bin/ssh'),'CURL_AND_REAL_SSH_AVAILABLE');
$policy = new class extends VpsTargetPolicy {
    public function publicAddress(string $host): string {
        if ($host !== 'p08-stage-preview.example.org') throw new RuntimeException('SYNTHETIC_HOST_ONLY');
        parent::publicHost($host);
        return '127.0.0.1';
    }
};
$config=[
    'host'=>$hostname,
    'username'=>'p08stage',
    'slug'=>'lp-preview',
    'host_key'=>trim((string)file_get_contents(getenv('P08_TEST_SSH_PIN_FILE'))),
    'private_key'=>(string)file_get_contents(getenv('P08_TEST_SSH_IDENTITY_FILE')),
    'site_url'=>'https://'.$hostname,
];
$remote = new OpenSshRemoteExecutor($policy);
$gateway = new VpsAtomicGateway($remote,$policy);
$lastStep='REAL_SSH_INITIAL_STATUS_NONE';
$lastStep='REAL_SSH_INITIAL_STATUS_NONE';
echo "P08_S3_TRANSPORT_REAL_GATEWAY_STATUS=START\n";
$check($gateway->status($config) === null,'REAL_SSH_INITIAL_STATUS_NONE');
echo "P08_S3_TRANSPORT_REAL_GATEWAY_STATUS=PASS\n";
$check(str_starts_with($config['host_key'],'ssh-ed25519 '),'REAL_ED25519_KEY_PIN');

$prepare=static function(string $tag) use ($root): array {
    $directory=$root.'/bundle-'.$tag;
    if (!mkdir($directory.'/assets',0700,true)) throw new RuntimeException('SYNTHETIC_SOURCE_DIR');
    $html='<!doctype html><html><head><title>Stage '.$tag.'</title><link rel="stylesheet" href="/assets/site.css"></head><body><main>Stage-'.$tag.'</main></body></html>';
    $css='body{margin:0}main{color:teal}/*'.$tag.'*/';
    file_put_contents($directory.'/index.html',$html);
    file_put_contents($directory.'/assets/site.css',$css);
    $inventory=(new StaticBundleInspector())->inspect($directory);
    return [$directory,$inventory,$html,$css];
};
[$sourceA,$a,$htmlA,$cssA]=$prepare('A');
[$sourceB,$b,$htmlB,$cssB]=$prepare('B');
$check($a['file_count']===2 && $b['file_count']===2,'TWO_REAL_STATIC_INVENTORIES');
$check($a['bundle_sha256']!==$b['bundle_sha256'],'INDEPENDENT_SHA_IDENTITIES');

$httpsBytes=static function (string $path) use ($hostname): string {
    $curl=curl_init();
    if (!is_resource($curl) && !($curl instanceof CurlHandle)) throw new RuntimeException('SYNTHETIC_CURL_INIT');
    curl_setopt_array($curl,[
        CURLOPT_URL=>'https://'.$hostname.'/'.$path,
        CURLOPT_RETURNTRANSFER=>true,
        CURLOPT_RESOLVE=>[$hostname.':443:127.0.0.1'],
        CURLOPT_PROXY=>'',
        CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_CONNECTTIMEOUT=>3,
        CURLOPT_TIMEOUT=>7,
    ]);
    $payload=curl_exec($curl);
    $status=(int)curl_getinfo($curl,CURLINFO_HTTP_CODE);
    $curlCode=curl_errno($curl);
    curl_close($curl);
    if (!is_string($payload) || $status!==200) {
        echo "P08_S3_TRANSPORT_HTTPS_HTTP_STATUS=".$status."\n";
        echo "P08_S3_TRANSPORT_HTTPS_CURL_CODE=".$curlCode."\n";
        throw new RuntimeException('SYNTHETIC_HTTPS_READBACK_UNAVAILABLE');
    }
    return $payload;
};
try {
    echo "P08_S3_TRANSPORT_DEPLOY_A=START\n";
    $resultA=$gateway->deploy($config,$sourceA,$a['bundle_sha256'],null);
    echo "P08_S3_TRANSPORT_DEPLOY_A=COMPLETE\n";
    $check($resultA['current']===$a['bundle_sha256'],'REAL_SSH_TAR_FIRST_DEPLOY');
    $independentStatusA=$gateway->status($config);
    $independentLinkA=$remote->command($config,'readlink -- /home/p08stage/vf-adops-static/lp-preview/current');
    echo "P08_S3_TRANSPORT_FIRST_STATUS_CLASS=".(
        $independentStatusA===$a['bundle_sha256'] ? 'A' :
        ($independentStatusA===null ? 'NONE' : ($independentStatusA===$b['bundle_sha256'] ? 'B' : 'OTHER')))."\n";
    echo "P08_S3_TRANSPORT_FIRST_SYMLINK_CLASS=".(
        $independentLinkA==='releases/'.$a['bundle_sha256'] ? 'A' : 'OTHER')."\n";
    $check($independentStatusA===$a['bundle_sha256'],'FIRST_REAL_SSH_POINTER');
    $lastStep='FIRST_DIRECT_NGINX_HTTPS';
    $nginxIndex=$httpsBytes('index.html');
    echo "P08_S3_TRANSPORT_FIRST_NGINX_EXACT_SHA=".(
        hash_equals(hash('sha256',$htmlA),hash('sha256',$nginxIndex)) ? 'YES':'NO')."\n";
    $check($nginxIndex===$htmlA,'FIRST_NGINX_HTTPS_EXACT_HTML');
    $lastStep='FIRST_LARAVEL_HTTP_FACADE_VERIFY';
    echo "P08_S3_TRANSPORT_FIRST_GATEWAY_TLS=START\n";
    $check($gateway->verify($config,$a['bundle_sha256'],$a['files']['index.html']['sha256']),'FIRST_STRICT_TLS_GATEWAY_VERIFY');
    echo "P08_S3_TRANSPORT_FIRST_GATEWAY_TLS=PASS\n";
    $check($httpsBytes('assets/site.css')===$cssA,'FIRST_NGINX_HTTPS_NESTED_CSS');

    echo "P08_S3_TRANSPORT_DEPLOY_B=START\n";
    $resultB=$gateway->deploy($config,$sourceB,$b['bundle_sha256'],$a['bundle_sha256']);
    echo "P08_S3_TRANSPORT_DEPLOY_B=COMPLETE\n";
    $check($resultB['current']===$b['bundle_sha256'],'REAL_SSH_TAR_SECOND_DEPLOY');
    $check($gateway->verify($config,$b['bundle_sha256'],$b['files']['index.html']['sha256']),'SECOND_STRICT_TLS_GATEWAY_VERIFY');
    $check($httpsBytes('index.html')===$htmlB,'SECOND_NGINX_HTTPS_EXACT_HTML');
    $check($httpsBytes('assets/site.css')===$cssB,'SECOND_NGINX_HTTPS_NESTED_CSS');
    $check(is_dir($site.'/releases/'.$a['bundle_sha256']) && is_dir($site.'/releases/'.$b['bundle_sha256']),'PRESERVED_TWO_IMMUTABLE_RELEASES');

    $reject(static fn()=> $gateway->deploy($config,$sourceA,$a['bundle_sha256'],null),'STALE_DEPLOY_NO_REPLAY');
    $check($gateway->status($config)===$b['bundle_sha256'],'STALE_REFUSAL_KEEPS_B');

    // A malicious actor changed the OLD release index; history must fail closed.
    $oldIndex=$site.'/releases/'.$a['bundle_sha256'].'/index.html';
    $remote->command($config,'printf %s '.escapeshellarg('remote-tampered').' > '.escapeshellarg($oldIndex));
    $reject(static fn()=> $gateway->rollback($config,$b['bundle_sha256'],$a['bundle_sha256'],$a['files']['index.html']['sha256']),'TAMPERED_HISTORY_REFUSED_OVER_SSH');
    $check($gateway->status($config)===$b['bundle_sha256'],'TAMPER_PRESERVES_LIVE_B');
    $remote->command($config,'printf %s '.escapeshellarg(base64_encode($htmlA)).' | base64 -d > '.escapeshellarg($oldIndex));

    $returnedA=$gateway->rollback($config,$b['bundle_sha256'],$a['bundle_sha256'],$a['files']['index.html']['sha256']);
    $check($returnedA['current']===$a['bundle_sha256'],'HISTORY_B_TO_A_ACTUAL_SSH_ATOMIC');
    $check($gateway->verify($config,$a['bundle_sha256'],$a['files']['index.html']['sha256']),'RESTORED_A_STRICT_TLS_VERIFY');
    $check($httpsBytes('index.html')===$htmlA,'RESTORED_A_REAL_HTTPS');

    $returnedB=$gateway->rollback($config,$a['bundle_sha256'],$b['bundle_sha256'],$b['files']['index.html']['sha256']);
    $check($returnedB['current']===$b['bundle_sha256'],'HISTORY_A_TO_B_ACTUAL_SSH_ATOMIC');
    $check($gateway->verify($config,$b['bundle_sha256'],$b['files']['index.html']['sha256']),'RESTORED_B_STRICT_TLS_VERIFY');
    $check($httpsBytes('index.html')===$htmlB,'RESTORED_B_REAL_HTTPS');
    $reject(static fn()=> $gateway->rollback($config,$a['bundle_sha256'],$b['bundle_sha256'],$b['files']['index.html']['sha256']),'STALE_ROLLBACK_REFUSED');

    $badPin=$config;
    $raw=base64_decode(explode(' ',$badPin['host_key'],2)[1],true);
    if (!is_string($raw) || strlen($raw)<2) throw new RuntimeException('INVALID_SYNTHETIC_PIN');
    $badPin['host_key']='ssh-ed25519 '.base64_encode(substr($raw,0,-1).chr(ord(substr($raw,-1))^1));
    $reject(static fn()=> $gateway->status($badPin),'STRICT_PIN_WRONG_ED25519_REJECTED');
    $check($gateway->status($config)===$b['bundle_sha256'],'DENIED_HOST_KEY_PRESERVES_RELEASE');

    $reject(static fn()=> $remote->uploadTar($config,'/tmp/unsafe-stage','/tmp/nonexistent.tar'),'TAR_UPLOAD_OUTSIDE_RESERVED_STAGE_REFUSED');
    $check($httpsBytes('assets/site.css')===$cssB,'POST_NEGATIVE_HTTPS_ASSETS_UNCHANGED');
    $check(is_link($site.'/current') && readlink($site.'/current')==='releases/'.$b['bundle_sha256'],'FINAL_LIVE_POINTER_B');
    echo "P08_S3_TRANSPORT_REAL_SSH_NGINX_TLS={$successes}/{$successes}_PASS\n";
} catch (Throwable $e) {
    // No provider output, SSH logs, source path, secret, exception or PHP stack trace.
    $type = match (true) {
        $e instanceof \Illuminate\Http\Client\ConnectionException => 'LARAVEL_HTTP_CONNECTION',
        $e instanceof \GuzzleHttp\Exception\GuzzleException => 'GUZZLE_CLIENT',
        $e instanceof RuntimeException => 'RUNTIME_OR_ASSERTION',
        $e instanceof Error => 'PHP_RUNTIME',
        default => 'OTHER_EXCEPTION',
    };
    echo "P08_S3_TRANSPORT_FAILED_STEP=".$lastStep."\n";
    echo "P08_S3_TRANSPORT_EXCEPTION_CLASS=".$type."\n";
    exit(1);
}
