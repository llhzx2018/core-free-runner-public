<?php
declare(strict_types=1);
/** R07 focused sitemap eligibility regression against exact checked-out Theme source. */
function wp_parse_url(string $url, int $component = -1) { return parse_url($url, $component); }
require __DIR__ . '/../../../target/src/inc/services/url/public-url-sitemap-output-guards.php';
$cases = [
    'search query' => ['https://example.test/?s=player', false],
    'empty search query' => ['https://example.test/?s=', false],
    'directory keyword' => ['https://example.test/glossary/?vf_q=codec', false],
    'directory category' => ['https://example.test/guides/?vf_filter=editing', false],
    'glossary letter' => ['https://example.test/glossary/?vf_letter=a', false],
    'directory pagination' => ['https://example.test/blog/?paged=2', false],
    'normal page' => ['https://example.test/blog/', true],
    'WordPress plain permalink' => ['https://example.test/?page_id=123', true],
];
foreach ($cases as $name => [$url, $expected]) {
    $actual = vf_theme_should_include_in_sitemap($url);
    if ($actual !== $expected) {
        fwrite(STDERR, "FAIL $name: expected " . (int)$expected . ", got " . (int)$actual . PHP_EOL);
        exit(1);
    }
    echo "PASS $name\n";
}
echo "R07 sitemap URL-eligibility checks: 8/8 PASS\n";
