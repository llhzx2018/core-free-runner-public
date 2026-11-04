<?php
/**
 * P08 R16 one-off isolated fixture: run the real P08 publisher against a
 * genuine ephemeral Kuma REST server. No mocked HTTP, no production data.
 */
declare(strict_types=1);
require 'vendor/autoload.php';
$app = require 'bootstrap/app.php';
$app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();

$root = getenv('P08_R16_PUBLIC_ROOT');
$sqlite = getenv('P08_R16_SQLITE');
$token = getenv('P08_R16_KUMA_TOKEN');
if (!$root || !$sqlite || !$token || !str_starts_with($root, '/')
    || !str_starts_with($sqlite, '/')
    || !str_contains($root, '/p08-kuma/p08-public')
    || !str_contains($sqlite, '/p08-kuma/')) {
    throw new RuntimeException('P08_R16_ISOLATED_INPUTS_REQUIRED');
}
if (!is_dir($root) || file_exists($sqlite)) {
    throw new RuntimeException('P08_R16_DIRTY_TEST_PATH_BLOCKED');
}
if (!touch($sqlite)) throw new RuntimeException('P08_R16_SQLITE_CREATE_FAILED');
chmod($sqlite, 0600);

$app->usePublicPath($root);
config()->set('database.default', 'sqlite');
config()->set('database.connections.sqlite.database', $sqlite);
\Illuminate\Support\Facades\DB::purge('sqlite');
config()->set('tracker.simple_kuma.api_base', 'https://kuma.example.test');
config()->set('tracker.simple_kuma.public_base', 'https://kuma.example.test');
config()->set('tracker.simple_kuma.api_token', $token);
if (\Illuminate\Support\Facades\Artisan::call('migrate', ['--force' => true]) !== 0) {
    throw new RuntimeException('P08_R16_SYNTHETIC_SCHEMA_FAILED');
}

$adapter = new \App\Support\Tracker\SimpleKumaAdapter();
$remote = $adapter->verify(1, 1, 1);
if ($remote['verification_scope'] !== 'RESOURCE_ONLY') {
    throw new RuntimeException('P08_R16_REMOTE_ID_UNVERIFIED');
}
$owner = \App\Models\User::query()->create([
    'name' => 'R16 Synthetic Owner',
    'email' => 'owner-r16@isolated.example',
    'password' => 'Synthetic-Only-P08-Owner-R16-Password!',
]);
$offer = \App\Models\OfferReference::query()->create([
    'owner_id' => $owner->id,
    'name' => 'R16 Synthetic CPA Offer',
    'kind' => 'app',
    'network' => 'Synthetic Network',
    'geo' => 'US',
    'platform' => 'android',
    'external_offer_id' => '1',
    'status' => 'active',
]);
$page = \App\Models\LandingPage::query()->create([
    'owner_id' => $owner->id,
    'offer_reference_id' => $offer->id,
    'slug' => 'synthetic-lander',
    'template_key' => 'app-classic',
    'title' => 'Synthetic R16',
    'status' => 'draft',
    'content' => [
        'headline' => 'Verified synthetic landing page',
        'description' => 'Browser-tested real P08 immutable publication.',
        'cta_label' => 'Continue to synthetic offer',
        'cta_url' => 'https://offers.example.test/direct',
        'disclaimer' => 'Synthetic integration test only.',
        'features' => ['Real P08 publisher', 'No real affiliate traffic'],
        'hero_asset_id' => null,
    ],
]);
\App\Models\TrackerBinding::query()->create([
    'owner_id' => $owner->id,
    'page_id' => $page->id,
    'provider' => 'simple_kuma',
    'remote_campaign_id' => $remote['campaign_id'],
    'remote_offer_id' => $remote['offer_id'],
    'remote_landing_id' => $remote['landing_page_id'],
    'tracking_url' => $remote['tracking_url'],
    'verification_scope' => $remote['verification_scope'],
    'status' => 'verified_resources',
    'verified_at' => now(),
]);
$publisher = new \App\Support\Landing\StaticReleasePublisher(
    new \App\Support\Landing\StaticLandingRenderer()
);
$receipt = $publisher->publish($page, '00000000-0000-4000-8000-000000000016');
if ($receipt['data']['status'] !== 'published') {
    throw new RuntimeException('P08_R16_PUBLISH_FAILED');
}
$published = $root.$receipt['data']['url'];
if (!is_file($published) || !str_contains(file_get_contents($published), 'data-kuma-exit=') ||
    !str_contains(file_get_contents($published), 'new URL(window.location.href)')) {
    throw new RuntimeException('P08_R16_PUBLISHED_HTML_UNVERIFIED');
}
$revision = \App\Models\PageRevision::query()->findOrFail($receipt['data']['active_revision_id']);
if (hash_file('sha256', $published) !== $revision->html_sha256) {
    throw new RuntimeException('P08_R16_PUBLISHED_HASH_MISMATCH');
}
$trackingFile = dirname($root).'/tracking-url';
if (file_put_contents($trackingFile, $remote['tracking_url'], LOCK_EX) === false) {
    throw new RuntimeException('P08_R16_TRACKING_LINK_SAVE_FAILED');
}
chmod($trackingFile, 0600);
echo "P08_R16_EXACT_PRIVATE_SOURCE_PUBLISHER_AND_HASH_READBACK_PASS\n";
echo "P08_R16_TRACKING_SCOPE_RESOURCE_ONLY\n";
